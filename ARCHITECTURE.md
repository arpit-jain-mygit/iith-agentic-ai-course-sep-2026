# PlantGuard - Architecture

ASCII overview of the full system (M1-M8), with step numbers matching the
code's own `L1-L6`/`P1-P5`/`H1-H6` step labels. Steps 1-12 are the shared
core pipeline; 13 onward is where the two orchestration layers
(`graph.py` vs `team.py`) diverge, then re-converge at step 17 (the M3
memory write).

```
┌──────────────────────────────── DATA SOURCES ─────────────────────────────────┐
│  records.jsonl        mock API JSON tables       PDFs            golden_set   │
│  (intake events)      (assets, telemetry,        (manuals/SOPs)  (20 eval     │
│                        work_orders, inventory,                    cases)      │
│                        purchase_orders, techs)                                │
└───────────┬──────────────────┬────────────────────────┬──────────────┬───────┘
            │                  │                         │              │
            │                  │                  ┌──────▼──────┐       │
            │                  │                  │ rag_ingest  │       │
            │                  │                  │ .py (M4)    │       │
            │                  │                  │ chunk+embed │       │
            │                  │                  │ (pre-run,   │       │
            │                  │                  │  once)      │       │
            │                  │                  └──────┬──────┘       │
            │                  │                         │              │
            │                  │                         ▼              │
            │                  │              ┌─────────────────────┐   │
            │                  │              │       Qdrant          │   │
            │                  │              │ ┌─────────────────┐  │   │
            │                  │              │ │ plantguard_docs │  │   │
            │                  │              │ ├─────────────────┤  │   │
            │                  │              │ │ plantguard_     │  │   │
            │                  │              │ │ equipment_      │  │   │
            │                  │              │ │ memory          │  │   │
            │                  │              │ └─────────────────┘  │   │
            │                  │              └──────────▲──────────┘   │
            │                  │                         │              │
┌───────────▼──────────────────▼─────────────────────────┼──────────────▼───────┐
│                          CORE TRIAGE PIPELINE (per event)                      │
│                                                          │                      │
│  STEP 1        STEP 2        STEP 3                    │    STEP 4            │
│  ┌───────────┐ ┌───────────┐ ┌──────────────┐          │    ┌──────────────┐  │
│  │ intake.py │▶│ facts.py  │▶│  memory.py   │──────────┘    │  llm_step.py │  │
│  │   (M1)    │ │(L1, steps │ │ read (M3     │────────────────▶ STEP 4:      │  │
│  │ LLM parse │ │  1-13)    │ │ recall)      │                │  L2 retrieve │  │
│  │ raw text  │ │ JSON-only │ └──────────────┘                │  (search_    │  │
│  │ -> event  │ │  facts    │                                 │   best, M4)  │  │
│  └───────────┘ └───────────┘                                 ├──────────────┤  │
│                                                                │ STEP 5:      │  │
│                                                                │  L3/L4 LLM   │  │
│                                                                │  recommend-  │  │
│                                                                │  ation call  │  │
│                                                                ├──────────────┤  │
│                                                                │ STEP 6:      │  │
│                                                                │  L5 citation │  │
│                                                                │  guard       │  │
│                                                                ├──────────────┤  │
│                                                                │ STEP 7:      │  │
│                                                                │  H5 ground-  │  │
│                                                                │  edness      │  │
│                                                                │  judge       │  │
│                                                                └──────┬───────┘  │
│                                                                       │         │
│                                                                ┌──────▼──────┐  │
│                                                                │  decide.py  │  │
│                                                                │ STEP 8: P1  │  │
│                                                                │  triage     │  │
│                                                                │ STEP 9: P2  │  │
│                                                                │  parts      │  │
│                                                                │ STEP 10: P3 │  │
│                                                                │  techs      │  │
│                                                                │ STEP 11: P4 │  │
│                                                                │  guards     │  │
│                                                                │ STEP 12: P5 │  │
│                                                                │  route      │  │
│                                                                └──────┬──────┘  │
└───────────────────────────────────────────────────────────────────┬─┴──────────┘
                                                                      │
                           ┌──────────────────────────────────────────┤
                           │ STEP 13: pipeline wrapped by ONE of       │
                           │ two orchestration layers (choose path)    │
                           ▼                                          ▼
           ┌───────────────────────────┐              ┌───────────────────────────────┐
           │       graph.py (M5)        │              │          team.py (M6)          │
           │                            │              │                                 │
           │ STEP 13a: intake→lookup    │              │ STEP 13b: Log Intake (1) →      │
           │  →recommend→route node     │              │  Manual RAG (2) → Maintenance    │
           │  (re-runs steps 1-12       │              │  Recommendation (3)              │
           │   above as graph nodes)    │              │  (re-runs steps 1-12 above       │
           │                            │              │   as agent calls)                │
           │ STEP 14: conditional       │              │                                   │
           │  branch on route ─┬──────┐ │              │ STEP 14: Safety Reviewer (4)      │
           │                   │      │ │              │  - fires only if safety_critical  │
           │              [auto_log] [approval]         │    or requires_permit             │
           │                   │      │ │              │  - unsafe verdict -> critical flag │
           │ STEP 15a:         │ STEP 15b:              │                                   │
           │  log + done       │  interrupt()           │ STEP 15: route re-checked          │
           │                   │  pause, Sqlite         │  (route=="auto" only below)        │
           │                   │  checkpoint,           │                                    │
           │                   │  resume with           │ STEP 16: Procurement (5)           │
           │                   │  --approve/--reject     │  - raises POs via MCP, GATED on    │
           └───────────────────┼────────────────────────┘    route=="auto" (M8 guardrail)     │
                                │                        └───────────────┬────────────────────┘
                                │                                        │
                                │                                        ▼
                                │                          ┌───────────────────────────┐
                                │                          │     mcp_server.py (M6)      │
                                │                          │ STEP 16a: check_stock        │
                                │                          │ STEP 16b: raise_purchase_    │
                                │                          │  order (idempotent, writes   │
                                │                          │  procurement_log.json)       │
                                │                          └───────────────┬───────────────┘
                                │                                          │
                                └──────────────────┬───────────────────────┘
                                                    │
                                          STEP 17: memory.py write
                                          (M3 remember) - every live
                                          run, both paths, skipped on
                                          unmatched asset or replay
                                                    │
                              ┌─────────────────────┴────────────────────┐
                              │  CROSS-CUTTING (M7 - every step above      │
                              │  passes through these)                     │
                              │                                             │
                              │  tracing.py          reliability.py         │
                              │  @observe wraps       @with_retries +       │
                              │  steps 13-16           CircuitBreaker wrap  │
                              │  (LangFuse, no-ops     steps 2 (sensor_feed)│
                              │   w/o keys)            & 16a/16b (erp)      │
                              └─────────────────────────────────────────────┘

┌──────────────────────────── Q&A + EVAL + API (M8) ─────────────────────────────┐
│                                                                                  │
│  ┌───────────┐        ┌────────────────┐        ┌─────────────────────────┐    │
│  │  qa.py    │◀───────│ eval_golden.py │        │         api.py           │    │
│  │ STEP A:   │ STEP B │ STEP C: 20     │        │       (FastAPI)          │    │
│  │ retrieve  │ answer │ golden cases,  │        │ STEP X: POST /triage/{id}│────▶ team.py (step 13b)
│  │ STEP A2:  │ (RAG + │ each checks    │        │ STEP Y: POST /ask ───────│────▶ qa.py (steps A-B)
│  │ guardrail │ guard- │ route+must_    │        │ STEP Z: GET  /status      │    │
│  │ classify  │ rail)  │ cite+must_not_ │        │  (Qdrant health, memory   │    │
│  │ route     │        │ contain        │        │   count, POs, breakers)  │    │
│  └───────────┘        └────────────────┘        └──────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────────┘

External services, used across every numbered step above: Gemini (via LiteLLM -
all LLM calls + embeddings), Qdrant Cloud (vector search), LangFuse (optional tracing).
```

## Milestone -> file map

| Milestone | Files |
|---|---|
| M1 | `intake.py`, `models.py` |
| M2 | `llm_step.py` (`--agent` path: `run_agent`, `TOOLS`) |
| M3 | `memory.py` |
| M4 | `rag_common.py`, `rag_ingest.py` |
| M5 | `graph.py` |
| M6 | `team.py`, `mcp_server.py` |
| M7 | `tracing.py`, `reliability.py` |
| M8 | `qa.py`, `eval_golden.py`, `api.py` |
| Core (L1-L6, P1-P5, H5) | `facts.py`, `llm_step.py`, `decide.py` |
