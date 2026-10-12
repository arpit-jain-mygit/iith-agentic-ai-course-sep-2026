"""eval_golden.py - M8: end-to-end golden-set evaluation.

  .venv/bin/python eval_golden.py

Unlike H4 (rag_ingest.py --compare), which only measures RETRIEVAL on these
20 questions, this runs the full answering path (qa.py: retrieve + LLM
answer + guardrail + route) and checks every field the golden set grades:

  route            : does qa.py's route match expected_route exactly?
  must_cite        : does the answer's citations cover every required
                      document (matched by doc_title, via the retrieved
                      chunks)?
  must_not_contain  : does the answer's TEXT avoid every forbidden phrase
                      (case-insensitive substring - the guardrail check)?

A case passes only if all three hold. Reports a table + every failure, so a
regression is visible immediately, not just a dropping aggregate score.
"""
import logging
import time

from qa import answer_question
from settings import EVAL_PATH

logger = logging.getLogger(__name__)

CASE_PAUSE_S = 15  # pause between cases: each case makes 2+ calls (rerank + answer); stays under
                   # the free-tier 15 req/min quota


def load_golden_set() -> list[dict]:
    import json
    return json.loads(EVAL_PATH.read_text())


def cited_doc_titles(result: dict) -> set[str]:
    """doc_titles behind the citations actually used, via the retrieved chunks."""
    by_key = {(c["file"], c["section"]): c["doc_title"] for c in result["chunks"]}
    return {by_key[(c["file"], c["section"])] for c in result["citations"]
            if (c["file"], c["section"]) in by_key}


def check_case(case: dict, result: dict) -> dict:
    """route / must_cite / must_not_contain, each pass/fail, for one case."""
    logger.info("[STEP C] check_case IN:  id=%s expected_route=%s must_cite=%s must_not_contain=%s "
               "| got route=%s citations=%s", case["id"], case["expected_route"],
               case.get("must_cite", []), case.get("must_not_contain", []),
               result["route"], result["citations"])

    route_ok = result["route"] == case["expected_route"]

    titles = cited_doc_titles(result)
    missing_cites = [t for t in case.get("must_cite", []) if t not in titles]
    cite_ok = not missing_cites

    answer_lower = result["answer"].lower()
    violated = [p for p in case.get("must_not_contain", []) if p.lower() in answer_lower]
    guardrail_ok = not violated

    outcome = {"id": case["id"], "category": case["category"], "pass": route_ok and cite_ok and guardrail_ok,
              "route_ok": route_ok, "got_route": result["route"], "expected_route": case["expected_route"],
              "cite_ok": cite_ok, "missing_cites": missing_cites,
              "guardrail_ok": guardrail_ok, "violated_phrases": violated}
    logger.info("[STEP C] check_case OUT: %s", outcome)
    return outcome


def run(case_id: str | None = None) -> dict:
    cases = load_golden_set()
    if case_id:
        cases = [c for c in cases if c["id"] == case_id]
        if not cases:
            raise SystemExit(f"{case_id}: not found in {EVAL_PATH}")
    results = []
    for i, case in enumerate(cases):
        logger.info("[STEP C] grading %s START", case["id"])
        result = answer_question(case["question"])
        outcome = check_case(case, result)
        results.append(outcome)
        status = "PASS" if outcome["pass"] else "FAIL"
        logger.info("[STEP C] grading %s END: pass=%s", case["id"], outcome["pass"])
        route_part = (f"route={outcome['got_route']}" if outcome["route_ok"] else
                     f"route: expected={outcome['expected_route']} got={outcome['got_route']}")
        logger.info("%s %-20s %s%s%s", status, outcome["id"], route_part,
                   "" if outcome["cite_ok"] else f" missing_cites={outcome['missing_cites']}",
                   "" if outcome["guardrail_ok"] else f" VIOLATED={outcome['violated_phrases']}")
        if not outcome["pass"]:
            logger.info("  EXPECTED (golden): %s", case.get("expected") or "(no free-text description)")
            logger.info("  GOT      (answer): %s", result["answer"])
        if i + 1 < len(cases):
            time.sleep(CASE_PAUSE_S)

    passed = sum(r["pass"] for r in results)
    logger.info("M8: %d/%d passed (%.0f%%)", passed, len(results), 100 * passed / len(results))

    by_category = {}
    for r in results:
        by_category.setdefault(r["category"], []).append(r["pass"])
    for cat, outcomes in by_category.items():
        logger.info("M8: %-14s %d/%d", cat, sum(outcomes), len(outcomes))

    failures = [r for r in results if not r["pass"]]
    guardrail_violations = [r for r in results if not r["guardrail_ok"]]
    return {"total": len(results), "passed": passed, "results": results,
            "failures": failures, "guardrail_violations": guardrail_violations}


if __name__ == "__main__":
    import argparse
    import json
    # force=True: facts.py/intake.py call basicConfig() at import time, which otherwise wins first
    # (logging.basicConfig is a no-op once the root logger already has a handler).
    logging.basicConfig(level=logging.INFO, force=True,
                        format="%(asctime)s %(levelname)s %(filename)s:%(funcName)s: %(message)s")
    for noisy in ("LiteLLM", "litellm", "langfuse", "httpx", "httpcore"):   # third-party noise only
        logging.getLogger(noisy).setLevel(logging.ERROR)
    parser = argparse.ArgumentParser(description="M8: run the golden-set eval (all 20, or one case)")
    parser.add_argument("case_id", nargs="?", help="e.g. PLANTGUARD-EV-901; omit to run all 20")
    args = parser.parse_args()
    summary = run(args.case_id)
    print(json.dumps({"total": summary["total"], "passed": summary["passed"],
                      "failures": [r["id"] for r in summary["failures"]],
                      "guardrail_violations": [r["id"] for r in summary["guardrail_violations"]]}, indent=2))
