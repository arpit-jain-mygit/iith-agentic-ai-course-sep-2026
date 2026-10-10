"""graph.py - M5: orchestrated LangGraph workflow with checkpointing.

  .venv/bin/python graph.py PLANTGUARD-00000              # run until a pause (or the end)
  .venv/bin/python graph.py PLANTGUARD-00000 --approve     # resume a paused run, approved
  .venv/bin/python graph.py PLANTGUARD-00000 --reject      # resume a paused run, rejected

Spec: "alert intake -> root-cause lookup -> recommendation -> conditional
routing (auto-log minor issues, human-approval interrupt for any
safety-critical recommendation), with checkpointing."

Every node below WRAPS an existing, already-tested function (facts.py,
llm_step.py, decide.py) - this file adds graph state, checkpointing and the
interrupt; it does not re-implement any triage logic.

  intake    : facts.main() (L1, steps 1-13) + M3 equipment-memory recall
  lookup    : llm_step.retrieve() (L2)                        "root-cause lookup"
  recommend : llm_step.call_llm() (L3/L4) + L5 citation guard + H5 groundedness
              + decide.py P1-P4 (triage, parts, technicians, guards)
  route     : decide.py P5 (route + final_output)
  auto_log / approval : the conditional branch on route["route"]
              - "auto"         -> auto_log: no interrupt, logged straight away
              - "human_review" -> approval: interrupt() pauses here; the run
                                  resumes only with --approve / --reject

State is checkpointed (SqliteSaver) under thread_id = record_id, so a run
that pauses for approval can be resumed later (possibly hours/days, in a
different process) without re-doing facts/retrieval/the LLM call.
"""
import json
import logging
import sqlite3
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

import decide as D
import facts as F
import llm_step

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
CHECKPOINT_DB = HERE / "checkpoints.db"


# ---------------------------------------------------------------------------
# State: everything a node reads or writes, across the whole run
# ---------------------------------------------------------------------------
class TriageState(TypedDict, total=False):
    record_id: str
    facts: dict
    prompt_facts: dict
    chunks: list
    decision: dict
    invalid_citations: list
    groundedness: dict
    triage: dict
    parts: dict
    technicians: dict
    guards: dict
    routing: dict
    final: dict


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
def intake_node(state: TriageState) -> dict:
    """Alert intake: L1 facts + M3 equipment memory."""
    result = F.main(state["record_id"])
    facts, prompt_facts = result["facts"], result["prompt_facts"]
    prompt_facts = llm_step.add_equipment_memory(prompt_facts)
    return {"facts": facts, "prompt_facts": prompt_facts}


def lookup_node(state: TriageState) -> dict:
    """Root-cause lookup: L2 retrieve (manual + plant-wide chunks)."""
    chunks = llm_step.retrieve(state["prompt_facts"])
    return {"chunks": chunks}


def recommend_node(state: TriageState) -> dict:
    """Recommendation: L3/L4 LLM call, L5 citations, H5 groundedness, P1-P4."""
    decision = llm_step.call_llm(llm_step.build_user_prompt(state["prompt_facts"], state["chunks"]))
    bad = llm_step.invalid_citations(decision, state["chunks"])
    groundedness = llm_step.check_groundedness(decision, state["prompt_facts"], state["chunks"])

    out = {"record_id": state["record_id"], "decision": decision.model_dump(),
           "invalid_citations": bad, "facts": state["facts"], "groundedness": groundedness}
    triage = D.final_triage(out)                                   # P1
    parts = D.parts_check(out)                                     # P2
    techs = D.technician_filter(out, triage)                       # P3
    checks = D.guards(out, triage, parts, techs)                   # P4
    return {"decision": out["decision"], "invalid_citations": bad, "groundedness": groundedness,
            "triage": triage, "parts": parts, "technicians": techs, "guards": checks}


def route_node(state: TriageState) -> dict:
    """P5: route + the final record."""
    out = {"record_id": state["record_id"], "decision": state["decision"],
           "facts": state["facts"], "invalid_citations": state["invalid_citations"]}
    routing = D.route(out, state["triage"], state["guards"])
    final = D.final_output(out, state["triage"], state["parts"], state["technicians"],
                           state["guards"], routing)
    return {"routing": routing, "final": final}


def route_branch(state: TriageState) -> str:
    """Conditional edge: auto-log minor issues, interrupt for everything else."""
    return "auto_log" if state["routing"]["route"] == "auto" else "approval"


def _remember(state: TriageState) -> None:
    """M3 write, shared by both branches below (decide.py already guards an unmatched asset)."""
    out = {"record_id": state["record_id"], "facts": state["facts"]}
    D.remember(out, state["triage"], state["guards"], state["routing"])


def auto_log_node(state: TriageState) -> dict:
    """Minor issue: logged automatically, no human pause."""
    _remember(state)
    logger.info("M5: %s auto-logged (no interrupt)", state["record_id"])
    return {"final": {**state["final"], "approved": True}}


def approval_node(state: TriageState) -> dict:
    """Safety-critical / flagged: pause for a human, resume with approve or reject."""
    answer = interrupt({"record_id": state["record_id"],
                        "route_reasons": state["final"]["route_reasons"],
                        "priority": state["triage"]["priority"],
                        "probable_fault": state["triage"]["probable_fault"],
                        "safety_critical": state["triage"]["safety_critical"]})
    _remember(state)
    return {"final": {**state["final"], "approved": answer == "approve"}}


# ---------------------------------------------------------------------------
# Build + compile (checkpointed)
# ---------------------------------------------------------------------------
def build_app():
    g = StateGraph(TriageState)
    g.add_node("intake", intake_node)
    g.add_node("lookup", lookup_node)
    g.add_node("recommend", recommend_node)
    g.add_node("route", route_node)
    g.add_node("auto_log", auto_log_node)
    g.add_node("approval", approval_node)

    g.add_edge(START, "intake")
    g.add_edge("intake", "lookup")
    g.add_edge("lookup", "recommend")
    g.add_edge("recommend", "route")
    g.add_conditional_edges("route", route_branch, {"auto_log": "auto_log", "approval": "approval"})
    g.add_edge("auto_log", END)
    g.add_edge("approval", END)

    conn = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))


# ---------------------------------------------------------------------------
# Run: resumable by thread_id = record_id
# ---------------------------------------------------------------------------
def _pending_interrupt(record_id: str, state) -> dict:
    return {"record_id": record_id, "paused": True, "interrupt": state.interrupts[0].value}


def run(record_id: str, resume: str | None = None) -> dict | None:
    app = build_app()
    config = {"configurable": {"thread_id": record_id}}
    state = app.get_state(config)

    if state.next:                                   # a prior run is paused here
        if resume is None:
            logger.info("M5: %s is paused for approval; resume with --approve or --reject", record_id)
            print(json.dumps(_pending_interrupt(record_id, state), indent=2))
            return None
        result = app.invoke(Command(resume=resume), config)
    else:                                             # fresh run
        result = app.invoke({"record_id": record_id}, config)

    state = app.get_state(config)
    if state.next:                                    # just paused (fresh run hit the interrupt)
        print(json.dumps(_pending_interrupt(record_id, state), indent=2))
        return None

    print(json.dumps(result["final"], indent=2))
    return result["final"]


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="M5: LangGraph triage workflow with checkpointing")
    parser.add_argument("record_id", help="record_id or (unique) event_id")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--approve", action="store_const", dest="resume", const="approve")
    group.add_argument("--reject", action="store_const", dest="resume", const="reject")
    args = parser.parse_args()
    run(args.record_id, resume=args.resume)
