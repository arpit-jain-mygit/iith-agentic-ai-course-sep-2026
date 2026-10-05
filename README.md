# PlantGuard: maintenance-event triage

Triages plant maintenance events (alarms, operator reports, shift logs, inspections):
priority, probable fault, safety, permit, missing readings, plus parts, technicians and a route.

Design rule: **code uses only JSON data** (mock API tables + intake events); anything from
manuals / SOP PDFs is read by the **LLM** through RAG. The LLM is called **once per event**.

## Pipeline

```
event -> facts.py (steps 1-13, JSON only)
      -> llm_step.py (retrieve from Qdrant + 1 LLM call + citation check)
      -> decide.py (P1-P5: final triage, parts, technicians, guards, route)
PDFs  -> rag_ingest.py (R1-R7, run once) -> Qdrant
```

| File | Role |
|---|---|
| `settings.py` | paths from `DATA_ROOT`, `LLM_MODEL` (both in `.env`) |
| `models.py`, `intake.py` | load + validate intake events |
| `facts.py` | steps 1-13: asset, missing fields, trip, suspect readings, limits, telemetry, history, downtime, inventory, technicians, prompt facts |
| `rag_common.py` | embedding (cached), Qdrant client, `search` / `search_split` |
| `rag_ingest.py` | R1-R7: find PDFs, extract, chunk by section, metadata, embed, store, verify recall |
| `llm_step.py` | L1-L6: facts, retrieve, prompt, validated LLM call, citation guard |
| `decide.py` | P1-P5: final triage, parts check, technician filter, guards, route + final record |

## Setup

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env        # then fill in the values
brew install poppler        # pdftotext, used by rag_ingest.py
```

## Run

```bash
.venv/bin/python rag_common.py                     # self-test: settings, keys, embedding, Qdrant
.venv/bin/python rag_ingest.py                     # build the collection (once / when PDFs change)
.venv/bin/python facts.py PLANTGUARD-00000 --evaluate   # steps 1-13 only, no API calls
.venv/bin/python llm_step.py PLANTGUARD-00000 --evaluate
.venv/bin/python decide.py PLANTGUARD-00000 --evaluate --save runs/PLANTGUARD-00000.json
.venv/bin/python decide.py --from-file runs/PLANTGUARD-00000.json   # replay, no LLM call
```

- Pass a `record_id` (unique). An `event_id` works only if unique.
- `--evaluate` compares with the event's `ground_truth` after the decision; labels never reach the prompt.
- `facts.py --full` also prints the complete facts.

## Current settings and results

- Retrieval: `search_split` = 3 asset-manual + 3 plant-wide chunks; R7 recall **86%** on `golden_set.json`.
- LLM: `LLM_MODEL` in `.env`. `gemini-3.5-flash` triaged the sample event correctly;
  `gemini-3.5-flash-lite` runs but misjudged its priority.
- Route: `AUTO_ROUTING_ENABLED = False` in `decide.py`, so every event goes to `human_review`
  (reasons are still listed: critical flags, high-risk job, low confidence, trip).
