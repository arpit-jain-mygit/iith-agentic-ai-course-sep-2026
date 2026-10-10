# PlantGuard - Test Plan

Self-test guide covering all 8 milestones (M1-M8). Each test case names the
exact command to run and what to check in the output. Start here (E2E);
lower-level (unit/integration) test cases will be added in a later section.

## M1 - Intake parsing

| ID | Objective | Command | Expected |
|---|---|---|---|
| E2E-M1-01 | LLM correctly resolves asset from free text | `.venv/bin/python intake.py --parse-batch 20` *(or however you invoke M1-E)* | `asset_accuracy` reported >= 0.8; log shows per-event OK/MISS |
| E2E-M1-02 | Conflicting sensor vs. text reading is flagged | Pick an event where readings differ from the narrative; inspect `conflicts` field | `conflicts` list is non-empty for that event |
| E2E-M1-03 | Unknown/garbled asset name resolves to `None`, not a guess | Feed a nonsense asset name via `parse_event` | `asset_tag` is `None`, not a hallucinated tag |

## M2 - Single tool-agent

| ID | Objective | Command | Expected |
|---|---|---|---|
| E2E-M2-01 | Agent reaches an answer using tools, not precomputed facts | `.venv/bin/python llm_step.py PLANTGUARD-00000 --agent` | JSON output has `trace` with >=1 tool call; `decision` present |
| E2E-M2-02 | Agent respects the step cap | Temporarily lower `AGENT_MAX_STEPS`, rerun | Log shows `"hit AGENT_MAX_STEPS, forcing an answer"` |
| E2E-M2-03 | `search_manuals` tool citations pass the L5 guard | Same run as E2E-M2-01 | `invalid_citations` is empty |

## M3 - Persistent equipment memory

| ID | Objective | Command | Expected |
|---|---|---|---|
| E2E-M3-01 | First triage on an asset recalls nothing | `.venv/bin/python decide.py <record_id A, asset X>` | Log: `"M3: 0 past triage(s) recalled"` |
| E2E-M3-02 | Second triage on the same asset recalls the first | `.venv/bin/python decide.py <record_id B, same asset X>` | Log: `"M3: 1 past triage(s) recalled"`; recalled summary is semantically related |
| E2E-M3-03 | Replay (`--from-file`) never writes a new memory | `.venv/bin/python decide.py --from-file runs/X.json` | No `"MEM: remembered"` log line appears |
| E2E-M3-04 | Unmatched-asset event doesn't crash the write | Triage an event with a bad/unknown asset_tag | Log: `"M3: asset unmatched, nothing to remember"`, no traceback |

## M4 - Production RAG + groundedness

| ID | Objective | Command | Expected |
|---|---|---|---|
| E2E-M4-01 | Rerank mode beats dense/hybrid on the golden set | `.venv/bin/python rag_ingest.py --compare` | `rerank` row has >= dense/hybrid on recall, best on precision+MRR |
| E2E-M4-02 | A fabricated recommended action is caught | Run any `decide.py <record_id>`; inspect `flags` | If H5 finds an unsupported claim, `ungrounded_claims` (critical) appears and `confidence` drops to `low` |
| E2E-M4-03 | Disabling the judge skips the extra call, cleanly | Set `JUDGE_ENABLED = False` in `llm_step.py`, rerun | `groundedness.score` is `null`, no second LLM call in the log |

## M5 - LangGraph orchestration

| ID | Objective | Command | Expected |
|---|---|---|---|
| E2E-M5-01 | A flagged event pauses for approval | `.venv/bin/python graph.py <record_id>` | Output is `{"paused": true, "interrupt": {...}}`, not a final record |
| E2E-M5-02 | Resuming reuses the checkpoint, no re-run | `.venv/bin/python graph.py <same record_id> --approve` | No new `"LLM: calling..."` log lines before the final result; `"approved": true` in output |
| E2E-M5-03 | Rejecting is recorded distinctly from approving | `.venv/bin/python graph.py <record_id> --reject` | `"approved": false` in the final output |
| E2E-M5-04 | A clean event auto-logs without pausing | Find/force a case with no guard flags | Output returns a final record directly (no `"paused": true`), `"approved": true` |

## M6 - Multi-agent team + MCP server

| ID | Objective | Command | Expected |
|---|---|---|---|
| E2E-M6-01 | All 5 agents run end to end | `.venv/bin/python team.py <record_id>` | Output has `final`, `safety_review`, `procurement`, `intake_check` all populated |
| E2E-M6-02 | Safety Reviewer fires only when warranted | Run on a non-safety-critical, non-permit event | `safety_review.reviewed` is `false` (no second LLM call) |
| E2E-M6-03 | Procurement raises a PO for a real shortage | Run on an event whose `fault_parts` includes an out-of-stock part | `procurement.purchase_orders_raised` is non-empty; `po_id` starts `AGENT-PO-` |
| E2E-M6-04 | Procurement is idempotent | Run the same record_id's team twice | Second run's PO has `"created": false`, same `po_id` as the first |
| E2E-M6-05 | MCP server starts and lists its tools | `.venv/bin/python mcp_server.py` (separate terminal), connect with any MCP client (e.g. `mcp dev mcp_server.py` or Claude Desktop) | `check_stock` and `raise_purchase_order` are listed with correct schemas |

## M7 - Tracing + reliability

| ID | Objective | Command | Expected |
|---|---|---|---|
| E2E-M7-01 | Tracing degrades gracefully without keys | Run anything in `team.py` with `.env` unset for `LANGFUSE_*` | One `"Authentication error"` warning, pipeline still completes |
| E2E-M7-02 | Tracing actually reports, with real keys | Set `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY`, rerun `team.py` | A new trace named `run_team` appears in your LangFuse project, with 5 child spans |
| E2E-M7-03 | Retries exhaust and raise, never return a silent default | (unit-level, but observable E2E) monkeypatch `get_telemetry_summary` to always fail, run `decide.py` | Pipeline crashes with `ServiceUnavailable`, not a quiet "no telemetry" result |

## M8 - Eval harness, hard-block guardrail, FastAPI

| ID | Objective | Command | Expected |
|---|---|---|---|
| E2E-M8-01 | Full golden-set run reports per-category scores | `.venv/bin/python eval_golden.py` | Table logged for `guardrail`/`multi_hop`/`unanswerable`/`factual`; overall `%` printed |
| E2E-M8-02 | A lockout-bypass request is refused, not complied with | `.venv/bin/python qa.py "...skip the paperwork..."` | `route: human_review`, `bypasses_safety_request: true`, answer refuses |
| E2E-M8-03 | Procurement is withheld on a human_review team run | Run `team.py` on a flagged event with a part shortage | `procurement.purchase_orders_raised` is `[]`, `withheld_reason` present |
| E2E-M8-04 | `/triage` works over HTTP | `.venv/bin/uvicorn api:app` (separate terminal), then `curl -X POST http://127.0.0.1:8000/triage/PLANTGUARD-00000` | 200, full triage JSON |
| E2E-M8-05 | `/triage` 404s cleanly on a bad id | `curl -X POST http://127.0.0.1:8000/triage/NOT-REAL` | 404, `{"detail": "...not found"}` |
| E2E-M8-06 | `/status` reflects real system state | `curl http://127.0.0.1:8000/status` | `qdrant_connected: true`, `equipment_memories_stored` > 0, circuit breakers listed |

---

29 E2E cases across all 8 milestones. Lower-level (unit/integration) test
cases to be added in a later section.
