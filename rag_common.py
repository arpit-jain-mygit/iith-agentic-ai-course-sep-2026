"""rag_common.py - shared RAG settings, embedding and Qdrant access.

Used by:
  rag_ingest.py  (writes: PDFs -> chunks -> vectors -> Qdrant)
  llm_step.py    (reads : event -> query -> vectors -> top chunks)

Both MUST embed with the same model into the same collection. A mismatch does
not raise an error: search still runs and silently returns poor matches.
Keeping the settings here, in one place, prevents that.

.env (next to this file) needs the 3 secrets:
  QDRANT_URL, QDRANT_API_KEY, GOOGLE_API_KEY
"""
import hashlib
import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings
#
# IN SHORT: every value both sides must agree on, in one place.
# Secrets (URL, keys) live in .env; everything else is a fixed constant here.
# To experiment (another model, another chunking), change COLLECTION too:
# vectors from different models must never share a collection.
# ---------------------------------------------------------------------------
from settings import PDF_DIR   # data location comes from DATA_ROOT in .env
COLLECTION = "plantguard_docs"
EMBED_MODEL = "gemini/gemini-embedding-001"

CACHE_DIR = HERE / ".embcache"   # one file per embedded text: re-runs cost nothing
BATCH_SIZE = 90                  # texts per embedding request (design choice)
PAUSE_S = 60                     # wait between batches to stay under a per-minute quota

PLANT_WIDE = "PLANT"             # asset_code used for plant-wide documents (not one class)


# ---------------------------------------------------------------------------
# Embedding
#
# IN SHORT: text -> vector (a list of floats). Similar meaning -> nearby vectors,
# which is what lets search find relevant sections by meaning, not exact words.
#
# Cache: each text's vector is saved to CACHE_DIR, keyed by a hash of
# (EMBED_MODEL + text). Re-running ingest, or embedding the same query twice,
# reads from disk instead of calling the API. Changing EMBED_MODEL changes
# every key, so stale vectors from an old model are never reused.
#
# Batching + pause: the API limits requests per minute, so texts are sent in
# batches of BATCH_SIZE with PAUSE_S between batches.
# ---------------------------------------------------------------------------
def _cache_path(text: str) -> Path:
    """Where the vector for this text (under EMBED_MODEL) is cached."""
    digest = hashlib.sha1((EMBED_MODEL + text).encode()).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def embed(texts: list[str]) -> list[list[float]]:
    """Vectors for texts, in the same order; uses the cache, calls the API only for new texts."""
    import litellm
    os.environ.setdefault("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    CACHE_DIR.mkdir(exist_ok=True)

    # Unique texts not yet cached (dict.fromkeys removes duplicates, keeps order)
    todo = [t for t in dict.fromkeys(texts) if not _cache_path(t).exists()]

    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start:start + BATCH_SIZE]
        resp = litellm.embedding(model=EMBED_MODEL, input=batch)
        for text, item in zip(batch, resp.data):
            _cache_path(text).write_text(json.dumps(item["embedding"]))
        if start + BATCH_SIZE < len(todo):
            logger.info("embedded %d/%d, pausing %ds (rate limit)",
                        start + len(batch), len(todo), PAUSE_S)
            time.sleep(PAUSE_S)

    return [json.loads(_cache_path(t).read_text()) for t in texts]


# ---------------------------------------------------------------------------
# Qdrant client
#
# IN SHORT: one connection to the vector database, built from .env.
# Fails early with a clear message if the credentials are missing.
#
# Timeout: the client's default (5 s) is too short for uploading batches of
# large vectors over a home connection, so it is raised to QDRANT_TIMEOUT_S.
# ---------------------------------------------------------------------------
QDRANT_TIMEOUT_S = 60    # seconds per request (design choice)


def get_client():
    """Connected QdrantClient."""
    from qdrant_client import QdrantClient

    url, key = os.getenv("QDRANT_URL"), os.getenv("QDRANT_API_KEY")
    if not url or not key:
        raise SystemExit(f"Set QDRANT_URL and QDRANT_API_KEY in {HERE / '.env'}")
    return QdrantClient(url=url, api_key=key, timeout=QDRANT_TIMEOUT_S)


# ---------------------------------------------------------------------------
# Search
#
# IN SHORT: query text -> the k most similar chunks, optionally limited to one
# asset class plus the plant-wide documents.
#   asset_code given -> filter asset_code in [asset_code, PLANT_WIDE]
#                       (that class's manual + plant-wide procedures)
#   asset_code None  -> no filter (search everything)
# Returns plain dicts, so callers do not depend on Qdrant's types.
# ---------------------------------------------------------------------------
def search(client, query: str, asset_code: str | None = None, k: int = 5) -> list[dict]:
    """Top-k chunks for the query: file, doc_title, section, pages, text, score."""
    from qdrant_client.models import FieldCondition, Filter, MatchAny

    flt = (Filter(must=[FieldCondition(key="asset_code",
                                       match=MatchAny(any=[asset_code, PLANT_WIDE]))])
           if asset_code else None)
    hits = client.query_points(COLLECTION, query=embed([query])[0],
                               query_filter=flt, limit=k).points
    return [{"file": h.payload["file"], "doc_title": h.payload["doc_title"],
             "section": h.payload["section"], "pages": h.payload["pages"],
             "text": h.payload["text"], "score": round(h.score, 3)} for h in hits]


