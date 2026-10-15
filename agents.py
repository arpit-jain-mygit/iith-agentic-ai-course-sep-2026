"""agents.py - M6: the 5-agent team (spec's mandatory components).

This file simulates a small team of specialists working one maintenance event end
to end, instead of one big function doing everything. Each agent below has ONE job;
splitting it this way is what the spec calls "multi-agent."

All 5 agent FUNCTIONS are defined in THIS file - there is no one-file-per-agent split.
What varies is where each agent's actual LOGIC lives: most agents are thin wrappers
that call into already-tested code in facts.py/llm_step.py/decide.py; only Safety
Reviewer and Procurement's ordering decision are genuinely new code, written here.

  .venv/bin/python agents.py PLANTGUARD-00000

  Log Intake Agent            : log_intake_agent() below. Reads the raw event and
                                 figures out which asset it's about and what's
                                 already known about it. Every other agent depends
                                 on this being right first.
                                 Logic: intake.py:parse_event() (M1 LLM parse) +
                                 facts.py:main() (L1, steps 1-13) +
                                 llm_step.py:add_equipment_memory() (M3 recall).

  Manual RAG Agent             : manual_rag_agent() below. Looks up the relevant
                                 manual/SOP pages for this asset - the evidence the
                                 next agent must base its recommendation on and
                                 cite, instead of guessing from general knowledge.
                                 Logic: llm_step.py:retrieve() (M4 hybrid+rerank).

  Maintenance Recommendation   : maintenance_recommendation_agent() below. Decides
    Agent                        what's wrong and what to do, using ONLY the
                                 retrieved pages as evidence, then checks its own
                                 citations are real and its claims are backed by
                                 the text - so it can't just sound plausible.
                                 Logic: llm_step.py:call_llm()/build_user_prompt()/
                                 invalid_citations() (L3-L5) + check_groundedness()
                                 (H5) + decide.py:final_triage()/parts_check()/
                                 technician_filter()/guards() (P1-P4).

  Safety Reviewer Agent        : safety_reviewer_agent() below - NEW, logic lives
                                 HERE in agents.py (not a wrapper). A second,
                                 independent LLM call whose only job is to catch
                                 an unsafe recommendation before anyone acts on it
                                 (e.g. it forgot lockout/tagout or a required
                                 permit). Exists because the agent above optimizes
                                 for a correct diagnosis, not safety - so safety
                                 gets its own dedicated check. A "not safe" verdict
                                 is a hard, critical guard flag (forces
                                 human_review), using only llm_step.py:
                                 call_structured()/cited_chunks() as plumbing.

  Procurement Agent            : procurement_agent() below - NEW, the ordering
                                 decision (which part, what quantity) lives HERE;
                                 for any part found out-of-stock/below-reorder, it
                                 raises a PO via mcp_server.py:call_tool_sync()
                                 (the ERP tool). Only runs if route == "auto" - we
                                 never want to auto-spend money on an event a human
                                 still needs to sign off on.

run_team() below is the ORCHESTRATOR: it calls the 5 agents in order, pipes each
one's output into the next's input, applies decide.py's routing (D.route/
D.final_output), gates Procurement on route=="auto", and writes the shared M3
equipment memory via D.remember() - so the next event on this asset benefits from
what happened here.
"""
import json
import logging

from pydantic import BaseModel

