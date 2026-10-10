"""decide.py - post-LLM steps: turn the LLM's decision + facts into the final output.

  .venv/bin/python decide.py PLANTGUARD-00000 [--evaluate]            (calls the LLM)
  .venv/bin/python decide.py PLANTGUARD-00000 --save runs/p0.json     (calls the LLM, saves its output)
  .venv/bin/python decide.py --from-file runs/p0.json [--evaluate]    (NO LLM call: replays the file)

Steps (all deterministic, JSON data only):
  P1 final triage   the 5 graded fields, each from its authoritative source
  P2 parts check    stock / reorder / open POs for the parts the LLM named
  P3 technicians    pool filtered by the permit the LLM chose
  P4 guards         contradictions and invented references lower confidence
  P5 route          auto / human_review
"""
import json
import logging
from datetime import date, timedelta
from pathlib import Path

import llm_step

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# P1: final triage
#
# IN SHORT: assemble the 5 graded fields (priority, probable_fault,
# safety_critical, requires_permit, missing_fields), taking each from the
# source that is AUTHORITATIVE for it, and record that source.
#   input : out from llm_step.run()  -> out["decision"], out["facts"]
#   output: {"priority", "probable_fault", "safety_critical", "requires_permit",
#            "missing_fields", "permit_type", "is_trip", "sources": {...}}
#
# Why P1 exists:
#   the LLM is not the best source for everything. Where code computed a
#   field exactly from JSON, code wins; where judgement on the documents is
#   needed, the LLM's answer is used.
#
# Field -> source:
#   missing_fields  : facts (step 3)          exact null check, never asked of the LLM
#   is_trip         : facts (step 4) when it is True/False (alarm strings);
#                     the LLM's is_trip when step 4 returned None (prose)
#   priority, probable_fault, safety_critical, requires_permit, permit_type
#                   : LLM (needs the documents)
#
# sources records where each field came from: when a field is wrong in
# evaluation, it says whether to fix code (a step) or the LLM side
# (retrieval / prompt / model).
# P1 does NOT overrule the LLM's judgement; checks on it come in P4 / P5.
# ---------------------------------------------------------------------------
GRADED_FIELDS = ("priority", "probable_fault", "safety_critical", "requires_permit",
                 "missing_fields")


def final_triage(out: dict) -> dict:
    """The graded fields, each from its authoritative source."""
    decision, facts = out["decision"], out["facts"]

    # Trip: code's pattern match for alarm strings, the LLM's reading for prose
    code_trip = facts["trip"]["is_trip"]
    if code_trip is not None:
        is_trip, trip_source = code_trip, "facts.step4"
    else:
        is_trip, trip_source = decision["is_trip"], "llm"

    return {
        "priority": decision["priority"],
        "probable_fault": decision["probable_fault"],
        "safety_critical": decision["safety_critical"],
        "requires_permit": decision["requires_permit"],
        "missing_fields": facts["missing_fields"],
        "permit_type": decision["permit_type"],
        "is_trip": is_trip,
        "sources": {"missing_fields": "facts.step3", "is_trip": trip_source,
                    "priority": "llm", "probable_fault": "llm",
                    "safety_critical": "llm", "requires_permit": "llm",
                    "permit_type": "llm"},
    }


