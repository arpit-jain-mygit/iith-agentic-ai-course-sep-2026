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
import re
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


# ===========================================================================
# M4: production retrieval = hybrid search (dense + keyword) + LLM rerank
#
# IN SHORT: search_split() above finds sections by MEANING only. M4 adds:
#   H1 keyword index : BM25 over the same chunks, so exact tokens
#                      (part numbers, tag names, fault codes) always match
#   H2 hybrid        : dense list + keyword list merged with RRF
#   H3 rerank        : ONE LLM call scores every candidate against the
#                      query; the best K_ASSET + K_PLANT are kept
#   search_best()    : the entry point triage and the agent use; its mode
#                      (dense / hybrid / rerank) is picked by H4's numbers
#
# Why: dense vectors blur near-identical codes (VPW-P-00043 vs -00034) and
# similarity is not relevance. Keyword search fixes the first, the rerank
# the second. The asset / plant-wide split is kept in every mode.
# ===========================================================================


# ---------------------------------------------------------------------------
# H1: keyword (BM25) index over the stored chunks
#
# IN SHORT: read every chunk back from Qdrant (R6 stored the text in the
# payload), split each into tokens, build a BM25 index in memory.
#   input : the Qdrant collection (no PDFs, no local copy)
#   output: KeywordIndex: search(query, asset_code, k) -> chunk dicts,
#           best keyword score first
#
# Tokens: lower-case runs of letters/digits, KEEPING "-" and "_" inside a
# token, so "VPW-P-00043" and "VIB_TRIP" stay one token each (a plain split
# on punctuation would turn them into common pieces like "p" and "00043").
# Built once per process (about 100 chunks: milliseconds), cached in memory.
# ---------------------------------------------------------------------------
SCROLL_PAGE = 256                                   # points per Qdrant scroll request
TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")   # "vpw-p-00043", "vib_trip" stay whole


def _chunk_dict(point_id, payload: dict, score: float, source: str | None = None) -> dict:
    """One chunk in the shared output shape (as search_split) + its id."""
    out = {"id": str(point_id), "file": payload["file"], "doc_title": payload["doc_title"],
           "section": payload["section"], "pages": payload["pages"], "text": payload["text"],
           "asset_code": payload["asset_code"], "score": round(score, 4)}
    if source:
        out["source"] = source
    return out


def load_all_chunks(client) -> list[dict]:
    """Every stored chunk as a dict (payload fields + 'id'), via Qdrant scroll."""
    chunks, offset = [], None
    while True:
        points, offset = client.scroll(COLLECTION, limit=SCROLL_PAGE, offset=offset,
                                       with_payload=True, with_vectors=False)
        chunks += [_chunk_dict(p.id, p.payload, 0.0) for p in points]
        if offset is None:                          # no more pages
            return chunks


def tokenize(text: str) -> list[str]:
    """Lower-case tokens; codes like vpw-p-00043 / vib_trip stay whole."""
    return TOKEN_RE.findall(text.lower())


class KeywordIndex:
    """BM25 over all chunks; search can be limited to one asset_code."""

    def __init__(self, chunks: list[dict]):
        from rank_bm25 import BM25Okapi
        self.chunks = chunks
        # Title + section are indexed with the text: "Fault codes" in a heading counts
        self.bm25 = BM25Okapi([tokenize(f"{c['doc_title']} {c['section']} {c['text']}")
                               for c in chunks])

    def search(self, query: str, asset_code: str | None, k: int) -> list[dict]:
        """Top-k chunks by BM25 score (only chunks of asset_code, if given)."""
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(
            ((s, c) for s, c in zip(scores, self.chunks)
             if s > 0 and (asset_code is None or c["asset_code"] == asset_code)),
            key=lambda pair: pair[0], reverse=True)
        return [dict(c, score=round(float(s), 4)) for s, c in ranked[:k]]


_KEYWORD_INDEX: KeywordIndex | None = None


def get_keyword_index(client) -> KeywordIndex:
    """The process-wide KeywordIndex, built on first use."""
    global _KEYWORD_INDEX
    if _KEYWORD_INDEX is None:
        chunks = load_all_chunks(client)
        _KEYWORD_INDEX = KeywordIndex(chunks)
        logger.info("H1: keyword index built over %d chunks", len(chunks))
    return _KEYWORD_INDEX