from tracing import observe

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent 1: Log Intake
# ---------------------------------------------------------------------------
@observe(as_type="agent", name="log_intake_agent")
def log_intake_agent(record_id: str) -> dict:
    """M1 LLM parse (confidence/conflicts, cross-checked against the registry) +
    L1 deterministic facts (authoritative) + M3 equipment memory."""
    import facts as F
    import llm_step
    from intake import PARSE_PROMPT, load_events, parse_event

    lk = F.load_lookups()
    events = load_events()
    event = next((e for e in events if record_id in (e.record_id, e.event_id)), None)
    if event is None:
        raise SystemExit(f"{record_id} not found")

    logger.info("***STEP 1.1 (LLM)*** M1 LLM parse | PROMPT: %r", PARSE_PROMPT.splitlines()[0])
    logger.info("***STEP 1.1 (LLM)*** M1 LLM parse | IN:  raw_text=%r", event.raw_text[:80])
    intake_check = parse_event(lk, event)                         # M1: LLM parse (confidence/conflicts)
    logger.info("***STEP 1.1 (LLM)*** M1 LLM parse | OUT: asset_tag=%s asset_confidence=%s conflicts=%s "
               "-> cross-checked raw_text against the asset registry",
               intake_check["asset_tag"], intake_check["asset_confidence"], intake_check["conflicts"])

    logger.info("***STEP 1.2 (non-LLM)*** L1 facts build | IN:  event.record_id=%s", event.record_id)
    result = F.main(event.record_id)                              # L1: steps 1-13 (authoritative source)
    facts, prompt_facts = result["facts"], result["prompt_facts"]
    logger.info("***STEP 1.2 (non-LLM)*** L1 facts build | OUT: queried 12 lookup tables (asset/telemetry/work "
               "orders/inventory/techs/PDF tables) -> facts (%d chars) compressed to prompt_facts (%d chars)",
               len(json.dumps(facts)), len(json.dumps(prompt_facts)))

    logger.info("***STEP 1.3 (non-LLM)*** M3 memory recall | IN:  asset_tag=%s", intake_check["asset_tag"])
    prompt_facts = llm_step.add_equipment_memory(prompt_facts)     # M3: this asset's past triages
    logger.info("***STEP 1.3 (non-LLM)*** M3 memory recall | OUT: semantic search over this asset's past triages "
               "in Qdrant -> %d past triage(s) recalled, added to prompt_facts.equipment_memory",
               len(prompt_facts.get("equipment_memory", [])))

    return {"facts": facts, "prompt_facts": prompt_facts, "intake_check": intake_check}


# ---------------------------------------------------------------------------
# Agent 2: Manual RAG
# ---------------------------------------------------------------------------
@observe(as_type="agent", name="manual_rag_agent")
def manual_rag_agent(prompt_facts: dict) -> list[dict]:
    """M4 hybrid+rerank retrieval: the asset's manual + plant-wide procedures (root-cause lookup)."""
    import llm_step
    from rag_common import RERANK_PROMPT

    code = (prompt_facts["asset"] or {}).get("asset_code") or prompt_facts["event"]["asset_code"]
    logger.info("***STEP 2.1 (LLM)*** M4 hybrid+rerank retrieve | PROMPT (H3 rerank stage, one candidate "
               "list per source): %r", RERANK_PROMPT.splitlines()[0])
    logger.info("***STEP 2.1 (LLM)*** M4 hybrid+rerank retrieve | IN:  asset_code=%s", code)
    chunks = llm_step.retrieve(prompt_facts)
    logger.info("***STEP 2.1 (LLM)*** M4 hybrid+rerank retrieve | OUT: embed query -> dense+keyword hybrid "
               "fuse (asset manual source + plant-wide source, RRF-ranked) -> LLM rerank -> "
               "%d chunk(s) kept", len(chunks))
    return chunks