# ---------------------------------------------------------------------------
# P2: parts check
#
# IN SHORT: for every part number the LLM named (decision["fault_parts"]),
# look it up in this asset class's inventory (facts["inventory"]["parts"],
# from step 11) and report whether it is available, and if not, when.
#   input : out["decision"]["fault_parts"], out["facts"]["inventory"], event date
#   output: {"parts": [one entry per named part], "all_in_stock": bool,
#            "not_in_inventory": [...], "stock_note": ...}
#
# Why P2 exists:
#   the LLM picked the parts from the documents; only the JSON knows whether
#   they are on the shelf. A repair is only as fast as its slowest part.
#
# Per part (all from inventory.json / purchase_orders.json via step 11):
#   status       : "in_stock"          on_hand > 0
#                  "out_of_stock"      on_hand == 0
#                  "not_in_inventory"  not a part of this asset class
#                                      (wrong class, mistyped or invented: P4 flags it)
#   below_reorder, used_before, lead_time_days, open_purchase_orders : as step 11
#   available_by : earliest date the part could be in hand (arithmetic only):
#                    in stock        -> event date
#                    open PO         -> earliest expected_delivery_on
#                    otherwise       -> event date + lead_time_days
#
# Only this class's parts are searched: a part from another machine class
# cannot fix this machine, so naming one is a mistake to surface, not to hide.
# all_in_stock is True when no parts are named (nothing needed = nothing
# missing); whether parts SHOULD have been named is judged in P4.
# Part numbers are normalised (strip + upper) before lookup, so "vpw-p-00043 "
# still matches.
# Limitation (from step 11): on_hand is today's value, not stock at event time.
# ---------------------------------------------------------------------------
def normalise_part(part: str) -> str:
    """'  vpw-p-00043 ' -> 'VPW-P-00043'."""
    return part.strip().upper()


def available_by(part: dict, event_day: date) -> str:
    """Earliest date the part could be in hand (ISO string)."""
    if part["on_hand"] > 0:
        return event_day.isoformat()
    deliveries = [po["expected_delivery_on"] for po in part["open_purchase_orders"]]
    if deliveries:
        return min(deliveries)                    # ISO dates sort correctly as strings
    return (event_day + timedelta(days=part["lead_time_days"])).isoformat()


def check_part(number: str, by_number: dict, event_day: date) -> dict:
    """One named part -> its availability entry."""
    part = by_number.get(number)
    if part is None:
        return {"part_number": number, "status": "not_in_inventory"}
    return {
        "part_number": number,
        "description": part["description"],
        "status": "in_stock" if part["on_hand"] > 0 else "out_of_stock",
        "on_hand": part["on_hand"],
        "reorder_point": part["reorder_point"],
        "below_reorder": part["below_reorder"],
        "used_before": part["used_before"],
        "lead_time_days": part["lead_time_days"],
        "open_purchase_orders": part["open_purchase_orders"],
        "available_by": available_by(part, event_day),
    }


def parts_check(out: dict) -> dict:
    """Availability of every part the LLM named for this fault."""
    facts = out["facts"]
    if "received_at" not in facts:
        raise SystemExit("facts has no received_at: re-save this run (decide.py <id> --save ...)")
    inventory = facts["inventory"]
    by_number = {p["part_number"]: p for p in inventory["parts"]}
    event_day = date.fromisoformat(facts["received_at"][:10])

    # dict.fromkeys: drop duplicates, keep the LLM's order
    named = list(dict.fromkeys(normalise_part(p) for p in out["decision"]["fault_parts"]))
    parts = [check_part(n, by_number, event_day) for n in named]

    return {
        "parts": parts,
        "all_in_stock": all(p["status"] == "in_stock" for p in parts),
        "not_in_inventory": [p["part_number"] for p in parts if p["status"] == "not_in_inventory"],
        "stock_note": inventory["stock_note"],
    }


