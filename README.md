# PlantGuard: Predictive Maintenance & Supply Chain Ops Copilot

Triages plant maintenance events (alarms, operator reports, shift logs, inspections):
priority, probable fault, safety, permit, missing readings, parts, technicians and a route
(`auto` or `human_review`). Grounds every answer in the plant's own manuals/SOPs via RAG,
and answers free-text maintenance questions the same way.

Capstone project, IIT Hyderabad Applied AI Professional Certification Program — Problem
Statement 5.

## Setup

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
brew install poppler        # pdftotext, used by rag_ingest.py
```

Fill in `.env` (already in the repo, committed blank — **never commit real values into it**):

```
DATA_ROOT=/path/to/capstone-data-toolkit/data/plantguard
LLM_MODEL=gemini/gemini-3.5-flash
GOOGLE_API_KEY=...
QDRANT_URL=...
QDRANT_API_KEY=...
LANGFUSE_PUBLIC_KEY=...   # optional - tracing no-ops (one warning, no crash) if unset
LANGFUSE_SECRET_KEY=...   # optional
LANGFUSE_BASE_URL=...     # optional
```

`DATA_ROOT`, `LLM_MODEL`, `GOOGLE_API_KEY`, `QDRANT_URL` and `QDRANT_API_KEY` are all
required — `settings.py` checks them together at import time and lists every missing one
in a single error if any are blank, before anything else runs.

One-time: build the Qdrant collection from the PDF manuals (needed before any retrieval,
Q&A, or triage run):

```bash
.venv/bin/python rag_common.py       # self-test: settings, keys, embedding, Qdrant
.venv/bin/python rag_ingest.py       # chunk + embed + store (rerun only when PDFs change)
```

## Entry points

PlantGuard has several independent entry points, one per milestone. Pick the one that
matches what you want to do.

### Run one event through the 5-agent team (M6 — the main path)

```bash
.venv/bin/python agents.py PLANTGUARD-00000
```

Runs Log Intake → Manual/SOP RAG → Maintenance Recommendation → Safety Reviewer →
routing → Procurement (gated on `route == "auto"`) → equipment-memory write, end to end.
Logs every step as `***STEP N (LLM/non-LLM)***`, tagged by whether it made a real model
call; filter the noise out with:

```bash
.venv/bin/python agents.py PLANTGUARD-00000 2>&1 | grep STEP
```

### Run the same event through LangGraph (M5 — checkpointed, human-approval interrupt)

```bash
.venv/bin/python graph.py PLANTGUARD-00000          # pauses here if route != auto
.venv/bin/python graph.py PLANTGUARD-00000 --approve   # resume and complete
.venv/bin/python graph.py PLANTGUARD-00000 --reject    # resume and reject instead
```

State is checkpointed to `checkpoints.db` (gitignored, regenerates), keyed by `record_id`.
CLI-only — not wired into `api.py`.

### Ask a free-text question (M8 Q&A)

```bash
.venv/bin/python qa.py "What is the normal operating pressure range for CHILLER-01?"
.venv/bin/python qa.py "..." --verbose   # also show LiteLLM/Qdrant/httpx logs
```

### Run the golden-set evaluation (M8)

```bash
.venv/bin/python eval_golden.py                    # all 20 graded Q&A cases
.venv/bin/python eval_golden.py PLANTGUARD-EV-901   # one case only
```

### Run the FastAPI service (M8 — the production path)

```bash
.venv/bin/uvicorn api:app --reload
```

Fails to start (not just to serve) if any required `.env` value is missing or Qdrant is
unreachable. Once up: `http://127.0.0.1:8000/docs` for the interactive API, or:

```bash
curl -s -X POST http://127.0.0.1:8000/triage/PLANTGUARD-00000 | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" \
  -d '{"question": "..."}' | python3 -m json.tool
curl -s http://127.0.0.1:8000/status | python3 -m json.tool
```

### Run the MCP ERP server standalone (M6)