# ---------------------------------------------------------------------------
# Agent 3: Maintenance Recommendation
# ---------------------------------------------------------------------------
@observe(as_type="agent", name="maintenance_recommendation_agent")
def maintenance_recommendation_agent(record_id: str, prompt_facts: dict, chunks: list[dict],
                                     facts: dict) -> dict:
    """L3/L4 LLM call, L5 citation guard, H5 groundedness, then P1-P4 (triage, parts, techs, guards)."""
    import decide as D
    import llm_step

    user_prompt = llm_step.build_user_prompt(prompt_facts, chunks)
    logger.info("***STEP 3.1 (LLM)*** L3/L4 LLM decision | PROMPT: system=%r | user=%d chars "
               "(FACTS block + %d numbered DOCUMENTS)",
               llm_step.SYSTEM_PROMPT.splitlines()[0], len(user_prompt), len(chunks))
    logger.info("***STEP 3.1 (LLM)*** L3/L4 LLM decision | IN:  %d chunk(s) as evidence", len(chunks))
    decision = llm_step.call_llm(user_prompt)
    logger.info("***STEP 3.1 (LLM)*** L3/L4 LLM decision | OUT: priority=%s probable_fault=%r citations=%d",
               decision.priority, decision.probable_fault[:60], len(decision.citations))

    logger.info("***STEP 3.2 (non-LLM)*** L5 citation guard | IN:  %d citation(s) to verify against retrieved chunks",
               len(decision.citations))
    bad = llm_step.invalid_citations(decision, chunks)
    logger.info("***STEP 3.2 (non-LLM)*** L5 citation guard | OUT: %d invalid citation(s) (cited a file/section "
               "never retrieved)", len(bad))

    logger.info("***STEP 3.3 (LLM)*** H5 groundedness judge | PROMPT: %r", llm_step.JUDGE_PROMPT.splitlines()[0])
    logger.info("***STEP 3.3 (LLM)*** H5 groundedness judge | IN:  decision's claims + %d chunk(s)", len(chunks))
    groundedness = llm_step.check_groundedness(decision, prompt_facts, chunks)
    logger.info("***STEP 3.3 (LLM)*** H5 groundedness judge | OUT: a second LLM call checks each claim against "
               "FACTS/cited chunks -> score=%s (%s/%s supported)",
               groundedness["score"], groundedness["checked"] - len(groundedness["unsupported"]),
               groundedness["checked"])

    out = {"record_id": record_id, "decision": decision.model_dump(), "invalid_citations": bad,
           "facts": facts, "groundedness": groundedness}

    logger.info("***STEP 3.4 (non-LLM)*** P1 final triage | IN:  decision + facts")
    triage = D.final_triage(out)                                  # P1
    logger.info("***STEP 3.4 (non-LLM)*** P1 final triage | OUT: each field taken from its authoritative source "
               "(facts where code-computed, else llm) -> priority=%s is_trip=%s",
               triage["priority"], triage["is_trip"])

    logger.info("***STEP 3.5 (non-LLM)*** P2 parts check | IN:  fault_parts=%s", out["decision"]["fault_parts"])
    parts = D.parts_check(out)                                    # P2
    logger.info("***STEP 3.5 (non-LLM)*** P2 parts check | OUT: looked up each named part in inventory as of the "
               "event date -> all_in_stock=%s not_in_inventory=%s",
               parts["all_in_stock"], parts["not_in_inventory"])

    logger.info("***STEP 3.6 (non-LLM)*** P3 technician filter | IN:  required_certification for permit_type=%s",
               triage["permit_type"])
    techs = D.technician_filter(out, triage)                      # P3
    logger.info("***STEP 3.6 (non-LLM)*** P3 technician filter | OUT: filtered the ranked candidate pool to those "
               "certified, available-first -> recommended=%s", techs["recommended"])

    logger.info("***STEP 3.7 (non-LLM)*** P4 guards | IN:  decision + triage + parts + techs, cross-checked for "
               "contradictions")
    checks = D.guards(out, triage, parts, techs)                  # P4
    logger.info("***STEP 3.7 (non-LLM)*** P4 guards | OUT: flags=%s llm_confidence=%s -> final_confidence=%s",
               [f["code"] for f in checks["flags"]], checks["llm_confidence"], checks["final_confidence"])

    return {"out": out, "triage": triage, "parts": parts, "technicians": techs, "checks": checks}


