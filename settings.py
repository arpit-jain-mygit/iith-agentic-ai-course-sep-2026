"""settings.py - machine-specific config, read once from .env.

Every file that needs data or credentials imports from here, so they're all
set in ONE place: .env, next to this file.

Why .env and not code: the location and credentials differ per machine (your
Mac, a teammate's laptop, a grader's machine). The code stays the same; each
person sets their own values.

All five values below are REQUIRED. They are checked together, here, at
import time - not one at a time as each is first used - so a half-configured
.env is reported in ONE error listing every missing value, not a loop of
"fix this, rerun, fix the next one, rerun". This file is imported (directly
or transitively) by every real entry point in the project, so this check
always runs before anything else does.

LANGFUSE_* (tracing.py) are intentionally NOT required: the project is
designed to run with tracing disabled (a no-op) if they're unset. GROQ_API_KEY
and OPENAI_API_KEY in the .env template are unused by any code in this
project - alternate-provider keys left over from setup, not read anywhere.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

_REQUIRED = {
    "DATA_ROOT": "the folder that holds mock_api/, intake/, corpus/",
    "LLM_MODEL": "e.g. gemini/gemini-3.5-flash - the LLM used for triage",
    "GOOGLE_API_KEY": "Gemini API key, for every LLM call and embedding",
    "QDRANT_URL": "Qdrant Cloud cluster URL, for retrieval and equipment memory",
    "QDRANT_API_KEY": "Qdrant Cloud API key",
}
_missing = [f"  {name:<15} {hint}" for name, hint in _REQUIRED.items() if not os.getenv(name)]
if _missing:
    raise SystemExit(
        f"Missing {len(_missing)} required value(s) in {HERE / '.env'}:\n" + "\n".join(_missing)
    )

DATA_ROOT = Path(os.environ["DATA_ROOT"]).expanduser()
if not DATA_ROOT.is_dir():
    raise SystemExit(f"DATA_ROOT folder not found: {DATA_ROOT} (check .env)")

# Every data path is built from DATA_ROOT
MOCK_API = DATA_ROOT / "mock_api"                       # JSON tables (facts.py)
RECORDS_PATH = DATA_ROOT / "intake" / "records.jsonl"   # intake events (intake.py)
PDF_DIR = DATA_ROOT / "corpus" / "pdf"                  # documents for RAG (rag_common.py)
EVAL_PATH = DATA_ROOT / "eval" / "golden_set.json"      # graded questions (rag_ingest.py R7)

# litellm's Gemini provider reads GEMINI_API_KEY, not GOOGLE_API_KEY - mirror it once here
# so callers don't each need their own os.environ.setdefault(...) line.
os.environ.setdefault("GEMINI_API_KEY", os.environ["GOOGLE_API_KEY"])


def llm_model() -> str:
    """The LLM used for triage, e.g. "gemini/gemini-3.5-flash". Already validated above;
    this just returns it. Use a pinned version, not a "-latest" alias - an alias can
    silently change."""
    return os.environ["LLM_MODEL"]


def google_api_key() -> str:
    """The Gemini API key. Already validated above; this just returns it."""
    return os.environ["GOOGLE_API_KEY"]