```bash
.venv/bin/python mcp_server.py       # stdio transport, for any MCP client
```

`agents.py`'s Procurement agent calls these same two tools (`check_stock`,
`raise_purchase_order`) in-process — this standalone run is only needed to connect an
external MCP client.

### Core pipeline, one step at a time (useful for debugging)

```bash
.venv/bin/python facts.py PLANTGUARD-00000 --evaluate       # steps 1-13, JSON only, no API calls
.venv/bin/python llm_step.py PLANTGUARD-00000 --evaluate    # + retrieval + 1 LLM call + citation guard
.venv/bin/python llm_step.py PLANTGUARD-00000 --agent       # M2: agentic tool-calling variant (6 tools)
.venv/bin/python decide.py PLANTGUARD-00000 --evaluate --save runs/PLANTGUARD-00000.json
.venv/bin/python decide.py --from-file runs/PLANTGUARD-00000.json   # replay, no LLM call
```

- Pass a `record_id` (unique). An `event_id` works only if unique.
- `--evaluate` compares against the event's `ground_truth` after the decision; labels
  never reach the prompt.
- `facts.py --full` also prints the complete facts.

## Design rule

**Code uses only JSON data** (mock API tables + intake events); anything from manuals/SOP
PDFs is read by the **LLM**, through RAG, never hardcoded. Citations are checked against
the actually-retrieved chunks (L5), and claims are groundedness-checked against FACTS/cited
text by a second LLM call (H5) — not just trusted.

## Architecture at a glance

```
event -> facts.py (L1, steps 1-13, JSON only)
      -> llm_step.py (L2 retrieve, L3/L4 decision, L5 citations, H5 groundedness)
      -> decide.py (P1-P5: triage, parts, technicians, guards, route)
PDFs  -> rag_ingest.py (R1-R7, run once) -> Qdrant (plantguard_docs)
```

Wrapped by one of two orchestration paths (`graph.py` or `agents.py`) — see
[ARCHITECTURE.md](ARCHITECTURE.md) for the full block diagram, both paths, the 5-agent
team, and the milestone → file map.

| Milestone | Files | What it adds |
|---|---|---|
| M1 | `intake.py`, `models.py` | Raw text → structured event (LLM parse) |
| M2 | `llm_step.py` (`--agent`, `TOOLS`) | Standalone agentic tool-calling demo (6 tools) |
| M3 | `memory.py` | Persistent, episodic equipment memory (Qdrant) |
| M4 | `rag_common.py`, `rag_ingest.py` | Manuals/SOPs chunked, embedded, hybrid + rerank retrieval |
| M5 | `graph.py` | LangGraph orchestration, checkpointing, human-approval interrupt |
| M6 | `agents.py`, `mcp_server.py` | 5-agent team + MCP ERP server (production path) |
| M7 | `tracing.py`, `reliability.py` | LangFuse tracing; retries + circuit breaker |
| M8 | `qa.py`, `eval_golden.py`, `api.py` | Free-text Q&A, golden-set eval, hard-block guardrail, FastAPI |
| Core | `facts.py`, `llm_step.py`, `decide.py` | Shared L1-L6 / P1-P5 / H5 steps, reused by every milestone |

## Current results

- Golden-set Q&A eval (`eval_golden.py`, 20 graded cases): **75%** (15/20) — factual and
  unanswerable-detection categories both perfect.
- Full triage run across all 200 dataset records (`agents.py`): **197/200** completed end
  to end; 9 routed `auto`, 188 `human_review` (the remaining 3 hit a Gemini free-tier
  daily quota limit, not a logic fault). See `records-logs.md` for the full per-record
  trace and summary table.
- `AUTO_ROUTING_ENABLED = True` in `decide.py` — real conditional routing (4 independent
  rules; any one firing sends the event to `human_review`).
- Retrieval mode: `SEARCH_MODE = "rerank"` in `rag_common.py` — hybrid (dense + keyword)
  search, fused, then LLM-reranked.