# ---------------------------------------------------------------------------
# Agent 4: Procurement (NEW)
#
# IN SHORT: P2 (parts_check) ran earlier in the pipeline and already flagged
# which named parts are out of stock or below reorder; this agent re-verifies
# each candidate against LIVE stock via the check_stock MCP tool before
# spending money, since P2's view is a snapshot and this is the one agent
# that actually commits a side effect (raising a PO). The quantity decision
# (bring on_hand back up to reorder_point) lives here, in code - the
# raise_purchase_order tool itself just records whatever quantity it is told
# (see mcp_server.py's docstring).
# ---------------------------------------------------------------------------
@observe(as_type="agent", name="procurement_agent")
def procurement_agent(record_id: str, received_at: str, parts: dict,
                      asset_tag: str, asset_code: str) -> dict:
    """Raise a PO for every named part that still needs restocking after a live
    check_stock re-verification (idempotent per record_id+part)."""
    from mcp_server import call_tool_sync

    logger.info("***STEP 6.1 (non-LLM)*** evaluate parts (P2 snapshot) | IN:  %s",
               [(p["part_number"], p["status"], p["below_reorder"]) for p in parts["parts"]])
    candidates = [p for p in parts["parts"] if p["status"] != "not_in_inventory"
                 and (p["status"] == "out_of_stock" or p["below_reorder"])]
    logger.info("***STEP 6.1 (non-LLM)*** evaluate parts (P2 snapshot) | OUT: %d of %d part(s) are "
               "reorder candidates", len(candidates), len(parts["parts"]))

    raised = []
    for p in candidates:
        logger.info("***STEP 6.2 (non-LLM)*** check_stock re-verify | IN:  part=%s asset_tag=%s "
                   "(P2 snapshot had on_hand=%s reorder_point=%s)",
                   p["part_number"], asset_tag, p["on_hand"], p["reorder_point"])
        live = call_tool_sync("check_stock", {
            "asset_tag": asset_tag, "asset_code": asset_code,
            "received_at": received_at, "part_numbers": [p["part_number"]],
        })
        live_part = next((lp for lp in live["parts"] if lp["part_number"] == p["part_number"]), None)
        if live_part is None:
            logger.info("***STEP 6.2 (non-LLM)*** check_stock re-verify | OUT: part not found live, "
                       "skipping")
            continue
        logger.info("***STEP 6.2 (non-LLM)*** check_stock re-verify | OUT: on_hand=%s reorder_point=%s "
                   "out_of_stock=%s below_reorder=%s", live_part["on_hand"], live_part["reorder_point"],
                   live_part["out_of_stock"], live_part["below_reorder"])

        if not live_part["out_of_stock"] and not live_part["below_reorder"]:
            logger.info("***STEP 6.3 (non-LLM)*** raise PO | SKIPPED: stock changed since triage, "
                       "%s no longer needs reordering", p["part_number"])
            continue

        qty = max(live_part["reorder_point"] - live_part["on_hand"], 1)   # bring on_hand back up to reorder_point
        po = call_tool_sync("raise_purchase_order", {
            "reference": record_id, "part_number": p["part_number"],
            "quantity": qty, "raised_on": received_at[:10],
        })
        raised.append(po)
        logger.info("***STEP 6.3 (non-LLM)*** raise PO | IN:  part=%s on_hand=%s reorder_point=%s -> qty=%d "
                   "| OUT: po_id=%s (idempotent on record_id+part_number)",
                   p["part_number"], live_part["on_hand"], live_part["reorder_point"], qty, po.get("po_id"))
    return {"purchase_orders_raised": raised}


# ---------------------------------------------------------------------------
# Agent 5: Safety Reviewer (NEW)
#
# IN SHORT: a SECOND, narrower LLM call than the main recommendation - it
# does not re-judge the diagnosis, only whether the recommended actions
# properly account for lockout/permit requirements, using ONLY the cited
# safety documents as evidence. Skipped (auto-pass, no LLM call) for a job
# that is neither safety-critical nor permit-required: nothing to review.
# A "not safe" verdict is a hard, critical guard (forces human_review),
# separate from H5 (which checks factual grounding, not safety soundness).
# ---------------------------------------------------------------------------
SAFETY_REVIEW_PROMPT = """You are a safety reviewer for a manufacturing plant's maintenance
recommendations. You check ONLY whether a safety-critical or permit-required job's
recommended actions properly account for lockout/tagout and permit requirements - you do
not re-judge the diagnosis itself.

Rules:
- Use ONLY the DOCUMENTS given as evidence; do not use outside knowledge of safety practice.
- safe_to_proceed is false if the recommended actions could let someone work on hazardous
  energy without isolation, or skip a permit the documents say is required.
- List any concern plainly, and any safety step the documents require that the recommended
  actions do not mention.
- Return JSON matching the schema exactly."""


class SafetyReview(BaseModel):
    safe_to_proceed: bool
    concerns: list[str]
    missing_safety_steps: list[str]


def build_safety_review_prompt(decision: dict, evidence_chunks: list[dict]) -> str:
    docs_block = "\n\n".join(
        f"[{i}] file: {c['file']} | section: {c['section']}\n{c['text']}"
        for i, c in enumerate(evidence_chunks, start=1)) or "(no cited documents)"
    recommendation = json.dumps({
        "safety_critical": decision["safety_critical"], "requires_permit": decision["requires_permit"],
        "permit_type": decision["permit_type"], "recommended_actions": decision["recommended_actions"],
    }, indent=1)
    return f"RECOMMENDATION:\n{recommendation}\n\nDOCUMENTS:\n{docs_block}"