# ---------------------------------------------------------------------------
# P3: technician filter
#
# IN SHORT: from step 12's ranked pool (right trade for this asset class),
# keep the technicians who hold the certification for the permit the LLM
# chose, then sort the ones known to be available first.
#   input : out["facts"]["technicians"] (step 12), triage from P1
#   output: {"required_certification", "qualified": [...], "excluded": {...},
#            "recommended": [top TECH_RECOMMEND], "calendar_covers_event_date",
#            "no_qualified_technician": bool}
#
# Why P3 exists:
#   step 12 could only match the TRADE (before the diagnosis). Now the LLM has
#   said which permit the job needs, so the pool can be narrowed to people
#   allowed to do it.
#
# Certification (JSON naming, no document rule):
#   permit_type "<type>"  ->  technicians.json column "<type>_certified"
#   e.g. "pressure_system" -> "pressure_system_certified"
#   no permit (requires_permit false) -> no certification filter
#   requires_permit true but permit_type None -> cannot filter: keep everyone,
#     set required_certification "unknown" (P4 flags it). Filtering on a guess
#     could remove the right person.
#
# Availability (technician_calendar.json, from step 12):
#   "available"   status == on_shift and available_hours > 0 on the event date
#   "unavailable" any other calendar status, or 0 hours left
#   "unknown"     no calendar row for that date (NOT treated as available)
#   Order: available, then unknown, then unavailable. The sort is stable, so
#   within each group step 12's ranking (trade match, same line, level,
#   experience) is kept.
#
# LOTO: loto_authorised is REPORTED for every candidate but NOT used as a
# filter: whether the job needs lockout comes from the documents (LLM side),
# so code does not decide it. (Design decision: report-only.)
# ---------------------------------------------------------------------------
TECH_RECOMMEND = 3                         # technicians recommended (design choice)
AVAILABILITY_ORDER = {"available": 0, "unknown": 1, "unavailable": 2}
QUALIFIED_FIELDS = ("technician_id", "name", "primary_skill", "skill_level", "home_line",
                    "same_line", "loto_authorised", "availability")


def required_certification(triage: dict) -> str | None:
    """'<permit_type>_certified', 'unknown', or None when no permit is needed."""
    if not triage["requires_permit"]:
        return None
    if triage["permit_type"] is None:
        return "unknown"
    return f"{triage['permit_type']}_certified"


def availability_status(candidate: dict) -> str:
    """'available' / 'unavailable' / 'unknown' from the calendar on the event date."""
    day = candidate["availability"]
    if day is None:
        return "unknown"
    if day["status"] == "on_shift" and day["available_hours"] > 0:
        return "available"
    return "unavailable"


def technician_filter(out: dict, triage: dict) -> dict:
    """Qualified technicians for this job, available ones first."""
    pool = out["facts"]["technicians"]
    cert = required_certification(triage)

    qualified, excluded = [], {"missing_certification": []}
    for c in pool["candidates"]:                        # already ranked by step 12
        if cert not in (None, "unknown") and not c["certifications"].get(cert, False):
            excluded["missing_certification"].append(c["technician_id"])
            continue
        qualified.append({**{k: c[k] for k in QUALIFIED_FIELDS},
                          "availability_status": availability_status(c)})

    # Stable sort: availability groups, step 12's order kept inside each group
    qualified.sort(key=lambda c: AVAILABILITY_ORDER[c["availability_status"]])

    return {
        "required_certification": cert,
        "qualified": qualified,
        "excluded": {k: len(v) for k, v in excluded.items()},
        "recommended": [c["technician_id"] for c in qualified[:TECH_RECOMMEND]],
        "calendar_covers_event_date": pool["calendar_covers_event_date"],
        "no_qualified_technician": not qualified,
    }


