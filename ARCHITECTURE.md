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

## Horizontal (step-flow) view

Same system, laid out left-to-right by step order instead of nested boxes.

```
═══════════════════════════ CORE TRIAGE PIPELINE (steps 1-12) ═══════════════════════════

┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐   ┌──────────────────┐
│  STEP 1  │   │  STEP 2  │   │  STEP 3  │   │   STEP 4-7   │   │    STEP 8-12      │
│ intake.py│──▶│ facts.py │──▶│ memory.py│──▶│  llm_step.py │──▶│    decide.py       │
│   (M1)   │   │ (L1, 1-13│   │ M3 read  │   │ 4 L2 retrieve│   │ 8  P1 triage       │
│ LLM parse│   │ JSON-only│   │ (recall  │   │ 5 L3/L4 LLM  │   │ 9  P2 parts        │
│ raw text │   │  facts)  │   │  past    │   │   call       │   │ 10 P3 techs        │
│ -> event │   │          │   │ triages) │   │ 6 L5 citation│   │ 11 P4 guards       │
│          │   │          │   │          │   │   guard      │   │ 12 P5 route        │
│          │   │          │   │          │   │ 7 H5 ground- │   │                     │
│          │   │          │   │          │   │   edness     │   │                     │
└──────────┘   └──────────┘   └──────────┘   └──────────────┘   └─────────┬───────────┘
      ▲               ▲             ▲▼              ▲▼                     │
  records.jsonl   mock API JSON   Qdrant:        Qdrant:                   │
                  tables          equipment_     plantguard_docs           │
                                  memory          (M4, via                 │
                                                   rag_ingest.py)           │
                                                                            │
                                                                            ▼
═══════════════════ STEP 13: ORCHESTRATION (pick ONE path) ═══════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│  PATH A: graph.py (M5)                                                       │
│                                                                               │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────────────────────────┐    │
│  │ STEP 13a │──▶│ STEP 14  │──▶│           STEP 15 (branch)             │    │
│  │ re-runs  │   │conditional│   │  auto ──▶ 15a: log + done              │    │
│  │ steps    │   │ branch on │   │           (no pause)                   │    │
│  │ 1-12 as  │   │ route     │   │                                        │    │
│  │ 4 graph  │   │           │   │  else ──▶ 15b: interrupt() pause,      │    │
│  │ nodes    │   │           │   │           SqliteSaver checkpoint,      │    │
│  │          │   │           │   │           resume --approve/--reject    │    │
│  └──────────┘   └──────────┘   └──────────────────┬─────────────────────┘    │
└──────────────────────────────────────────────────┬┴────────────────────────┘
                                                      │
┌─────────────────────────────────────────────────────────────────────────────┐
│  PATH B: team.py (M6) - 5 named agents                                       │
│                                                                               │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────────┐     │
│  │ STEP 13b │──▶│ STEP 14  │──▶│ STEP 15  │──▶│       STEP 16          │     │
│  │ 1 Log    │   │ 4 Safety │   │ route    │   │ 5 Procurement           │     │
│  │  Intake  │   │  Reviewer│   │ re-check │   │  raises POs via         │     │
│  │ 2 Manual │   │ (fires   │   │ (only    │   │  mcp_server.py:         │     │
│  │  RAG     │   │  only if │   │ "auto"   │   │   16a check_stock       │     │
│  │ 3 Maint. │   │  safety/ │   │ proceeds)│   │   16b raise_purchase_   │     │
│  │  Recomm- │   │  permit) │   │          │   │        order (idem-     │     │
│  │  endation│   │ unsafe ⇒ │   │          │   │        potent)          │     │
│  │ (re-runs │   │ critical │   │          │   │  GATED: route must be   │     │
│  │  1-12)   │   │  flag    │   │          │   │  "auto" (M8 guardrail)  │     │
│  └──────────┘   └──────────┘   └──────────┘   └───────────┬─────────────┘     │
└───────────────────────────────────────────────────────────┬───────────────────┘
                                                              │
                     ┌────────────────────────────────────────┘
                     ▼
            ┌─────────────────────┐
            │       STEP 17        │
            │ memory.py write (M3) │
            │ every live run, both │
            │ paths; skipped on    │
            │ unmatched asset or   │
            │ replay               │
            └─────────────────────┘

─────────────────────── CROSS-CUTTING, every step 13-16 (M7) ───────────────────────
  tracing.py: @observe wraps steps 13-16 (LangFuse, no-ops without keys)
  reliability.py: @with_retries + CircuitBreaker wrap step 2 (sensor_feed) and
                   steps 16a/16b (erp) - raises ServiceUnavailable, never a silent default


═══════════════════════════ Q&A + EVAL + API (M8) ═══════════════════════════

┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   STEP A-A2  │   │    STEP B    │   │    STEP C     │
│   qa.py      │──▶│   qa.py      │   │ eval_golden.py│
│ A  retrieve  │   │ answer (RAG  │   │ 20 golden     │
│ A2 guardrail │   │  + guard-    │   │ cases, each   │
│    classify  │   │  rail)       │◀──│ checks route +│
│    route     │   │              │   │ must_cite +   │
│              │   │              │   │ must_not_     │
│              │   │              │   │ contain       │
└──────────────┘   └──────────────┘   └──────────────┘
       ▲
       │
┌──────┴───────────────────────────────────────────────┐
│                     api.py (FastAPI)                  │
│  STEP X: POST /triage/{id}  ──▶ team.py (step 13b)    │
│  STEP Y: POST /ask          ──▶ qa.py (steps A-B)      │
│  STEP Z: GET  /status       ──▶ Qdrant health, memory  │
│                                 count, POs, breakers    │
└─────────────────────────────────────────────────────────┘

External services used across every step above: Gemini (via LiteLLM - all LLM
calls + embeddings), Qdrant Cloud (vector search), LangFuse (optional tracing).
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