@observe(as_type="agent", name="safety_reviewer_agent")
def safety_reviewer_agent(decision: dict, chunks: list[dict]) -> dict:
    """Vets a safety-critical/permit job's actions against the cited safety documents."""
    logger.info("***STEP 4.1 (non-LLM)*** gate check | IN:  safety_critical=%s requires_permit=%s",
               decision["safety_critical"], decision["requires_permit"])
    if not (decision["safety_critical"] or decision["requires_permit"]):
        logger.info("***STEP 4.1 (non-LLM)*** gate check | OUT: neither applies -> skip LLM call, auto-pass")
        return {"safe_to_proceed": True, "concerns": [], "missing_safety_steps": [], "reviewed": False}
    logger.info("***STEP 4.1 (non-LLM)*** gate check | OUT: at least one applies -> review fires")

    from llm_step import LLMDecision, call_structured, cited_chunks

    logger.info("***STEP 4.2 (non-LLM)*** gather cited evidence | IN:  %d retrieved chunk(s)", len(chunks))
    evidence = cited_chunks(LLMDecision.model_validate(decision), chunks)
    logger.info("***STEP 4.2 (non-LLM)*** gather cited evidence | OUT: keep only the %d chunk(s) the main decision "
               "actually cited -> this LLM sees ONLY those, not the full retrieved set", len(evidence))

    prompt = build_safety_review_prompt(decision, evidence)
    logger.info("***STEP 4.3 (LLM)*** LLM safety vet | PROMPT: system=%r | user=%d chars "
               "(recommendation + %d cited doc(s) as evidence)",
               SAFETY_REVIEW_PROMPT.splitlines()[0], len(prompt), len(evidence))
    logger.info("***STEP 4.3 (LLM)*** LLM safety vet | IN:  recommended_actions=%s", decision["recommended_actions"])
    review = call_structured(SAFETY_REVIEW_PROMPT, prompt, SafetyReview).model_dump()
    review["reviewed"] = True
    logger.info("***STEP 4.3 (LLM)*** LLM safety vet | OUT: checked actions against cited evidence only -> "
               "safe_to_proceed=%s concerns=%s", review["safe_to_proceed"], review["concerns"])
    return review