# ---------------------------------------------------------------------------
# P4: guards
#
# IN SHORT: check the LLM's decision for contradictions with the facts and
# with P1-P3, record each problem as a flag, and lower confidence to match.
#   input : out (decision, facts, invalid_citations), triage (P1),
#           parts (P2), techs (P3)
#   output: {"flags": [{"code", "severity", "message"}], "llm_confidence",
#            "final_confidence", "needs_human_review": bool}
#
# Why P4 exists:
#   the LLM can sound sure and still be wrong. These checks catch the cases
#   code CAN detect: invented references, impossible parts, contradictions,
#   overconfidence on missing evidence. The LLM's answer is never edited;
#   problems are made visible (a silent "fix" would hide that the model erred).
#
# Guards are consistency / data checks only (no rules from the documents):
#   code                          severity  when
#   invented_citations            critical  L5 found citations not in the retrieved chunks
#   no_citations                  warning   the decision cites nothing
#   part_not_in_inventory         critical  a named part is not in this class's inventory (P2)
#                                           (the reasoning itself is in doubt)
#   part_out_of_stock             warning   a named part has on_hand == 0 (P2)
#                                           (a real part, just delayed: a planning issue)
#   permit_type_unknown           critical  requires_permit true but no permit_type
#   permit_type_without_permit    warning   permit_type set but requires_permit false
#   no_qualified_technician       critical  nobody holds the required certification (P3)
#   suspect_readings_ignored      warning   facts flag impossible readings (step 5) but
#                                           the LLM did not suspect a sensor fault
#   trip_disagreement             warning   step 4 (alarm string) and the LLM disagree on is_trip
#   overconfident_on_missing_data warning   confidence "high" although readings are missing
#                                           or there is no pre-event telemetry
#   ungrounded_claims             critical  H5 judge: a claim (fault, action, part, safety)
#                                           is not supported by FACTS or the cited chunks
#                                           (a fabricated repair step is a safety hazard)
#                                           one flag per unsupported claim; skipped when
#                                           out["groundedness"] is absent or JUDGE_ENABLED=False
#
# NOT checked here: whether priority / safety / permit are CORRECT. That needs
# the documents (LLM side) and evaluation; P4 only checks what JSON can verify.
#
# Confidence (design choice):
#   any critical flag    -> "low"
#   otherwise, warnings  -> one level down per warning (high -> medium -> low), floor "low"
#   no flags             -> the LLM's own confidence
# needs_human_review = any critical flag (P5 uses it)
# ---------------------------------------------------------------------------
CONFIDENCE_LEVELS = ["low", "medium", "high"]


def flag(code: str, severity: str, message: str) -> dict:
    """One guard result."""
    return {"code": code, "severity": severity, "message": message}


def run_guards(out: dict, triage: dict, parts: dict, techs: dict) -> list[dict]:
    """Every guard that fires, as a list of flags."""
    decision, facts = out["decision"], out["facts"]
    flags = []

    # Citations (L5)
    if out["invalid_citations"]:
        cited = "; ".join(f"{c['file']} | {c['section']}" for c in out["invalid_citations"])
        flags.append(flag("invented_citations", "critical",
                          f"cited documents that were not retrieved: {cited}"))
    if not decision["citations"]:
        flags.append(flag("no_citations", "warning", "the decision cites no document"))

    # Groundedness (H5 judge)
    groundedness = out.get("groundedness") or {}
    for claim in groundedness.get("unsupported", []):
        flags.append(flag("ungrounded_claims", "critical",
                          f"not supported by FACTS or the cited documents: {claim}"))

    # Parts (P2)
    for number in parts["not_in_inventory"]:
        flags.append(flag("part_not_in_inventory", "critical",
                          f"{number} is not a part of this asset class"))
    for p in parts["parts"]:
        if p["status"] == "out_of_stock":
            flags.append(flag("part_out_of_stock", "warning",
                              f"{p['part_number']} out of stock, available by {p['available_by']}"))

    # Permit (P1)
    if triage["requires_permit"] and triage["permit_type"] is None:
        flags.append(flag("permit_type_unknown", "critical",
                          "a permit is required but its type was not given"))
    if not triage["requires_permit"] and triage["permit_type"] is not None:
        flags.append(flag("permit_type_without_permit", "warning",
                          f"permit_type {triage['permit_type']} given but requires_permit is false"))

    # Technicians (P3)
    if techs["no_qualified_technician"]:
        flags.append(flag("no_qualified_technician", "critical",
                          f"no candidate holds {techs['required_certification']}"))

    # Suspect readings (step 5)
    if facts["suspect_readings"] and not decision["sensor_fault_suspected"]:
        flags.append(flag("suspect_readings_ignored", "warning",
                          f"physically impossible readings {list(facts['suspect_readings'])} "
                          "but no sensor fault suspected"))

    # Trip (step 4 vs LLM)
    code_trip = facts["trip"]["is_trip"]
    if code_trip is not None and decision["is_trip"] is not None and code_trip != decision["is_trip"]:
        flags.append(flag("trip_disagreement", "warning",
                          f"alarm text says is_trip={code_trip}, the LLM says {decision['is_trip']}"))

    # Overconfidence on missing evidence
    gaps = []
    if facts["missing_fields"]:
        gaps.append(f"missing readings {facts['missing_fields']}")
    if facts["telemetry"]["coverage"] == "none":
        gaps.append("no pre-event telemetry")
    if decision["confidence"] == "high" and gaps:
        flags.append(flag("overconfident_on_missing_data", "warning",
                          "confidence high despite " + " and ".join(gaps)))
    return flags


