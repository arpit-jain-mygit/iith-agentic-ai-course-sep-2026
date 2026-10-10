"""api.py - M8: FastAPI packaging.

  .venv/bin/uvicorn api:app --reload
  open http://127.0.0.1:8000/docs for the interactive API, or /status for
  the dashboard.

Endpoints:
  POST /triage/{record_id}   run the M6 5-agent team on one event
  POST /ask                  free-text Q&A over the manuals (qa.py)
  GET  /status                status dashboard: circuit breakers, equipment
                               memory size, POs raised, Qdrant connectivity
"""
import json
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="PlantGuard",
             description="Predictive maintenance triage, Q&A and status dashboard.")


class AskRequest(BaseModel):
    question: str


@app.post("/triage/{record_id}")
def triage(record_id: str) -> dict:
    """Run the full 5-agent team (Log Intake -> Manual RAG -> Recommendation ->
    Safety Review -> Procurement) on one intake event."""
    from team import run_team
    try:
        return run_team(record_id)
    except SystemExit as e:                               # facts.main's "not found" path
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    """Free-text Q&A over the manuals, with the M8 guardrail/route classification."""
    from qa import answer_question
    return answer_question(req.question)


@app.get("/status")
def status() -> dict:
    """Dashboard: is the system healthy, and what has it done so far."""
    from mcp_server import PROCUREMENT_LOG
    from memory import MEMORY_COLLECTION
    from rag_common import get_client
    from reliability import all_breaker_status

    try:
        client = get_client()
        has_memory = client.collection_exists(MEMORY_COLLECTION)
        memory_count = client.get_collection(MEMORY_COLLECTION).points_count if has_memory else 0
        qdrant_ok = True
    except Exception as e:
        logger.warning("STATUS: Qdrant unreachable (%s: %s)", type(e).__name__, e)
        qdrant_ok, memory_count = False, None

    pos_raised = len(json.loads(PROCUREMENT_LOG.read_text())) if PROCUREMENT_LOG.exists() else 0
    breakers = all_breaker_status()

    return {
        "status": "ok" if qdrant_ok and not any(b["open"] for b in breakers) else "degraded",
        "qdrant_connected": qdrant_ok,
        "equipment_memories_stored": memory_count,
        "purchase_orders_raised": pos_raised,
        "circuit_breakers": breakers,
    }