# ---------------------------------------------------------------------------
# H2: hybrid search = dense + keyword, fused with Reciprocal Rank Fusion
#
# IN SHORT: for ONE source (the asset's manual, or plant-wide documents):
#   1. dense  : top POOL chunks by vector similarity  (same as search_split)
#   2. keyword: top POOL chunks by BM25                (H1)
#   3. fuse   : each chunk scores sum(1 / (RRF_C + rank)) over the lists it
#               appears in; best fused score first
#   output    : up to POOL candidate chunks for that source, "score" = RRF score
#
# Why RRF: BM25 scores and cosine similarities are on different scales and
# cannot be added; RRF uses ranks only. RRF_C = 60 is the usual default: it
# damps the gap between rank 1 and rank 2 so neither list dominates.
# ---------------------------------------------------------------------------
POOL = 10          # candidates per list, per source (design choice)
RRF_C = 60         # RRF constant (standard default)


def rrf_fuse(rankings: list[list[str]], c: int = RRF_C) -> list[tuple[str, float]]:
    """Ids ranked by fused score: [(id, score)], best first."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            fused[item] = fused.get(item, 0.0) + 1.0 / (c + rank)
    return sorted(fused.items(), key=lambda pair: pair[1], reverse=True)


def hybrid_source(client, query: str, vector: list[float], asset_code: str | None,
                  pool: int = POOL) -> list[dict]:
    """Fused candidates for one source (asset_code or PLANT_WIDE; None = all)."""
    dense = [_chunk_dict(h.id, h.payload, h.score) for h in _query(client, vector, asset_code, pool)]
    keyword = get_keyword_index(client).search(query, asset_code, pool)

    by_id = {c["id"]: c for c in keyword + dense}            # same chunk -> one dict
    fused = rrf_fuse([[c["id"] for c in dense], [c["id"] for c in keyword]])[:pool]
    return [dict(by_id[cid], score=round(score, 4)) for cid, score in fused]


# ---------------------------------------------------------------------------
# H3: LLM rerank
#
# IN SHORT: one LLM call sees the query and ALL candidates (asset + plant
# pools, numbered) and scores each 0-10 for how directly it helps answer
# the query. Code then keeps the top k_asset asset chunks and the top
# k_plant plant-wide chunks, best first.
#   output: same dict shape as search_split, "score" = rerank score / 10
#
# Why an LLM and not similarity: similarity measures "sounds alike", the
# rerank judges "actually answers this". It reads query and chunk TOGETHER.
# The prompt is generic (relevance only); no plant rules are coded.
#
# Cache: scores are saved under CACHE_DIR keyed by (model + query + chunk
# ids), so re-running H4 or the same event costs nothing. If the call fails,
# the hybrid order is used and a warning is logged (retrieval never breaks
# because of the rerank).
# ---------------------------------------------------------------------------
RERANK_TEXT_CHARS = 1500     # chunk text shown to the reranker (design choice: bounds prompt size)

RERANK_PROMPT = """You rank document excerpts for a search query.
For each numbered excerpt, give a score from 0 to 10 for how directly it helps answer the query:
10 = directly answers it, 5 = related background, 0 = unrelated.
Judge relevance only; do not answer the query. Score every excerpt exactly once.
Return JSON matching the schema."""


def _rerank_schema():
    """Pydantic schema for the rerank answer (built lazily: pydantic loads on use)."""
    from pydantic import BaseModel, Field

    class ExcerptScore(BaseModel):
        index: int                                   # excerpt number as shown, 1-based
        score: int = Field(ge=0, le=10)

    class RerankScores(BaseModel):
        scores: list[ExcerptScore]

    return RerankScores


def _rerank_scores(query: str, candidates: list[dict]) -> dict[str, int]:
    """chunk id -> 0-10 score, from the cache or one LLM call."""
    from settings import llm_model
    key = hashlib.sha1("|".join([llm_model(), query] + [c["id"] for c in candidates]).encode())
    path = CACHE_DIR / f"rerank-{key.hexdigest()}.json"
    if path.exists():
        return json.loads(path.read_text())

    from llm_step import call_structured             # lazy: llm_step imports this module
    excerpts = "\n\n".join(f"[{i}] {c['doc_title']} | {c['section']}\n{c['text'][:RERANK_TEXT_CHARS]}"
                           for i, c in enumerate(candidates, start=1))
    answer = call_structured(RERANK_PROMPT, f"QUERY:\n{query}\n\nEXCERPTS:\n{excerpts}",
                             _rerank_schema())
    scores = {candidates[s.index - 1]["id"]: s.score
              for s in answer.scores if 1 <= s.index <= len(candidates)}
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(scores))
    return scores


def rerank(query: str, candidates: list[dict], k_asset: int = K_ASSET,
           k_plant: int = K_PLANT) -> list[dict]:
    """Best k_asset + k_plant candidates by LLM relevance score."""
    quota = {"asset": k_asset, "plant": k_plant, "any": k_asset + k_plant}
    try:
        scores = _rerank_scores(query, candidates)
        missing = sum(c["id"] not in scores for c in candidates)
        if missing:
            logger.warning("H3: reranker skipped %d candidate(s); they score 0", missing)
    except Exception as e:                           # retrieval must not break on the rerank
        logger.warning("H3: rerank failed (%s: %s); keeping hybrid order", type(e).__name__, e)
        scores = None

    kept = []
    for source, k in quota.items():
        pool = [c for c in candidates if c.get("source") == source]   # already in hybrid order
        if scores is not None:
            pool = sorted(pool, key=lambda c: scores.get(c["id"], 0), reverse=True)  # stable on ties
        kept += [dict(c, score=round(scores.get(c["id"], 0) / 10, 2)) if scores is not None else c
                 for c in pool[:k]]
    return sorted(kept, key=lambda c: c["score"], reverse=True)


# ---------------------------------------------------------------------------
# search_best: the retrieval used by triage (llm_step L2) and the agent tool
#
# IN SHORT: one function, three modes, same output shape:
#   "dense"  : search_split()                        (M3 baseline)
#   "hybrid" : H2 per source, top k_asset + k_plant by RRF
#   "rerank" : H2 per source, then H3 over both pools
# SEARCH_MODE is set from the H4 comparison (rag_ingest.py --compare).
#
# H6: confirmed on the golden set (18 graded questions, 3 asset + 3 plant-wide chunks):
#     mode      recall  precision   MRR
#     dense       86%       56%    0.91
#     hybrid      89%       57%    0.93
#     rerank      89%       62%    0.95
# rerank ties hybrid on recall but wins precision and MRR -> kept as SEARCH_MODE.
# ---------------------------------------------------------------------------
SEARCH_MODE = "rerank"


def search_best(client, query: str, asset_code: str | None, mode: str = SEARCH_MODE,
                k_asset: int = K_ASSET, k_plant: int = K_PLANT) -> list[dict]:
    """Chunks for the query in the chosen mode (asset manual + plant-wide)."""
    if mode == "dense":
        return search_split(client, query, asset_code, k_asset, k_plant)
    if mode not in ("hybrid", "rerank"):
        raise ValueError(f"unknown search mode {mode!r}")

    vector = embed([query])[0]                       # embed once, reuse for every source
    sources = ({"any": None} if asset_code is None
               else {"asset": asset_code, "plant": PLANT_WIDE})
    candidates = [dict(c, source=name) for name, code in sources.items()
                  for c in hybrid_source(client, query, vector, code)]

    if mode == "rerank":
        return rerank(query, candidates, k_asset, k_plant)

    quota = {"asset": k_asset, "plant": k_plant, "any": k_asset + k_plant}
    kept = [c for name in sources
            for c in [c for c in candidates if c["source"] == name][:quota[name]]]
    return sorted(kept, key=lambda c: c["score"], reverse=True)


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


# ---------------------------------------------------------------------------
# M4 try-out: `python rag_common.py --m4 "query" [ASSET_CODE]`
#
# IN SHORT: run one query through every mode (dense / hybrid / rerank) and
# print what each returns, side by side, to SEE the difference H1-H3 make.
# ---------------------------------------------------------------------------
def try_modes(query: str, asset_code: str | None) -> None:
    client = get_client()
    for mode in ("dense", "hybrid", "rerank"):
        print(f"\n== {mode} ==")
        for c in search_best(client, query, asset_code, mode=mode):
            print(f"  {c['score']:>7}  {c.get('source', '-'):5}  {c['file']} | {c['section'][:60]}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if len(sys.argv) > 2 and sys.argv[1] == "--m4":
        try_modes(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        raise SystemExit(0)
    raise SystemExit(0 if self_test() else 1)
