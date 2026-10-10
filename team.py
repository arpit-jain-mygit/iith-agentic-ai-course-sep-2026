"""team.py - M6: the 5-agent team (spec's mandatory components).

  .venv/bin/python team.py PLANTGUARD-00000

  Log Intake Agent            : M1 LLM parse (confidence/conflicts) + L1 facts + M3 recall
  Manual RAG Agent             : M4 hybrid+rerank retrieval (root-cause lookup)
  Maintenance Recommendation   : L3/L4 LLM call + L5 citations + H5 groundedness + P1-P4
    Agent
  Procurement Agent            : NEW - for any part P2 found out-of-stock/below-reorder,
                                  raises a PO via the mcp_server.py ERP tool
  Safety Reviewer Agent        : NEW - for a safety-critical/permit job only, a second
                                  LLM call vets the recommended actions against the CITED
                                  safety documents; a "not safe" verdict is a hard,
                                  critical guard flag (forces human_review)

Every agent above wraps already-tested code from facts.py/llm_step.py/decide.py
except Procurement and Safety Reviewer, which are new for M6. This file is the
ONE place that wires all 5 together and writes the shared M3 equipment memory.
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
    from intake import load_events, parse_event

    lk = F.load_lookups()
    events = load_events()
    event = next((e for e in events if record_id in (e.record_id, e.event_id)), None)
    if event is None:
        raise SystemExit(f"{record_id} not found")

    intake_check = parse_event(lk, event)                         # M1: LLM parse (confidence/conflicts)

    result = F.main(event.record_id)                              # L1: steps 1-13 (authoritative source)
    facts, prompt_facts = result["facts"], result["prompt_facts"]
    prompt_facts = llm_step.add_equipment_memory(prompt_facts)     # M3: this asset's past triages

    logger.info("M6: log intake %s asset_confidence=%s conflicts=%s",
               record_id, intake_check["asset_confidence"], intake_check["conflicts"])
    return {"facts": facts, "prompt_facts": prompt_facts, "intake_check": intake_check}


# ---------------------------------------------------------------------------
# Agent 2: Manual RAG
# ---------------------------------------------------------------------------
@observe(as_type="agent", name="manual_rag_agent")
def manual_rag_agent(prompt_facts: dict) -> list[dict]:
    """M4 hybrid+rerank retrieval: the asset's manual + plant-wide procedures (root-cause lookup)."""
    import llm_step
    return llm_step.retrieve(prompt_facts)


# ---------------------------------------------------------------------------
# Agent 3: Maintenance Recommendation
# ---------------------------------------------------------------------------
@observe(as_type="agent", name="maintenance_recommendation_agent")
def maintenance_recommendation_agent(record_id: str, prompt_facts: dict, chunks: list[dict],
                                     facts: dict) -> dict:
    """L3/L4 LLM call, L5 citation guard, H5 groundedness, then P1-P4 (triage, parts, techs, guards)."""
    import decide as D
    import llm_step

    decision = llm_step.call_llm(llm_step.build_user_prompt(prompt_facts, chunks))
    bad = llm_step.invalid_citations(decision, chunks)
    groundedness = llm_step.check_groundedness(decision, prompt_facts, chunks)

    out = {"record_id": record_id, "decision": decision.model_dump(), "invalid_citations": bad,
           "facts": facts, "groundedness": groundedness}
    triage = D.final_triage(out)                                  # P1
    parts = D.parts_check(out)                                    # P2
    techs = D.technician_filter(out, triage)                      # P3
    checks = D.guards(out, triage, parts, techs)                  # P4
    return {"out": out, "triage": triage, "parts": parts, "technicians": techs, "checks": checks}


# ---------------------------------------------------------------------------
# Agent 4: Procurement (NEW)
#
# IN SHORT: P2 (parts_check) already tells us which named parts are out of
# stock or below reorder; this agent ACTS on that by raising a PO through the
# MCP ERP server for each one. The quantity decision (bring on_hand back up
# to reorder_point) lives here, in code - the tool itself just records
# whatever quantity it is told (see mcp_server.py's docstring).
# ---------------------------------------------------------------------------
@observe(as_type="agent", name="procurement_agent")
def procurement_agent(record_id: str, received_at: str, parts: dict) -> dict:
    """Raise a PO for every named part that needs restocking (idempotent per record_id+part)."""
    from mcp_server import call_tool_sync

    raised = []
    for p in parts["parts"]:
        if p["status"] == "not_in_inventory":                     # can't reorder an unknown part
            continue
        if p["status"] == "out_of_stock" or p["below_reorder"]:
            qty = max(p["reorder_point"] - p["on_hand"], 1)
            po = call_tool_sync("raise_purchase_order", {
                "reference": record_id, "part_number": p["part_number"],
                "quantity": qty, "raised_on": received_at[:10],
            })
            raised.append(po)
            logger.info("M6: procurement raised %s for %s (qty %d)",
                        po.get("po_id"), p["part_number"], qty)
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
    if not (decision["safety_critical"] or decision["requires_permit"]):
        return {"safe_to_proceed": True, "concerns": [], "missing_safety_steps": [], "reviewed": False}

    from llm_step import LLMDecision, call_structured, cited_chunks

    evidence = cited_chunks(LLMDecision.model_validate(decision), chunks)
    prompt = build_safety_review_prompt(decision, evidence)
    review = call_structured(SAFETY_REVIEW_PROMPT, prompt, SafetyReview).model_dump()
    review["reviewed"] = True
    logger.info("M6: safety review safe_to_proceed=%s concerns=%s",
               review["safe_to_proceed"], review["concerns"])
    return review


# ---------------------------------------------------------------------------
# Run the team end to end
# ---------------------------------------------------------------------------
@observe(name="run_team", capture_input=True, capture_output=True)
def run_team(record_id: str) -> dict:
    """Log Intake -> Manual RAG -> Recommendation -> Safety Review -> route -> Procurement."""
    import decide as D

    intake = log_intake_agent(record_id)
    chunks = manual_rag_agent(intake["prompt_facts"])
    rec = maintenance_recommendation_agent(record_id, intake["prompt_facts"], chunks, intake["facts"])

    review = safety_reviewer_agent(rec["out"]["decision"], chunks)
    checks = rec["checks"]
    if review["reviewed"] and not review["safe_to_proceed"]:
        concern = "; ".join(review["concerns"]) or "recommended actions not safe to proceed"
        checks = {**checks,
                 "flags": checks["flags"] + [D.flag("safety_reviewer_blocked", "critical",
                                                    f"safety reviewer: {concern}")],
                 "final_confidence": "low", "needs_human_review": True}

    routing = D.route(rec["out"], rec["triage"], checks)
    final = D.final_output(rec["out"], rec["triage"], rec["parts"], rec["technicians"], checks, routing)

    procurement = procurement_agent(record_id, intake["facts"]["received_at"], rec["parts"])
    D.remember(rec["out"], rec["triage"], checks, routing)         # M3 write

    return {"record_id": record_id, "final": final, "safety_review": review,
            "procurement": procurement, "intake_check": intake["intake_check"]}


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="M6: run the 5-agent team on one event")
    parser.add_argument("record_id", help="record_id or (unique) event_id")
    args = parser.parse_args()
    print(json.dumps(run_team(args.record_id), indent=2))