def adjust_confidence(llm_confidence: str, flags: list[dict]) -> str:
    """Confidence after the guards (see the rule above)."""
    if any(f["severity"] == "critical" for f in flags):
        return "low"
    warnings = sum(f["severity"] == "warning" for f in flags)
    level = max(0, CONFIDENCE_LEVELS.index(llm_confidence) - warnings)
    return CONFIDENCE_LEVELS[level]


def guards(out: dict, triage: dict, parts: dict, techs: dict) -> dict:
    """P4 result: flags, confidence before/after, human-review need."""
    flags = run_guards(out, triage, parts, techs)
    llm_conf = out["decision"]["confidence"]
    return {"flags": flags,
            "llm_confidence": llm_conf,
            "final_confidence": adjust_confidence(llm_conf, flags),
            "needs_human_review": any(f["severity"] == "critical" for f in flags)}


# ---------------------------------------------------------------------------
# P5: route + final output
#
# IN SHORT: label the event "auto" (may proceed without a person) or
# "human_review", list EVERY reason that applies, and assemble the final
# record a planner sees.
#   input : out (decision, facts), triage (P1), parts (P2), techs (P3), checks (P4)
#   output: {"route", "route_reasons"} and the final record (final_output)
#
# M5: AUTO_ROUTING_ENABLED = True -> minor issues auto-log, only a flagged
# event (any rule below) pauses the M5 graph for human-approval (interrupt).
# The rules are still evaluated and listed even when a run goes "auto", so a
# reviewer who later opens it still sees why (or why not) it mattered.
#
# Rules (design choices), all evaluated, every one that applies is listed:
#   1. P4 raised a critical flag                         -> human_review
#   2. the LLM itself marked the job requires_permit, safety_critical or
#      priority P1                                       -> human_review
#      (system-design guardrail: code never lets an automated decision through
#       on a job the LLM marked high-risk; no plant rule is copied)
#   3. final confidence (after P4) is "low"              -> human_review
#   4. code saw a trip: the alarm text says trip (step 4) or a reading is at or
#      above its trip limit in asset_classes.json (step 6) -> human_review
#      (catches a tripped machine even if the LLM under-rates it)
#   otherwise -> auto (only when AUTO_ROUTING_ENABLED)
#
# "auto" is only a label today: nothing is created, ordered or assigned.
#
# Final output: the graded fields plus everything a reviewer needs to check
# the decision: route + reasons, confidence, flags, parts, technicians,
# actions, reasoning, citations, and where each field came from.
# ---------------------------------------------------------------------------
AUTO_ROUTING_ENABLED = True           # M5: real conditional routing (was False pre-M5)
HIGH_RISK_PRIORITIES = ("P1",)        # priorities treated as high-risk by rule 2


