"""rag_ingest.py - build the RAG collection: PDFs -> chunks -> vectors -> Qdrant.

Run once, and again whenever the PDFs change:
  .venv/bin/python rag_ingest.py

Steps:
  R1 find PDFs    R2 extract text    R3 chunk    R4 metadata
  R5 embed        R6 store           R7 verify
"""
import json
import logging
import re
import shutil
import subprocess
import sys
import time
import uuid
from collections import Counter
from pathlib import Path

from rag_common import (COLLECTION, K_ASSET, K_PLANT, PDF_DIR, PLANT_WIDE, embed,
                        get_client, search_split)
from settings import EVAL_PATH, MOCK_API

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# R1: find the PDFs
#
# IN SHORT: list every PDF in PDF_DIR, in a fixed order, and check each one
# is usable before any expensive work starts.
#   input : PDF_DIR (from rag_common.py)
#   output: sorted list of PDF paths
#
# Why R1 exists:
#   1. Fail fast: a wrong folder or an empty file is caught here, in a second,
#      not halfway through embedding (which costs API calls and time).
#   2. Fixed order: sorted() gives the same order on every run, so chunk
#      numbering and logs are repeatable.
#
# Checks (design choices):
#   - the folder exists
#   - it contains at least one .pdf
#   - no PDF is empty (0 bytes)
# A problem stops the run with a message saying what to fix: skipping a bad
# file would silently leave part of the documentation out of search.
# ---------------------------------------------------------------------------
def find_pdfs(pdf_dir: Path = PDF_DIR) -> list[Path]:
    """Sorted, non-empty PDF files in pdf_dir."""
    if not pdf_dir.is_dir():
        raise SystemExit(f"PDF folder not found: {pdf_dir}")

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"no .pdf files in {pdf_dir}")

    empty = [p.name for p in pdfs if p.stat().st_size == 0]
    if empty:
        raise SystemExit(f"empty PDF files: {empty}")

    logger.info("R1: %d PDFs in %s", len(pdfs), pdf_dir)
    for p in pdfs:
        logger.info("  %s (%d KB)", p.name, p.stat().st_size // 1024)
    return pdfs


# ---------------------------------------------------------------------------
# R2: extract text from each PDF, page by page
#
# IN SHORT: run pdftotext on each PDF and split its output into pages.
#   input : list of PDF paths (R1)
#   output: one dict per PDF: {"file": Path, "pages": [{"page": n, "text": str}, ...]}
#           page numbers start at 1, as printed in the document
#
# Why R2 exists:
#   1. Embedding models and the LLM read text, not PDF files.
#   2. Keeping PAGE numbers lets every chunk say where it came from, so a
#      citation can point to "file, section, pages".
#
# How:
#   pdftotext <file.pdf> -   writes plain text to stdout ("-"), nothing on disk
#   pages are separated by a form-feed character "\f", so
#   output.split("\f") gives one string per page
#
# Checks (design choices):
#   - pdftotext must be installed (system tool from Poppler, not a pip package)
#   - a page with no text is kept but empty (keeps page numbering correct)
#   - a PDF with NO text at all stops the run: it is probably a scanned image,
#     which needs OCR, not text extraction
# ---------------------------------------------------------------------------
PDFTOTEXT = "pdftotext"


def check_pdftotext() -> None:
    """Stop early if the pdftotext tool is not installed."""
    if shutil.which(PDFTOTEXT) is None:
        raise SystemExit("pdftotext not found: install Poppler (brew install poppler)")


def extract_pages(pdf: Path) -> list[dict]:
    """[{"page": 1, "text": ...}, {"page": 2, ...}] for one PDF."""
    # check=True raises if pdftotext fails (e.g. a corrupt file)
    result = subprocess.run([PDFTOTEXT, str(pdf), "-"],
                            capture_output=True, text=True, check=True)

    raw_pages = result.stdout.split("\f")
    # pdftotext ends with a trailing "\f": drop the empty string it leaves,
    # otherwise every document gains a phantom extra page
    if raw_pages and not raw_pages[-1].strip():
        raw_pages = raw_pages[:-1]

    # Empty pages are kept (as "") so later page numbers stay correct
    return [{"page": n, "text": text.strip()} for n, text in enumerate(raw_pages, start=1)]


def extract_all(pdfs: list[Path]) -> list[dict]:
    """Text of every PDF: [{"file": Path, "pages": [...]}, ...]."""
    check_pdftotext()
    docs = []
    for pdf in pdfs:
        pages = extract_pages(pdf)
        chars = sum(len(p["text"]) for p in pages)
        if chars == 0:
            raise SystemExit(f"no text in {pdf.name}: scanned image? needs OCR")
        logger.info("  %s: %d pages, %d chars", pdf.name, len(pages), chars)
        docs.append({"file": pdf, "pages": pages})
    logger.info("R2: extracted text from %d PDFs", len(docs))
    return docs


# ---------------------------------------------------------------------------
# R3: chunk each document by its numbered sections
#
# IN SHORT: walk a document line by line (remembering each line's page),
# start a new chunk at every top-level section heading, and record the
# pages each chunk spans.
#   input : one document from R2 {"file", "pages": [{"page", "text"}]}
#   output: list of chunks {"section_number", "section", "part", "pages": [first, last], "text"}
#           (R4 adds file / asset / title metadata)
#
# Why section-based:
#   each chunk is one complete topic (limits table, fault table, safety
#   actions...), which is what the LLM needs to read and cite. Fixed-size
#   cuts would split a table row from its corrective action.
#
# Heading formats recognised (document STRUCTURE, not content rules):
#   "2. NORMAL OPERATING RANGES ..."   number + "." + UPPERCASE title
#   "2.0 NORMAL OPERATING RANGES ..."  same, with ".0"
#   "SECTION 2: HAZARDOUS ENERGY ..."  "SECTION" + number + ":" + UPPERCASE title
# NOT headings:
#   "2.1 Purpose"                        sub-clause (a digit follows the dot)
#   "1. Replacement of relief valves"    numbered list item (title not UPPERCASE)
# Extra guard: a heading's number must be exactly previous + 1, so a stray
# numbered line inside a section cannot start a false chunk.
#
# Rules:
#   - headings are found ANYWHERE in the text, not only at the top of a page
#     (several sections can share a page)
#   - a section continues across pages until the next heading
#   - text before the first heading = "Preamble" chunk (title page, document ID)
#   - safety net: a section longer than MAX_CHARS is split on blank-line
#     paragraph boundaries, repeating OVERLAP_PARAS paragraph(s) between parts
# ---------------------------------------------------------------------------
HEADING = re.compile(
    r"^\s*(?:SECTION\s+(?P<n1>\d{1,2})\s*:|(?P<n2>\d{1,2})(?:\.0)?\.?)\s+"   # number part
    r"(?P<title>[A-Z][A-Z0-9&/(),'\- ]{2,}[A-Z0-9)])"                       # UPPERCASE title start
)
SUBCLAUSE = re.compile(r"\d{1,2}\.\d{1,2}")      # "4.1" = start of body text on a heading line
MAX_CHARS = 4000        # split sections longer than this (design choice)
OVERLAP_PARAS = 1       # paragraphs repeated between split parts (design choice)
PREAMBLE = "Preamble"


def page_lines(doc: dict) -> list[tuple[int, str]]:
    """Every line of the document with its page number: [(page, line), ...]."""
    return [(p["page"], line) for p in doc["pages"] for line in p["text"].splitlines()]


def match_heading(line: str, expected: int) -> tuple[int, str] | None:
    """(number, title) if this line is the heading for section `expected`, else None."""
    m = HEADING.match(line)
    if not m:
        return None
    number = int(m.group("n1") or m.group("n2"))
    if number != expected:                 # numbering guard: must be previous + 1
        return None
    return number, heading_label(line)


def heading_label(line: str) -> str:
    """The heading part of a heading line, without body text that follows on
    the same line. Headings are UPPERCASE, so the label ends at the first word
    with a lowercase letter or at a sub-clause number:
      "4. PM SCHEDULE 4.1 The base..."        -> "4. PM SCHEDULE"
      "6. SPARE PARTS LIST Technicians shall" -> "6. SPARE PARTS LIST"
    """
    words = line.split()
    kept = [words[0]]                                   # "4." / "SECTION"
    for word in words[1:]:
        if SUBCLAUSE.fullmatch(word) or any(ch.islower() for ch in word):
            break
        kept.append(word)
    return " ".join(kept)


def split_sections(doc: dict) -> list[dict]:
    """Group lines into sections: [{"section_number", "section", "lines": [(page, line)]}]."""
    sections = [{"section_number": 0, "section": PREAMBLE, "lines": []}]
    expected = 1
    for page, line in page_lines(doc):
        hit = match_heading(line, expected)
        if hit:
            number, title = hit
            sections.append({"section_number": number, "section": title, "lines": [(page, line)]})
            expected = number + 1
        else:
            sections[-1]["lines"].append((page, line))

    if not any(line.strip() for _, line in sections[0]["lines"]):   # empty preamble
        sections = sections[1:]
    return sections


def _paragraphs(lines: list[tuple[int, str]]) -> list[tuple[list[int], str]]:
    """Split (page, line) pairs on blank lines: [(pages, paragraph_text), ...]."""
    paras, pages, buf = [], [], []
    for page, line in lines + [(None, "")]:          # sentinel blank line flushes the last one
        if line.strip():
            buf.append(line)
            pages.append(page)
        elif buf:
            paras.append((pages, "\n".join(buf)))
            pages, buf = [], []
    return paras


def to_chunks(section: dict) -> list[dict]:
    """One section -> one chunk, or several parts if longer than MAX_CHARS."""
    base = {"section_number": section["section_number"], "section": section["section"]}
    text = "\n".join(line for _, line in section["lines"]).strip()
    pages = [p for p, _ in section["lines"]]
    if len(text) <= MAX_CHARS:
        return [{**base, "part": 1, "pages": [min(pages), max(pages)], "text": text}]

    # Too long: pack paragraphs into parts of at most MAX_CHARS, each part
    # starting with the last OVERLAP_PARAS paragraph(s) of the previous one.
    # (A single paragraph longer than MAX_CHARS stays whole: it is never cut.)
    paras = _paragraphs(section["lines"])
    parts, current = [], []
    for para in paras:
        size = sum(len(t) + 2 for _, t in current) + len(para[1])
        if current and size > MAX_CHARS and len(current) > OVERLAP_PARAS:
            parts.append(current)
            current = current[-OVERLAP_PARAS:] if OVERLAP_PARAS else []
        current.append(para)
    parts.append(current)

    chunks = []
    for n, part in enumerate(parts, start=1):
        part_pages = [p for pages_, _ in part for p in pages_]
        chunks.append({**base, "part": n, "pages": [min(part_pages), max(part_pages)],
                       "text": "\n\n".join(t for _, t in part)})
    return chunks


def chunk_document(doc: dict) -> list[dict]:
    """All chunks of one document, in reading order."""
    chunks = [c for s in split_sections(doc) for c in to_chunks(s)]
    logger.info("  %s: %d chunks (%s)", doc["file"].name, len(chunks),
                ", ".join(str(c["section_number"]) + (f".{c['part']}" if c["part"] > 1 else "")
                          for c in chunks))
    return chunks


# ---------------------------------------------------------------------------
# R4: attach metadata to every chunk
#
# IN SHORT: give each chunk the labels it needs to be filtered, cited and
# stored: which document, which asset class, what kind of document, its
# title, its position, and a stable id.
#   input : (doc, chunks) pairs from R3
#   output: one flat list of chunks, each with:
#           id, file, doc_title, doc_type, asset_code, chunk_index,
#           section_number, section, part, pages, char_count, text
#
# Where it is stored: ONLY in Qdrant (R6), as the payload of each point, next
# to the vector. No local copy: R1-R4 rebuild it from the PDFs in seconds.
#
# Why R4 exists:
#   1. Filtering: search for a CHILLER event looks only at the CHILLER manual
#      + plant-wide procedures (asset_code filter in rag_common.search).
#   2. Citations: the LLM cites "file + section"; the reader can open the PDF
#      at the right pages.
#   3. Stable ids: re-running ingest overwrites the same points in Qdrant
#      instead of adding duplicates.
#
# Where each field comes from (no document CONTENT rules):
#   file        : PDF file name
#   asset_code  : from the FILE NAME: "manual-<code>.pdf" -> "<CODE>"
#                 (e.g. manual-cnc-mill.pdf -> CNC-MILL); any other file -> PLANT_WIDE
#                 checked against asset_classes.json: an unknown code stops the run
#   doc_type    : "manual" for manual-*.pdf, otherwise "procedure"
#   doc_title   : first line of page 1, + the next line only if the title is
#                 broken mid-phrase: the first line ENDS with a joining word
#                 ("... Manual and" / "SOP") or the next line STARTS with one
#                 ("... Manual" / "and SOP")
#   chunk_index : 0, 1, 2... reading order within the document
#   id          : uuid5 of "file#section_number#part" (same input -> same id)
#   char_count  : len(text), for size checks
# ---------------------------------------------------------------------------
MANUAL_PREFIX = "manual-"
# A title line ending in one of these words continues on the next line (design choice)
TITLE_JOINING_WORDS = {"and", "&", "of", "for", "to", "the", "in", "on", "with", "-"}


def known_asset_codes() -> set[str]:
    """asset_code values from asset_classes.json."""
    with open(MOCK_API / "asset_classes.json") as f:
        return {row["asset_code"] for row in json.load(f)}


def asset_code_for(pdf: Path, known: set[str]) -> str:
    """Asset class from the file name; PLANT_WIDE for non-manual documents."""
    if not pdf.stem.startswith(MANUAL_PREFIX):
        return PLANT_WIDE
    code = pdf.stem[len(MANUAL_PREFIX):].upper()          # "cnc-mill" -> "CNC-MILL"
    if code not in known:
        raise SystemExit(f"{pdf.name}: asset_code {code} not in asset_classes.json")
    return code


def doc_title(doc: dict) -> str:
    """Document title from the first lines of page 1."""
    lines = [l.strip() for l in doc["pages"][0]["text"].splitlines() if l.strip()]
    if not lines:
        return doc["file"].stem
    title = lines[0]
    if len(lines) > 1:
        ends_mid_phrase = title.split()[-1].lower() in TITLE_JOINING_WORDS      # "... Manual and"
        next_continues = lines[1].split()[0].lower() in TITLE_JOINING_WORDS     # "and SOP"
        if ends_mid_phrase or next_continues:
            title += " " + lines[1]
    return title


def chunk_id(file_name: str, chunk: dict) -> str:
    """Stable id: the same file/section/part always gets the same id."""
    key = f"{file_name}#{chunk['section_number']}#{chunk['part']}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def add_metadata(chunked: list[tuple[dict, list[dict]]]) -> list[dict]:
    """Flat list of chunks with full metadata."""
    known = known_asset_codes()
    records = []
    for doc, chunks in chunked:
        file_name = doc["file"].name
        code = asset_code_for(doc["file"], known)
        title = doc_title(doc)
        doc_type = "manual" if code != PLANT_WIDE else "procedure"
        for index, c in enumerate(chunks):
            records.append({
                "id": chunk_id(file_name, c),
                "file": file_name,
                "doc_title": title,
                "doc_type": doc_type,
                "asset_code": code,
                "chunk_index": index,
                **c,                                       # section_number, section, part, pages, text
                "char_count": len(c["text"]),
            })

    if len({r["id"] for r in records}) != len(records):
        raise SystemExit("duplicate chunk ids")
    logger.info("R4: %d chunks with metadata %s", len(records),
                dict(Counter(r["asset_code"] for r in records)))
    return records


# ---------------------------------------------------------------------------
# R5: embed every chunk
#
# IN SHORT: build the text to embed for each chunk (a short header + the
# chunk text), turn it into a vector with rag_common.embed(), and pair each
# record with its vector.
#   input : records from R4
#   output: list of (record, vector) pairs, same order as the records
#
# Why R5 exists:
#   search compares VECTORS, not words. A query vector lands near the chunks
#   whose meaning is closest, even when the wording differs.
#
# What gets embedded (contextual header):
#   "Document: <doc_title>\nSection: <section>\n\n<text>"
#   A chunk on its own may be just table rows and numbers; the header tells
#   the embedding which machine's manual and which section it belongs to, so
#   "chiller fault codes" finds the CHILLER fault table, not another one.
#   The header is used ONLY for the vector; the payload keeps the plain text.
#   Search queries are embedded without a header (they are short questions).
#
# Cost and repeat runs (handled inside rag_common.embed):
#   - cached on disk per text: a second run makes no API calls
#   - sent in batches with a pause between them (rate limit)
#   - changing the header format changes every text -> everything re-embeds
#
# Checks:
#   - one vector per record
#   - every vector has the same length (a mix would mean a model mix-up)
# ---------------------------------------------------------------------------
def embed_text(record: dict) -> str:
    """The text that is turned into a vector: header + chunk text."""
    return f"Document: {record['doc_title']}\nSection: {record['section']}\n\n{record['text']}"


def embed_records(records: list[dict]) -> list[tuple[dict, list[float]]]:
    """(record, vector) for every record, in the same order."""
    texts = [embed_text(r) for r in records]
    vectors = embed(texts)

    if len(vectors) != len(records):
        raise SystemExit(f"got {len(vectors)} vectors for {len(records)} chunks")
    dims = {len(v) for v in vectors}
    if len(dims) != 1:
        raise SystemExit(f"vectors have mixed lengths: {dims}")

    logger.info("R5: embedded %d chunks, vector length %d", len(vectors), dims.pop())
    return list(zip(records, vectors))


# ---------------------------------------------------------------------------
# R6: store chunks in Qdrant
#
# IN SHORT: make sure the collection exists with the right vector size,
# upload every chunk as a point (id + vector + payload), remove points that
# no longer exist, and confirm the count.
#   input : (record, vector) pairs from R5
#   output: the Qdrant collection COLLECTION holding exactly these chunks
#
# One chunk = one point:
#   id      : record["id"] (stable uuid5 from R4)
#   vector  : the numbers from R5
#   payload : every other field of the record (metadata + text)
#   Qdrant is the ONLY place the payload is stored.
#
# Steps:
#   1. collection : create it if missing (vector size from R5, cosine distance).
#                   If it exists with a DIFFERENT vector size (another model),
#                   stop: run with --recreate (never deleted silently).
#   2. indexes    : keyword indexes on asset_code, file, doc_type
#                   (Qdrant needs an index to filter on a field efficiently)
#   3. upsert     : insert-or-replace by id, in batches. Same id -> replaced,
#                   so re-running never creates duplicates.
#                   Each batch is large (vectors as JSON), so batches are kept
#                   small and a failed batch is retried with a growing pause
#                   (network timeouts are usually temporary). Retrying is safe:
#                   the same ids are simply replaced again.
#   4. stale      : delete points whose id is not in this run (e.g. a section
#                   that disappeared after re-chunking), so search never
#                   returns chunks that no longer exist
#   5. verify     : point count == number of chunks
#
# --recreate: delete the whole collection first and start clean.
# ---------------------------------------------------------------------------
INDEXED_FIELDS = ("asset_code", "file", "doc_type")
UPSERT_BATCH = 16            # points per upload request, ~1 MB each (design choice)
UPSERT_ATTEMPTS = 3          # tries per batch before giving up (design choice)
RETRY_PAUSE_S = 5            # pause before retry n is n x this (design choice)
SCROLL_PAGE = 256            # ids fetched per page when listing points (design choice)


def ensure_collection(client, dim: int, recreate: bool) -> None:
    """Collection exists with vectors of length dim (cosine)."""
    from qdrant_client.models import Distance, VectorParams

    if recreate and client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
        logger.info("R6: deleted collection %s (--recreate)", COLLECTION)

    if not client.collection_exists(COLLECTION):
        client.create_collection(COLLECTION,
                                 vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
        logger.info("R6: created collection %s (dim=%d)", COLLECTION, dim)
        return

    existing = client.get_collection(COLLECTION).config.params.vectors.size
    if existing != dim:
        raise SystemExit(f"{COLLECTION} has vector size {existing}, chunks have {dim}: "
                         "run with --recreate")


def ensure_indexes(client) -> None:
    """Keyword index on each field used in search filters (re-creating is harmless)."""
    from qdrant_client.models import PayloadSchemaType

    for field in INDEXED_FIELDS:
        client.create_payload_index(COLLECTION, field, PayloadSchemaType.KEYWORD)


def upsert_points(client, pairs: list[tuple[dict, list[float]]]) -> None:
    """Insert or replace every chunk, in batches."""
    from qdrant_client.models import PointStruct

    points = [PointStruct(id=r["id"], vector=v,
                          payload={k: val for k, val in r.items() if k != "id"})
              for r, v in pairs]
    for start in range(0, len(points), UPSERT_BATCH):
        batch = points[start:start + UPSERT_BATCH]
        for attempt in range(1, UPSERT_ATTEMPTS + 1):
            try:
                client.upsert(COLLECTION, points=batch)
                break
            except Exception as e:                       # network errors vary by library
                if attempt == UPSERT_ATTEMPTS:
                    raise SystemExit(f"upload failed after {attempt} attempts "
                                     f"(points {start}-{start + len(batch) - 1}): {e}")
                pause = attempt * RETRY_PAUSE_S
                logger.warning("R6: batch at %d failed (%s), retrying in %ds",
                               start, type(e).__name__, pause)
                time.sleep(pause)


def delete_stale(client, keep_ids: set[str]) -> int:
    """Delete points not produced by this run; returns how many were deleted."""
    from qdrant_client.models import PointIdsList

    # Page through every point, ids only
    existing_ids, offset = [], None
    while True:
        points, offset = client.scroll(COLLECTION, limit=SCROLL_PAGE, offset=offset,
                                       with_payload=False, with_vectors=False)
        existing_ids += [p.id for p in points]
        if offset is None:
            break

    stale = [i for i in existing_ids if str(i) not in keep_ids]
    if stale:
        client.delete(COLLECTION, points_selector=PointIdsList(points=stale))
    return len(stale)


def store(pairs: list[tuple[dict, list[float]]], recreate: bool = False) -> None:
    """Write all chunks to Qdrant and verify the count."""
    client = get_client()
    dim = len(pairs[0][1])

    ensure_collection(client, dim, recreate)
    ensure_indexes(client)
    upsert_points(client, pairs)
    removed = delete_stale(client, {r["id"] for r, _ in pairs})

    count = client.count(COLLECTION, exact=True).count
    if count != len(pairs):
        raise SystemExit(f"{COLLECTION} has {count} points, expected {len(pairs)}")
    logger.info("R6: %s holds %d points (%d stale removed)", COLLECTION, count, removed)


# ---------------------------------------------------------------------------
# R7: verify retrieval quality
#
# IN SHORT: run every graded question in golden_set.json through search and
# check that the documents it MUST cite come back in the results.
#   input : the stored collection (R6), golden_set.json
#   output: per-question PASS / MISS, and overall recall
#           (logged; the run does not fail, it reports)
#
# Why R7 exists:
#   if search returns the wrong sections, the LLM reasons from the wrong
#   rules however good the prompt is. R7 measures retrieval ON ITS OWN,
#   before any LLM is involved, so a bad answer later can be traced to
#   either retrieval or the model.
#
# How a question is searched (same as at triage time: rag_common.search_split):
#   - if the question mentions a known asset_code (from asset_classes.json,
#     e.g. "AIR-COMP"): top K_ASSET chunks from that class's manual
#     + top K_PLANT chunks from plant-wide documents
#   - otherwise: top K_ASSET + K_PLANT chunks from everything
#   - the returned doc_title values are compared with must_cite
#
# Metrics:
#   recall per question = cited titles found / titles in must_cite
#   recall overall      = all found / all required, over questions with must_cite
#   questions with an empty must_cite are skipped (nothing to retrieve)
# ---------------------------------------------------------------------------


def load_golden_set() -> list[dict]:
    """Graded questions: id, question, must_cite, category, ..."""
    with open(EVAL_PATH) as f:
        return json.load(f)


def asset_code_in(question: str, known: set[str]) -> str | None:
    """A known asset_code mentioned in the question, or None (longest code first)."""
    upper = question.upper()
    for code in sorted(known, key=len, reverse=True):
        if code in upper:
            return code
    return None


def check_case(client, case: dict, known: set[str]) -> dict:
    """Search one question; which required titles were found?"""
    code = asset_code_in(case["question"], known)
    hits = search_split(client, case["question"], asset_code=code)
    titles = {h["doc_title"] for h in hits}

    required = set(case["must_cite"])
    found = required & titles
    return {"id": case["id"], "category": case["category"], "asset_filter": code,
            "required": sorted(required), "found": sorted(found),
            "missing": sorted(required - found),
            "recall": len(found) / len(required)}


def verify() -> float:
    """Log PASS/MISS per graded question and return overall recall."""
    client = get_client()
    known = known_asset_codes()
    cases = [c for c in load_golden_set() if c["must_cite"]]

    logger.info("R7: checking retrieval for %d graded questions (%d asset + %d plant-wide chunks)",
                len(cases), K_ASSET, K_PLANT)
    results = [check_case(client, c, known) for c in cases]
    for r in results:
        status = "PASS" if not r["missing"] else "MISS"
        logger.info("  %s %s [%s] filter=%s missing=%s",
                    status, r["id"], r["category"], r["asset_filter"], r["missing"])

    total_required = sum(len(r["required"]) for r in results)
    total_found = sum(len(r["found"]) for r in results)
    recall = total_found / total_required
    logger.info("R7: recall = %.0f%% (%d/%d cited documents retrieved, %d questions)",
                100 * recall, total_found, total_required, len(results))
    return recall


# ---------------------------------------------------------------------------
# Run: each step feeds the next (R1 -> R7)
# ---------------------------------------------------------------------------
def main() -> None:
    pdfs = find_pdfs()                         # R1
    docs = extract_all(pdfs)                   # R2
    logger.info("R3: chunking by section")
    chunked = [(doc, chunk_document(doc)) for doc in docs]     # R3
    logger.info("R3: %d chunks in total", sum(len(c) for _, c in chunked))
    records = add_metadata(chunked)                            # R4
    pairs = embed_records(records)                             # R5
    store(pairs, recreate="--recreate" in sys.argv)            # R6
    verify()                                                   # R7


if __name__ == "__main__":
    main()
