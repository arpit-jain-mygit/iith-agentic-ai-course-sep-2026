"""settings.py - machine-specific paths, read once from .env.

Every file that needs data imports its paths from here, so the data location
is set in ONE place: the DATA_ROOT line in .env (next to this file).

Why .env and not code: the location differs per machine (your Mac, a
teammate's laptop, a grader's machine). The code stays the same; each person
sets their own DATA_ROOT.

DATA_ROOT is REQUIRED. A silent default would point at the wrong folder on
someone else's machine, so a missing or wrong value stops with a clear message.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

_root = os.getenv("DATA_ROOT")
if not _root:
    raise SystemExit(f"Set DATA_ROOT in {HERE / '.env'} (the folder that holds mock_api/, intake/, corpus/)")

DATA_ROOT = Path(_root).expanduser()
if not DATA_ROOT.is_dir():
    raise SystemExit(f"DATA_ROOT folder not found: {DATA_ROOT} (check .env)")

# Every data path is built from DATA_ROOT
MOCK_API = DATA_ROOT / "mock_api"                       # JSON tables (facts.py)
RECORDS_PATH = DATA_ROOT / "intake" / "records.jsonl"   # intake events (intake.py)
PDF_DIR = DATA_ROOT / "corpus" / "pdf"                  # documents for RAG (rag_common.py)
EVAL_PATH = DATA_ROOT / "eval" / "golden_set.json"      # graded questions (rag_ingest.py R7)

# The LLM used for triage (llm_step.py), e.g. "gemini/gemini-3.5-flash".
# In .env so it can be switched (or tried per machine) without editing code.
# Use a pinned version, not a "-latest" alias: an alias can silently change.
# Read lazily: files that make no LLM call (facts.py, rag_ingest.py) do not need it.
def llm_model() -> str:
    model = os.getenv("LLM_MODEL")
    if not model:
        raise SystemExit(f"Set LLM_MODEL in {HERE / '.env'} (e.g. gemini/gemini-3.5-flash)")
    return model