def route_reasons(out: dict, triage: dict, checks: dict) -> list[str]:
    """Every rule that sends this event to human review."""
    facts = out["facts"]
    reasons = []

    # Rule 1: critical guard flags
    if checks["needs_human_review"]:
        critical = [f["code"] for f in checks["flags"] if f["severity"] == "critical"]
        reasons.append(f"critical guard flags: {critical}")

    # Rule 2: the LLM marked the job high-risk
    risks = []
    if triage["requires_permit"]:
        risks.append("requires a permit")
    if triage["safety_critical"]:
        risks.append("safety-critical")
    if triage["priority"] in HIGH_RISK_PRIORITIES:
        risks.append(f"priority {triage['priority']}")
    if risks:
        reasons.append("high-risk job (LLM): " + ", ".join(risks))

    # Rule 3: low confidence after the guards
    if checks["final_confidence"] == "low":
        reasons.append("final confidence is low")

    # Rule 4: code-detected trip (alarm text or a reading at its trip limit)
    tripped = [f for f, v in facts["readings_check"].items() if v.get("status") == "trip"]
    if facts["trip"]["is_trip"]:
        reasons.append(f"trip in alarm text ({facts['trip']['evidence']})")
    if tripped:
        reasons.append(f"reading at or above trip limit: {tripped}")
    return reasons


def route(out: dict, triage: dict, checks: dict) -> dict:
    """auto / human_review, with every reason that applied."""
    reasons = route_reasons(out, triage, checks)
    if not AUTO_ROUTING_ENABLED:
        reasons = ["auto routing disabled: every event is reviewed"] + reasons
    return {"route": "human_review" if reasons else "auto", "route_reasons": reasons}


def final_output(out: dict, triage: dict, parts: dict, techs: dict, checks: dict,
                 routing: dict) -> dict:
    """The record a planner sees: decision + evidence + route."""
    decision = out["decision"]
    return {
        "record_id": out["record_id"],
        "route": routing["route"],
        "route_reasons": routing["route_reasons"],
        **{k: triage[k] for k in GRADED_FIELDS},
        "permit_type": triage["permit_type"],
        "is_trip": triage["is_trip"],
        "confidence": checks["final_confidence"],
        "llm_confidence": checks["llm_confidence"],
        "flags": checks["flags"],
        "parts": parts["parts"],
        "all_parts_in_stock": parts["all_in_stock"],
        "recommended_technicians": techs["recommended"],
        "required_certification": techs["required_certification"],
        "recommended_actions": decision["recommended_actions"],
        "reasoning": decision["reasoning"],
        "citations": decision["citations"],
        "downtime_cost_per_hour_inr": out["facts"]["downtime"]["cost_per_hour_inr"],
        "sources": triage["sources"],
    }