# ---------------------------------------------------------------------------
# Split search: machine manual + plant-wide procedures, retrieved separately
#
# IN SHORT: for an event on one asset class, run TWO searches with the same
# query vector and merge them:
#   1. top K_ASSET chunks from that class's manual   (asset_code == code)
#   2. top K_PLANT chunks from plant-wide documents   (asset_code == PLANT_WIDE)
#   output: up to K_ASSET + K_PLANT chunks, best score first, each tagged with
#           "source": "asset" or "plant"
#
# Why: with ONE search over [class + plant-wide], a machine's own manual is
# so similar to questions about that machine that it can fill every slot, and
# the plant-wide procedures (permits, lockout, alarm response) never appear.
# Two searches guarantee both kinds of document are always in the results.
#
# No asset_code (the question names no class): fall back to one search over
# everything with K_ASSET + K_PLANT results, so the total stays the same.
#
# The query is embedded ONCE and reused for both searches.
# search() above stays for open questions and the self-test; triage and
# R7 use search_split().
# ---------------------------------------------------------------------------
K_ASSET = 3        # chunks from the machine's manual (design choice)
K_PLANT = 3        # chunks from plant-wide documents (design choice)


def _hits_to_dicts(hits, source: str) -> list[dict]:
    """Qdrant hits -> plain dicts (same fields as search()), plus their source."""
    return [{"file": h.payload["file"], "doc_title": h.payload["doc_title"],
             "section": h.payload["section"], "pages": h.payload["pages"],
             "text": h.payload["text"], "score": round(h.score, 3),
             "source": source} for h in hits]


def _query(client, vector: list[float], asset_code: str | None, k: int):
    """One Qdrant query: nearest k points, optionally only one asset_code."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    flt = (Filter(must=[FieldCondition(key="asset_code", match=MatchValue(value=asset_code))])
           if asset_code else None)
    return client.query_points(COLLECTION, query=vector, query_filter=flt, limit=k).points


def search_split(client, query: str, asset_code: str | None,
                 k_asset: int = K_ASSET, k_plant: int = K_PLANT) -> list[dict]:
    """Top chunks from the asset's manual AND from plant-wide documents, merged."""
    vector = embed([query])[0]                      # embed once, reuse for both searches

    if asset_code is None:                          # no class named: one search, same total
        return _hits_to_dicts(_query(client, vector, None, k_asset + k_plant), "any")

    asset_hits = _hits_to_dicts(_query(client, vector, asset_code, k_asset), "asset")
    plant_hits = _hits_to_dicts(_query(client, vector, PLANT_WIDE, k_plant), "plant")
    return sorted(asset_hits + plant_hits, key=lambda h: h["score"], reverse=True)


# ---------------------------------------------------------------------------
# Self-test: `python3 rag_common.py`
#
# IN SHORT: checks each part on its own, in order, and stops at the first
# failure with what to fix. Safe to run before ingest.
#   1. settings     : PDF folder exists and has PDFs
#   2. secrets      : the 3 keys are present in .env (values are never printed)
#   3. embed()      : one test text -> vector (calls the API once, then cached)
#   4. get_client() : connects to Qdrant, says whether COLLECTION exists yet
#   5. search()     : only if COLLECTION exists and has points (i.e. after ingest)
# ---------------------------------------------------------------------------
def self_test() -> bool:
    ok = lambda msg: print(f"  OK   {msg}")
    fail = lambda msg: print(f"  FAIL {msg}")

    print("1. settings")
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        fail(f"no PDFs in {PDF_DIR}")
        return False
    ok(f"{len(pdfs)} PDFs in {PDF_DIR}")
    ok(f"collection={COLLECTION}  model={EMBED_MODEL}")

    print("2. secrets in .env")
    missing = [k for k in ("QDRANT_URL", "QDRANT_API_KEY", "GOOGLE_API_KEY") if not os.getenv(k)]
    if missing:
        fail(f"missing {missing} in {HERE / '.env'}")
        return False
    ok("QDRANT_URL, QDRANT_API_KEY, GOOGLE_API_KEY are set")

    print("3. embed()")
    try:
        vector = embed(["self-test: pump bearing vibration"])[0]
    except Exception as e:
        fail(f"embedding failed: {type(e).__name__}: {e}")
        return False
    ok(f"vector length {len(vector)}")

    print("4. get_client()")
    try:
        client = get_client()
        exists = client.collection_exists(COLLECTION)
    except Exception as e:
        fail(f"Qdrant connection failed: {type(e).__name__}: {e}")
        return False
    ok(f"connected; collection '{COLLECTION}' exists: {exists}")

    print("5. search()")
    points = client.count(COLLECTION, exact=True).count if exists else 0
    if points == 0:
        print("  SKIP collection empty or missing: run rag_ingest.py first")
        return True
    hits = search(client, "bearing vibration", k=1)
    ok(f"{points} points; top hit: {hits[0]['file']} | {hits[0]['section']} ({hits[0]['score']})")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    raise SystemExit(0 if self_test() else 1)
