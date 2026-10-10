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
    route_ok = result["route"] == case["expected_route"]

    titles = cited_doc_titles(result)
    missing_cites = [t for t in case.get("must_cite", []) if t not in titles]
    cite_ok = not missing_cites

    answer_lower = result["answer"].lower()
    violated = [p for p in case.get("must_not_contain", []) if p.lower() in answer_lower]
    guardrail_ok = not violated

    return {"id": case["id"], "category": case["category"], "pass": route_ok and cite_ok and guardrail_ok,
            "route_ok": route_ok, "got_route": result["route"], "expected_route": case["expected_route"],
            "cite_ok": cite_ok, "missing_cites": missing_cites,
            "guardrail_ok": guardrail_ok, "violated_phrases": violated}


def run() -> dict:
    cases = load_golden_set()
    results = []
    for i, case in enumerate(cases):
        result = answer_question(case["question"])
        outcome = check_case(case, result)
        results.append(outcome)
        status = "PASS" if outcome["pass"] else "FAIL"
        logger.info("%s %-20s route=%s%s%s", status, outcome["id"], outcome["got_route"],
                   "" if outcome["cite_ok"] else f" missing_cites={outcome['missing_cites']}",
                   "" if outcome["guardrail_ok"] else f" VIOLATED={outcome['violated_phrases']}")
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
    import json
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    summary = run()
    print(json.dumps({"total": summary["total"], "passed": summary["passed"],
                      "failures": [r["id"] for r in summary["failures"]],
                      "guardrail_violations": [r["id"] for r in summary["guardrail_violations"]]}, indent=2))