# ---------------------------------------------------------------------------
# Saving and replaying llm_step output
#
# IN SHORT: P1-P5 need only llm_step's output (decision + facts), so a run can
# be saved once and replayed many times WITHOUT calling the LLM.
#   --save PATH      : run llm_step as normal, then write its output to PATH
#   --from-file PATH : skip llm_step; load its output from PATH instead
#
# Why: while building and testing P1-P5, each run would otherwise cost an
# LLM call (time, quota) and could give a different answer each time.
# Replaying the SAME saved output makes P-step tests repeatable.
#
# The file holds what llm_step.run() returns: record_id, decision,
# invalid_citations, chunks (file/section/pages/score/source) and facts.
# It contains no ground_truth (facts never does); --evaluate re-reads it from
# the intake data, exactly as a live run does.
# ---------------------------------------------------------------------------
def save_output(out: dict, path: Path) -> None:
    """Write llm_step's output to a JSON file (folders created if needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    logger.info("saved llm_step output to %s", path)


def load_output(path: Path) -> dict:
    """Read a saved llm_step output; stop with a clear message if it is not one."""
    if not path.is_file():
        raise SystemExit(f"--from-file: {path} not found")
    out = json.loads(path.read_text())
    missing = [k for k in ("record_id", "decision", "facts") if k not in out]
    if missing:
        raise SystemExit(f"--from-file: {path} is not an llm_step output (missing {missing})")
    llm_step.LLMDecision.model_validate(out["decision"])       # same schema check as a live run
    logger.info("replaying %s (record %s): no LLM call", path, out["record_id"])
    return out


# ---------------------------------------------------------------------------
# Run: llm_step (or a replayed file) -> P1 (P2-P5 added as we build them)
# ---------------------------------------------------------------------------
def run(event_id: str | None = None, evaluate: bool = False,
        from_file: Path | None = None, save: Path | None = None) -> dict:
    if from_file:
        out = load_output(from_file)
        if evaluate:                                             # score the saved decision
            llm_step.evaluate_against_truth(out["record_id"],
                                            llm_step.LLMDecision.model_validate(out["decision"]))
    else:
        out = llm_step.run(event_id, evaluate=evaluate)
        if save:
            save_output(out, save)

    triage = final_triage(out)                                   # P1
    logger.info("P1: %s", {k: triage[k] for k in GRADED_FIELDS})

    parts = parts_check(out)                                     # P2
    logger.info("P2: %d part(s) named, all in stock: %s%s", len(parts["parts"]), parts["all_in_stock"],
                "".join(f"; {p['part_number']}={p['status']}" for p in parts["parts"]))

    techs = technician_filter(out, triage)                       # P3
    logger.info("P3: cert=%s, %d qualified (%d excluded), recommended %s",
                techs["required_certification"], len(techs["qualified"]),
                techs["excluded"]["missing_certification"], techs["recommended"])

    checks = guards(out, triage, parts, techs)                   # P4
    logger.info("P4: %d flag(s) %s, confidence %s -> %s, human review: %s",
                len(checks["flags"]), [f["code"] for f in checks["flags"]],
                checks["llm_confidence"], checks["final_confidence"], checks["needs_human_review"])

    routing = route(out, triage, checks)                         # P5
    logger.info("P5: route=%s, reasons %s", routing["route"], routing["route_reasons"])
    final = final_output(out, triage, parts, techs, checks, routing)

    if not from_file:                                            # M3: live run only, never on replay
        remember(out, triage, checks, routing)

    return {"record_id": out["record_id"], "final": final, "triage": triage, "parts": parts,
            "technicians": techs, "guards": checks,
            "decision": out["decision"], "invalid_citations": out["invalid_citations"]}


# ---------------------------------------------------------------------------
# M3: persistent equipment memory (write side)
#
# IN SHORT: after every LIVE triage, write what happened for this asset to
# equipment memory (memory.py), so a future event on the SAME asset can
# recall it (llm_step.add_equipment_memory, read before L3). Skipped for an
# unmatched asset: there is no equipment to remember history against.
# ---------------------------------------------------------------------------
def remember(out: dict, triage: dict, checks: dict, routing: dict) -> None:
    """Write this triage's outcome to equipment memory."""
    from memory import remember_triage

    asset = out["facts"]["asset"]
    if asset is None:
        logger.info("M3: asset unmatched, nothing to remember")
        return
    remember_triage(record_id=out["record_id"], asset_tag=asset["asset_tag"],
                    received_at=out["facts"]["received_at"], priority=triage["priority"],
                    probable_fault=triage["probable_fault"], safety_critical=triage["safety_critical"],
                    requires_permit=triage["requires_permit"], confidence=checks["final_confidence"],
                    route=routing["route"])


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Final triage for one intake event")
    parser.add_argument("event_id", nargs="?", help="record_id or (unique) event_id")
    parser.add_argument("--evaluate", action="store_true", help="compare with ground truth")
    parser.add_argument("--save", type=Path, metavar="PATH",
                        help="save llm_step's output to PATH (for later --from-file)")
    parser.add_argument("--from-file", type=Path, metavar="PATH",
                        help="replay a saved llm_step output instead of calling the LLM")
    args = parser.parse_args()
    if args.from_file and (args.event_id or args.save):
        parser.error("--from-file replays a saved run: do not also pass an event_id or --save")
    result = run(args.event_id, evaluate=args.evaluate, from_file=args.from_file, save=args.save)
    print(json.dumps(result["final"], indent=2))
