"""memory.py - M3: persistent memory of equipment maintenance history.

IN SHORT: facts.py step 9 (get_history) already gives an asset's work-order
history, but that is PRE-GENERATED mock data, fixed when the dataset was
built. This module is different: it is what the SYSTEM ITSELF writes after
every LIVE triage, so a fault pattern that only emerges ACROSS triage runs
becomes visible, even though no mock work order will ever record it.

  remember_triage(...)                                   : write one triage
                                                            outcome (decide.py,
                                                            after P5)
  recall_equipment_history(asset_tag, query, k)          : this asset's past
                                                            triages, closest to
                                                            `query` first (read,
                                                            before L3 prompt)

Its own Qdrant collection, never mixed with the manual/SOP chunks in
rag_common.COLLECTION: same embedding model (rag_common.embed), so a new
event's text can be matched against a past summary by MEANING ("high
vibration" recalls a past "excess vibration trip" case), not exact wording.
"""
import logging
import uuid

from rag_common import embed, get_client

logger = logging.getLogger(__name__)

MEMORY_COLLECTION = "plantguard_equipment_memory"
RECALL_LIMIT = 5      # past triages surfaced per event (design choice, matches facts.py step 9)


def _memory_id(record_id: str) -> str:
    """Stable id from record_id (same uuid5 scheme as rag_ingest.py's chunk_id):
    re-running a triage for the same record overwrites its memory, never duplicates it."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, record_id))


def ensure_collection(client, dim: int) -> None:
    """Create the equipment-memory collection (+ its asset_tag filter index) if not there yet."""
    from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

    if not client.collection_exists(MEMORY_COLLECTION):
        client.create_collection(MEMORY_COLLECTION,
                                 vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
        client.create_payload_index(MEMORY_COLLECTION, "asset_tag", PayloadSchemaType.KEYWORD)
        logger.info("MEM: created collection %s (dim=%d)", MEMORY_COLLECTION, dim)


def summary_text(asset_tag: str, received_at: str, priority: str, probable_fault: str, route: str) -> str:
    """One line describing this triage outcome; embedded so a future event can recall it by meaning."""
    return f"{asset_tag} on {received_at[:10]}: {probable_fault} (priority {priority}, route {route})"


# ---------------------------------------------------------------------------
# Write: one triage outcome -> one point (called by decide.py after P5)
# ---------------------------------------------------------------------------
def remember_triage(record_id: str, asset_tag: str, received_at: str, priority: str,
                    probable_fault: str, safety_critical: bool, requires_permit: bool,
                    confidence: str, route: str) -> None:
    """Write one triage outcome to equipment memory."""
    from qdrant_client.models import PointStruct

    client = get_client()
    text = summary_text(asset_tag, received_at, priority, probable_fault, route)
    vector = embed([text])[0]
    ensure_collection(client, len(vector))
    client.upsert(MEMORY_COLLECTION, points=[PointStruct(id=_memory_id(record_id), vector=vector, payload={
        "record_id": record_id, "asset_tag": asset_tag, "received_at": received_at,
        "priority": priority, "probable_fault": probable_fault, "safety_critical": safety_critical,
        "requires_permit": requires_permit, "confidence": confidence, "route": route, "summary": text,
    })])
    logger.info("MEM: remembered %s: %s", record_id, text)


# ---------------------------------------------------------------------------
# Read: this asset's past triages (called by llm_step.py before L3 prompt)
# ---------------------------------------------------------------------------
def recall_equipment_history(asset_tag: str, query: str, k: int = RECALL_LIMIT) -> list[dict]:
    """This asset's past triage outcomes, closest to `query` first (semantic recall).
    Empty list if the collection does not exist yet (nothing remembered so far)."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client = get_client()
    if not client.collection_exists(MEMORY_COLLECTION):
        return []
    flt = Filter(must=[FieldCondition(key="asset_tag", match=MatchValue(value=asset_tag))])
    hits = client.query_points(MEMORY_COLLECTION, query=embed([query])[0],
                               query_filter=flt, limit=k).points
    return [{"record_id": h.payload["record_id"], "received_at": h.payload["received_at"],
             "priority": h.payload["priority"], "probable_fault": h.payload["probable_fault"],
             "route": h.payload["route"], "summary": h.payload["summary"],
             "score": round(h.score, 3)} for h in hits]