# ---------------------------------------------------------------------------
# Run the team end to end
# ---------------------------------------------------------------------------
@observe(name="run_team", capture_input=True, capture_output=True)
def run_team(record_id: str) -> dict:
    """Log Intake -> Manual RAG -> Recommendation -> Safety Review -> route -> Procurement."""
    import decide as D

    logger.info("***STEP 0 (non-LLM)*** run_team START | IN:  record_id=%s", record_id)

    logger.info("***STEP 1 (LLM)*** AGENT 1 Log Intake | IN:  record_id=%s", record_id)
    intake = log_intake_agent(record_id)
    ic = intake["intake_check"]
    logger.info("***STEP 1 (LLM)*** AGENT 1 Log Intake | OUT: asset_tag=%s asset_code=%s "
               "asset_confidence=%s conflicts=%s missing_fields=%s symptoms=%s",
               ic["asset_tag"], ic["asset_code"], ic["asset_confidence"], ic["conflicts"],
               ic["missing_fields"], ic["symptoms"])

    logger.info("***STEP 2 (LLM)*** AGENT 2 Manual/SOP RAG | IN:  asset_code=%s", ic["asset_code"])
    chunks = manual_rag_agent(intake["prompt_facts"])
    logger.info("***STEP 2 (LLM)*** AGENT 2 Manual/SOP RAG | OUT: %d chunk(s): %s", len(chunks),
               "; ".join(f"{c['file']} | {c['section']}" for c in chunks))

    logger.info("***STEP 3 (LLM)*** AGENT 3 Maintenance Recommendation | IN:  %d chunk(s), asset_code=%s",
               len(chunks), ic["asset_code"])
    rec = maintenance_recommendation_agent(record_id, intake["prompt_facts"], chunks, intake["facts"])
    logger.info("***STEP 3 (LLM)*** AGENT 3 Maintenance Recommendation | OUT: priority=%s probable_fault=%r "
               "safety_critical=%s requires_permit=%s groundedness=%s all_parts_in_stock=%s "
               "recommended_technicians=%s",
               rec["triage"]["priority"], rec["triage"]["probable_fault"][:80],
               rec["triage"]["safety_critical"], rec["triage"]["requires_permit"],
               rec["out"]["groundedness"], rec["parts"]["all_in_stock"],
               rec["technicians"]["recommended"])

    logger.info("***STEP 4 (LLM)*** AGENT 4 Safety Reviewer | IN:  safety_critical=%s requires_permit=%s "
               "recommended_actions=%s", rec["triage"]["safety_critical"], rec["triage"]["requires_permit"],
               rec["out"]["decision"]["recommended_actions"])
    review = safety_reviewer_agent(rec["out"]["decision"], chunks)
    logger.info("***STEP 4 (LLM)*** AGENT 4 Safety Reviewer | OUT: reviewed=%s safe_to_proceed=%s concerns=%s",
               review["reviewed"], review["safe_to_proceed"], review["concerns"])
    checks = rec["checks"]
    if review["reviewed"] and not review["safe_to_proceed"]:
        concern = "; ".join(review["concerns"]) or "recommended actions not safe to proceed"
        checks = {**checks,
                 "flags": checks["flags"] + [D.flag("safety_reviewer_blocked", "critical",
                                                    f"safety reviewer: {concern}")],
                 "final_confidence": "low", "needs_human_review": True}

    logger.info("***STEP 5.1 (non-LLM)*** apply 4 routing rules | IN:  flags=%s needs_human_review=%s "
               "triage(requires_permit=%s safety_critical=%s priority=%s) final_confidence=%s",
               [f["code"] for f in checks["flags"]], checks["needs_human_review"],
               rec["triage"]["requires_permit"], rec["triage"]["safety_critical"],
               rec["triage"]["priority"], checks["final_confidence"])
    routing = D.route(rec["out"], rec["triage"], checks)
    final = D.final_output(rec["out"], rec["triage"], rec["parts"], rec["technicians"], checks, routing)
    logger.info("***STEP 5.1 (non-LLM)*** apply 4 routing rules | OUT: rule1 critical-flags / rule2 high-risk-LLM-job "
               "/ rule3 low-confidence / rule4 code-detected-trip -> any reason -> human_review, else "
               "auto -> route=%s because %s", routing["route"], routing["route_reasons"])

    # M8 guardrail: never auto-execute a side effect (raising a PO) on an event
    # flagged for human review - that is exactly the unsigned-off auto-action
    # the spec hard-blocks. Only "auto" (nothing flagged it) reaches procurement.
    logger.info("***STEP 6 (non-LLM)*** AGENT 5 Procurement | IN:  route=%s parts=%s", routing["route"],
               [p["part_number"] for p in rec["parts"]["parts"]])
    if routing["route"] == "auto":
        procurement = procurement_agent(record_id, intake["facts"]["received_at"], rec["parts"],
                                        ic["asset_tag"], ic["asset_code"])
        logger.info("***STEP 6 (non-LLM)*** AGENT 5 Procurement | OUT: purchase_orders_raised=%s",
                   [po.get("po_id") for po in procurement["purchase_orders_raised"]])
    else:
        procurement = {"purchase_orders_raised": [],
                       "withheld_reason": "route is human_review: procurement withheld pending sign-off"}
        logger.info("***STEP 6 (non-LLM)*** AGENT 5 Procurement | OUT: SKIPPED withheld_reason=%s",
                   procurement["withheld_reason"])

    logger.info("***STEP 7.1 (non-LLM)*** M3 memory write | IN:  asset_tag=%s priority=%s probable_fault=%r route=%s",
               ic["asset_tag"], rec["triage"]["priority"], rec["triage"]["probable_fault"][:60],
               routing["route"])
    D.remember(rec["out"], rec["triage"], checks, routing)         # M3 write
    logger.info("***STEP 7.1 (non-LLM)*** M3 memory write | OUT: built one-line summary -> embedded -> upserted to "
               "Qdrant equipment_memory (see 'MEM: remembered' line above for the exact text)")

    logger.info("***STEP 8 (non-LLM)*** run_team END | OUT: record_id=%s route=%s", record_id, routing["route"])

    return {"record_id": record_id, "final": final, "safety_review": review,
            "procurement": procurement, "intake_check": intake["intake_check"]}


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="M6: run the 5-agent team on one event")
    parser.add_argument("record_id", help="record_id or (unique) event_id")
    args = parser.parse_args()
    print(json.dumps(run_team(args.record_id), indent=2))
