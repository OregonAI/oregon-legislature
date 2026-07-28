#!/usr/bin/env python3
"""Mirror pipeline for oregon-legislature: measure metadata + bill text.
See PHASE5-MCP-SPEC.md §5.3 (design), §2/§2.1b (measured API facts), §7
(guardrails). Follows the shape of oregon-policy-repo/src/ingest_ors.py:
idempotent, per-unit argv, catalog status tracking, skip-and-record rather
than fail.

  python3 src/ingest_measures.py 2025R1 [2024R1 ...] [--limit N] [--concurrency N]

Per session:
  1. Fetch Measure metadata with one $select of the mirrored fields (§5.1),
     fully paginated with $skip and verified against odata.count -- the
     server emits $top rows with NO nextLink (measured), so a single call
     silently truncates. This corpus's worst failure mode.
  2. Fetch the MeasureDocuments index for the session, same paginated
     discipline (2025R1: 6,178 rows, well past a single $top=4000 call).
  3. Download bill-text PDFs for versions Introduced and Enrolled ONLY
     (§2.1b), concurrency-capped at 4 (half the measured no-throttling
     ceiling of 8), skipping anything already snapshotted (idempotent,
     exactly like ingest_ors.py skips ingested sections).
  4. Extract text and write one markdown document per measure.

PDF extraction uses pypdf, not pdftotext: this environment has no poppler
binary installed, and PHASE5-MCP-SPEC.md §2.1b itself names both as
acceptable ("pdftotext/pypdf extracts cleanly; no OCR needed"). Extraction
yielding under ~200 chars is recorded as not_extractable and never
fabricated -- see MIN_EXTRACT_CHARS in `ingest_session`.

source_sha256 always comes from corpus_toolkit.repo.hash_snapshot() -- never
reimplemented. See `build_frontmatter`'s comments for the exact snapshot
each frontmatter's (source_url, source_format, snapshot_id) triple points at:
the embedded bill-text PDF when one was captured, else the session's shared
metadata JSON snapshot.
"""
import argparse
import io
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "_meta" / "snapshots"
MEASURES_DIR = REPO_ROOT / "measures"
CATALOG_PATH = REPO_ROOT / "_meta" / "catalog" / "measures.yml"

# corpus_toolkit must be installed (see requirements.txt) -- `pip install
# -e /path/to/corpus_toolkit` in this environment, since it isn't on PyPI.
from corpus_toolkit.repo import hash_snapshot, normalize_ws  # noqa: E402

BASE_URL = "https://api.oregonlegislature.gov/odata/odataservice.svc"
USER_AGENT = ("Mozilla/5.0 (oregon-legislature corpus ingest; "
              "+https://github.com/OregonAI/oregon-legislature)")
TODAY = date.today().isoformat()
MAINTAINER = "@dzinck"

# §5.1: mirror identity + the searchable narrative fields; leave out
# CurrentLocation/CurrentCommitteeCode/FiscalImpact/RevenueImpact/
# EffectiveDate/ChapterNumber/Vetoed/EmergencyClause -- those are the
# "current value" fields §5.1's own test says to proxy, not mirror.
MEASURE_SELECT = [
    "SessionKey", "MeasurePrefix", "MeasureNumber", "PrefixMeaning",
    "CatchLine", "MinorityCatchLine", "MeasureSummary", "RelatingTo",
    "RelatingToFull", "AtTheRequestOf", "LCNumber", "CreatedDate", "ModifiedDate",
]
DOCUMENT_SELECT = ["SessionKey", "MeasurePrefix", "MeasureNumber",
                   "VersionDescription", "DocumentUrl", "ModifiedDate"]

# --- appropriations-only scope -------------------------------------------------------
#
# Matched against CatchLine + RelatingTo + MeasureSummary, all of which arrive in the
# metadata page BEFORE any PDF is fetched — so a filtered session costs one metadata call
# and downloads bill text only for what it keeps.
#
# WHY THIS SCOPE EXISTS. Mirroring all 15 sessions that funded FY2019-FY2025 means 11,958
# measures and takes this repo from ~500 MB to ~2.6 GB, which also lands in the MCP image
# (the Dockerfile COPYs the whole repo). Appropriation-shaped measures are ~6% of a
# session, and they are the ones oregon-budget extracts line items from. Scope decided
# with the maintainer, 2026-07-28.
#
# DELIBERATELY BROAD. "moneys" alone catches a great deal, and that is the intended
# direction: a false positive costs one PDF, while a false negative silently drops an
# appropriation from the budget corpus's reach. Precision is the extractor's job — it
# already reports "no dollar amounts found" for a bill that carries none.
APPROPRIATION_RE = re.compile(
    r"appropriat|moneys|expenditure limitation|budget|lottery bonds|"
    r"revenue bonds|general fund|other funds|federal funds", re.I)


def is_appropriation_shaped(m: dict) -> bool:
    blob = " ".join(str(m.get(k) or "") for k in
                    ("CatchLine", "RelatingTo", "RelatingToFull", "MeasureSummary"))
    return bool(APPROPRIATION_RE.search(blob))

# §2.1b's recommended version policy: what was proposed and what became law.
WANTED_VERSIONS = ("Introduced", "Enrolled")

PAGE_SIZE = 2000          # comfortably under the measured $top>=4000 ceiling
MAX_CONCURRENCY = 4       # §7/measured: ceiling was 8, use half
PDF_TIMEOUT = 60
MIN_EXTRACT_CHARS = 200   # §7/measured: below this, record not_extractable

CITE_RE = re.compile(
    r"\bORS\s+((?:\d{2,3}[A-Z]{0,2}\.\d{3,4}(?:\s*\(\d+\))?\s*"
    r"(?:,\s*(?:and\s+)?|and\s+)?)+)")
SECN_RE = re.compile(r"\d{2,3}[A-Z]{0,2}\.\d{3,4}")

FURN_BRACKET_RE = re.compile(r"^\[\d+\]$")


# --------------------------------------------------------------------------
# OData access -- pagination is the one thing this module must never get
# wrong (PHASE5-MCP-SPEC.md: "a run that fetches 4,000 of 6,178 and reports
# success is the single worst failure mode here").
# --------------------------------------------------------------------------

def odata_get(query: str) -> dict:
    url = f"{BASE_URL}/{query}"
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all(entity: str, filter_clause: str, select_fields: list, orderby: str):
    """Page an OData v3 entity set with $skip until every row odata.count
    promised has been retrieved. Returns (rows, total). Raises if the
    retrieved count doesn't match odata.count -- silent truncation is the
    one failure mode this function exists to prevent; it must be loud."""
    select = ",".join(select_fields)
    rows, skip, total = [], 0, None
    pages = 0
    while True:
        q = (f"{entity}?$filter={urllib.parse.quote(filter_clause)}"
             f"&$select={select}&$orderby={urllib.parse.quote(orderby)}"
             f"&$top={PAGE_SIZE}&$skip={skip}&$inlinecount=allpages")
        page = odata_get(q)
        pages += 1
        if total is None:
            total = int(page["odata.count"])
        batch = page["value"]
        rows.extend(batch)
        skip += PAGE_SIZE
        if not batch or skip >= total:
            break
    if len(rows) != total:
        raise RuntimeError(
            f"{entity} filter={filter_clause!r}: paginated {len(rows)} rows "
            f"across {pages} page(s) but odata.count={total} -- pagination "
            f"bug, aborting rather than silently truncating")
    print(f"    {entity}: {len(rows)}/{total} rows across {pages} page(s) "
          f"(page size {PAGE_SIZE}) -- odata.count verified")
    return rows, total


def fetch_session_name(session: str) -> str:
    try:
        page = odata_get(f"LegislativeSessions?$filter=SessionKey%20eq%20"
                         f"%27{session}%27&$select=SessionKey,SessionName")
        rows = page.get("value") or []
        return rows[0]["SessionName"] if rows else session
    except Exception:
        return session


# --------------------------------------------------------------------------
# PDF fetch + extraction
# --------------------------------------------------------------------------

def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=PDF_TIMEOUT) as resp:
        return resp.read()


def extract_pdf_text(raw: bytes) -> str:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(raw))
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages)


def clean_bill_text(raw_text: str, prefix: str, number: int) -> str:
    """Strip page furniture specific to these PDFs, mechanically -- never
    touches prose. Two shapes only, both structural artifacts of how OLIS
    typesets a bill, not content: (a) the left-margin per-line numbering
    column, which pypdf extracts as a contiguous run of bare digit lines
    (verified against HB 2049: page 1 -> lines '1'..'28' before any prose);
    (b) the running '<PREFIX> <NUMBER>' header repeated on every page after
    the first, and the bracketed '[<page>]' footer. A real bill line is
    never JUST a bare number or exactly the bill's own citation -- so this
    can't collide with content."""
    banner = f"{prefix} {number}"
    out = []
    for ln in raw_text.splitlines():
        s = ln.strip()
        if s == banner or FURN_BRACKET_RE.match(s) or re.fullmatch(r"\d{1,3}", s):
            continue
        out.append(ln)
    res, blank = [], 0
    for ln in out:
        if not ln.strip():
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        res.append(ln)
    return "\n".join(res).strip("\n")


def candidate_ors_citations(text: str) -> list:
    """Distinct ORS section citations found in `text`, list-aware (an initial
    'ORS 137.225, 163A.040 and 163A.215' names one 'ORS' but three sections).
    Every edge produced from this is a CANDIDATE per PHASE5-MCP-SPEC.md §2.2/
    §2.1b -- RelatingToFull is a summary field and a bill-text regex is still
    a candidate, never a finding."""
    found = set()
    for m in CITE_RE.finditer(text or ""):
        for sm in SECN_RE.finditer(m.group(1)):
            found.add(sm.group(0))
    return sorted(found)


# --------------------------------------------------------------------------
# Snapshot + doc-id helpers
# --------------------------------------------------------------------------

def measure_doc_id(session: str, prefix: str, number: int) -> str:
    return f"measure-{session.lower()}-{prefix.lower()}{number}"


def pdf_snapshot_id(doc_id: str, version: str) -> str:
    return f"{doc_id}-{version.lower()}"


def metadata_snapshot_id(session: str) -> str:
    return f"measures-{session.lower()}"


def download_one(doc_id: str, version: str, url: str):
    """Fetch+extract one PDF if not already snapshotted. Returns a dict:
    {version, url, snap_id, chars, cached, error}. Never raises -- a failed
    fetch is recorded, not fatal to the batch (skip-and-record)."""
    snap_id = pdf_snapshot_id(doc_id, version)
    pdf_path = SNAPSHOT_DIR / f"{snap_id}.pdf"
    txt_path = SNAPSHOT_DIR / f"{snap_id}.txt"
    if pdf_path.exists() and txt_path.exists():
        chars = len(normalize_ws(txt_path.read_text(encoding="utf-8", errors="replace")))
        return {"version": version, "url": url, "snap_id": snap_id,
                "chars": chars, "cached": True, "error": None}
    try:
        raw = fetch_bytes(url)
        if raw[:5] != b"%PDF-":
            return {"version": version, "url": url, "snap_id": snap_id,
                    "chars": 0, "cached": False, "error": "fetched content is not a PDF"}
        text = extract_pdf_text(raw)
    except Exception as e:
        return {"version": version, "url": url, "snap_id": snap_id,
                "chars": 0, "cached": False, "error": f"{type(e).__name__}: {e}"}
    pdf_path.write_bytes(raw)
    txt_path.write_text(text, encoding="utf-8")
    return {"version": version, "url": url, "snap_id": snap_id,
            "chars": len(normalize_ws(text)), "cached": False, "error": None}


# --------------------------------------------------------------------------
# Document body
# --------------------------------------------------------------------------

def build_frontmatter(m: dict, session: str, session_name: str, doc_id: str,
                      primary: dict | None, other_captured: list,
                      candidates_text: list, candidates_relating: list) -> dict:
    prefix, number = m["MeasurePrefix"], m["MeasureNumber"]
    citation = f"{session_name} {m.get('PrefixMeaning') or prefix} {number}"
    # "ORS 137.225" (citation-shaped, with a space) rather than a slug like
    # "ors-137.225": corpus_toolkit's relationship check (SLUG_RE) treats any
    # slug-shaped target as a same-corpus id that MUST resolve or CI fails;
    # a citation-shaped string is correctly treated as "not yet ingested" --
    # exactly the candidate/forward-reference semantics these are (§2.2/§5.7,
    # resolution against oregon-policy-repo is future step-7 work, not this
    # build's to assume a sibling doc-id scheme for).
    all_candidates = sorted(set(f"ORS {c}" for c in (candidates_text or candidates_relating)))

    if primary is not None:
        source_url = primary["url"]
        source_format = "pdf"
        snapshot_id = primary["snap_id"]
        source_sha256 = hash_snapshot(snapshot_id, "pdf", SNAPSHOT_DIR)
        content_mode = "verbatim"
    else:
        source_url = (f"{BASE_URL}/Measures?$filter=SessionKey eq '{session}' and "
                      f"MeasurePrefix eq '{prefix}' and MeasureNumber eq {number}")
        source_format = "json"
        snapshot_id = metadata_snapshot_id(session)
        source_sha256 = hash_snapshot(snapshot_id, "json", SNAPSHOT_DIR)
        content_mode = "summary"

    fm = {
        "schema_version": 1,
        "corpus": "oregon-legislature",
        "jurisdiction": "oregon",
        "id": doc_id,
        "title": f"{prefix} {number} ({session}): {(m.get('CatchLine') or '').strip() or '(no catchline on record)'}",
        "doc_type": "dataset_doc",
        "citation": citation,
        "issuing_body": "Oregon State Legislature",
        "source_url": source_url,
        "source_format": source_format,
        "retrieved": TODAY,
        "source_sha256": source_sha256,
        "snapshot_id": snapshot_id,
        "status": "current",
        "content_mode": content_mode,
        "last_verified": TODAY,
        "verified_by": MAINTAINER,
        "maintainer": MAINTAINER,
        "relationships": {
            "implements": [],
            "implemented_by": [],
            "references_external": all_candidates,
            "related": [],
            "supersedes": [],
        },
        "tags": ["oregon-legislature", "measure", session.lower(), prefix.lower()],
        # --- measure-specific fields (schema permits additionalProperties
        # at the document level; only the nested `relationships` object is
        # closed) ---
        "session_key": session,
        "measure_prefix": prefix,
        "measure_number": number,
        "prefix_meaning": m.get("PrefixMeaning"),
        "catch_line": m.get("CatchLine"),
        "minority_catch_line": m.get("MinorityCatchLine"),
        "measure_summary": m.get("MeasureSummary"),
        "relating_to": m.get("RelatingTo"),
        "relating_to_full": (m.get("RelatingToFull") or "").rstrip() or None,
        "at_the_request_of": m.get("AtTheRequestOf"),
        "lc_number": m.get("LCNumber"),
        "measure_created_date": m.get("CreatedDate"),
        "measure_modified_date": m.get("ModifiedDate"),
        "bill_text_versions_available": m.get("_versions_available", []),
        "bill_text_versions_captured": ([primary["version"]] if primary else []) + other_captured,
        "bill_text_embedded_version": primary["version"] if primary else None,
        "bill_text_chars": primary["chars"] if primary else None,
        "bill_text_extractable": primary is not None,
        "candidate_ors_citations": {
            "from_bill_text": [f"ORS {c}" for c in candidates_text],
            "from_relating_to_full": [f"ORS {c}" for c in candidates_relating],
        },
    }
    return fm


def dump_frontmatter(fm: dict) -> str:
    return yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=100,
                          default_flow_style=False)


def build_body(m: dict, session: str, session_name: str, doc_id: str,
               primary: dict | None, primary_text: str | None,
               other_captured: list, not_extractable_note: str | None,
               metadata_sha: str) -> str:
    prefix, number = m["MeasurePrefix"], m["MeasureNumber"]
    url_measure = (f"{BASE_URL}/Measures?$filter=SessionKey eq '{session}' and "
                  f"MeasurePrefix eq '{prefix}' and MeasureNumber eq {number}")
    catch = (m.get("CatchLine") or "").strip()
    summary = (m.get("MeasureSummary") or "").strip()
    relating = (m.get("RelatingTo") or "").strip()
    relating_full = (m.get("RelatingToFull") or "").strip()

    parts = []
    parts.append(
        "> **NON-AUTHORITATIVE — AI-friendly reference only.** This is a mirrored copy of "
        "one measure's metadata (and, where captured, its bill text) from the Oregon "
        "Legislature's OData feed. It is a point-in-time snapshot, retrieved "
        f"{TODAY} — **not** the measure's current status. For current location, "
        "history, or votes, this corpus's live proxy tools (not yet built — "
        "PHASE5-MCP-SPEC.md step 5) must be used instead of anything in this file. "
        f"Official record: `{url_measure}`.")   # code span, not an autolink: see build_provenance
    parts.append(f"\n# {prefix} {number} — {session_name} ({session})\n")

    parts.append("## At a glance\n")
    parts.append(f"- **Measure:** {m.get('PrefixMeaning') or prefix} {number}, {session_name} ({session})")
    if m.get("AtTheRequestOf"):
        parts.append(f"- **At the request of:** {m['AtTheRequestOf']}")
    if m.get("LCNumber"):
        parts.append(f"- **LC number:** {m['LCNumber']}")
    if m.get("CreatedDate"):
        parts.append(f"- **Created:** {m['CreatedDate']}")
    if m.get("ModifiedDate"):
        parts.append(f"- **Metadata last modified (upstream):** {m['ModifiedDate']}")
    versions_avail = m.get("_versions_available") or []
    parts.append(f"- **Introduced/Enrolled documents on file:** "
                 f"{', '.join(versions_avail) if versions_avail else 'none'}")
    if primary is not None and primary_text:
        parts.append(f"- **Full text below:** {primary['version']} version, "
                     f"{primary['chars']} chars extracted from the source PDF; page "
                     "furniture (left-margin line numbers, the running bill-number "
                     "header/footer) mechanically stripped -- see `clean_bill_text` in "
                     f"`src/ingest_measures.py`. Source: <{primary['url']}>.")
    parts.append("")

    parts.append("## Summary\n")
    if catch:
        parts.append(f"**Catchline:** {catch}\n")
    if relating:
        parts.append(f"**Relating to:** {relating}\n")
    if summary:
        parts.append(summary.replace("\t", " ") + "\n")
    if not (catch or summary or relating):
        parts.append("_No CatchLine, MeasureSummary, or RelatingTo on the upstream record._\n")

    if relating_full:
        parts.append(f"**RelatingToFull (verbatim upstream field):** {relating_full}\n")

    if primary is not None and primary_text:
        # NOTE: this section must contain ONLY the extracted source text -- no
        # ingest-authored caption or note -- because corpus_toolkit's
        # verify-provenance mechanically checks that every non-empty line
        # under '## Full text', normalized, appears in the committed snapshot
        # IN ORDER (anti-fabrication check). A caption line here would itself
        # have to appear in the PDF text, which it doesn't, and would fail
        # that check for every single document. See "At a glance" above for
        # the human-readable caption instead.
        parts.append("## Full text\n")
        parts.append(primary_text)
        parts.append("")
    else:
        parts.append("## Bill text availability\n")
        parts.append(not_extractable_note or
                     "No Introduced or Enrolled document is on file for this measure "
                     "in the MeasureDocuments index as of the date above (measures "
                     "commonly die before an Introduced print, or this may be an "
                     "as-filed resolution with no printed bill text).")
        parts.append("")

    # candidate ORS citations
    cand_text = candidate_ors_citations(primary_text) if primary_text else []
    cand_relating = candidate_ors_citations(relating_full) if relating_full else []
    parts.append("## Candidate ORS citations (not a finding — see PHASE5-MCP-SPEC.md §2.2)\n")
    parts.append(
        "`RelatingToFull` is a summary field, and a regex over the bill text is still "
        "mechanically derived, not a verified amend list. Both sets below are "
        "**candidates**, to be resolved against `oregon-policy-repo` in a later step "
        "(§5.7), never presented as the authoritative amend list.\n")
    parts.append(f"- From `RelatingToFull`: {', '.join('ORS ' + c for c in cand_relating) or '(none found)'}")
    if primary_text:
        parts.append(f"- From bill text ({primary['version']} version): "
                     f"{', '.join('ORS ' + c for c in cand_text) or '(none found)'}")
    parts.append("")

    parts.append("## Provenance & related versions\n")
    if primary is not None:
        parts.append(f"- **Embedded full text:** {primary['version']} version, "
                     f"retrieved {TODAY}, sha256 `{hash_snapshot(primary['snap_id'], 'pdf', SNAPSHOT_DIR)}` "
                     f"(snapshot `_meta/snapshots/{primary['snap_id']}.pdf`). Source: <{primary['url']}>.")
    for oc in other_captured:
        oc_snap = pdf_snapshot_id(doc_id, oc["version"])
        parts.append(f"- **Also captured, not embedded:** {oc['version']} version, "
                     f"sha256 `{hash_snapshot(oc_snap, 'pdf', SNAPSHOT_DIR)}` "
                     f"(snapshot `_meta/snapshots/{oc_snap}.pdf`). Source: <{oc['url']}>.")
    # The OData query goes in a CODE SPAN, not a markdown autolink. An $filter contains
    # spaces and quotes, which <...> cannot hold: a link checker truncates it at the first
    # space, requests the fragment, and gets a 400 -- which is what failed CI on PR #1
    # across all 3,758 documents. It is provenance to READ, not a link to follow, and it
    # is reproducible by hand as written.
    parts.append(f"- **Measure metadata:** retrieved {TODAY} via `{url_measure}` "
                f"(part of the batched per-session fetch), sha256 `{metadata_sha}` "
                f"of the shared session snapshot `_meta/snapshots/{metadata_snapshot_id(session)}.json`.")
    parts.append("- See [CHANGELOG](../../CHANGELOG.md).\n")

    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------
# Per-session ingest
# --------------------------------------------------------------------------

def ingest_session(session: str, limit: int | None, concurrency: int, catalog: dict,
                   appropriations_only: bool = False):
    print(f"=== {session} ===")
    session_name = fetch_session_name(session)

    measures, m_total = fetch_all(
        "Measures", f"SessionKey eq '{session}'", MEASURE_SELECT,
        "MeasurePrefix,MeasureNumber")
    docs, d_total = fetch_all(
        "MeasureDocuments", f"SessionKey eq '{session}'", DOCUMENT_SELECT,
        "MeasurePrefix,MeasureNumber,VersionDescription")

    # snapshot the batched metadata response itself -- the canonical source
    # for every measure that has no bill text, and the audit trail for every
    # measure that does (see build_frontmatter/build_body "Provenance").
    meta_snap_id = metadata_snapshot_id(session)
    meta_path = SNAPSHOT_DIR / f"{meta_snap_id}.json"
    if not meta_path.exists():
        meta_path.write_text(json.dumps(measures, indent=1, sort_keys=True), encoding="utf-8")
    metadata_sha = hash_snapshot(meta_snap_id, "json", SNAPSHOT_DIR)

    # index MeasureDocuments by measure, restricted to the two wanted versions
    by_measure = {}
    for d in docs:
        if d["VersionDescription"] not in WANTED_VERSIONS:
            continue
        key = (d["MeasurePrefix"], d["MeasureNumber"])
        by_measure.setdefault(key, {})[d["VersionDescription"]] = d["DocumentUrl"]

    measures = sorted(measures, key=lambda m: (m["MeasurePrefix"], m["MeasureNumber"]))

    # Filter BEFORE the download phase so a scoped run costs one metadata call and fetches
    # bill text only for what it keeps. The full metadata snapshot written above is
    # deliberately unfiltered — it remains the complete audit trail for the session even
    # when only a subset becomes documents.
    n_before = len(measures)
    if appropriations_only:
        measures = [m for m in measures if is_appropriation_shaped(m)]
        print(f"  appropriations-only: {len(measures)} of {n_before} measures match")

    scope = measures[:limit] if limit else measures

    out_dir = MEASURES_DIR / session
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- phase 1: download (concurrency-capped, idempotent) ----
    tasks = []  # (key, version, url)
    for m in scope:
        key = (m["MeasurePrefix"], m["MeasureNumber"])
        for version, url in by_measure.get(key, {}).items():
            tasks.append((key, version, url))

    results = {}  # (key, version) -> result dict
    downloaded = cached = failed = 0
    workers = max(1, min(concurrency, MAX_CONCURRENCY))
    print(f"  fetching up to {len(tasks)} bill-text PDF(s) for {len(scope)} measure(s) "
         f"at concurrency {workers} (introduced/enrolled only)...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(download_one, measure_doc_id(session, k[0], k[1]), v, u): (k, v)
                for (k, v, u) in tasks}
        for fut in as_completed(futs):
            key, version = futs[fut]
            r = fut.result()
            results[(key, version)] = r
            if r["error"]:
                failed += 1
                print(f"    FAILED {key[0]}{key[1]} {version}: {r['error']}")
            elif r["cached"]:
                cached += 1
            else:
                downloaded += 1
    print(f"  done in {time.time()-t0:.1f}s: downloaded {downloaded}, cached {cached}, failed {failed}")

    # ---- phase 2: write one markdown document per measure ----
    written = summary_only = extractable = not_extractable = 0
    cand_text_total = cand_relating_total = 0
    for m in scope:
        prefix, number = m["MeasurePrefix"], m["MeasureNumber"]
        key = (prefix, number)
        doc_id = measure_doc_id(session, prefix, number)
        m["_versions_available"] = sorted(by_measure.get(key, {}).keys())

        primary = None
        other_captured = []
        not_extractable_note = None
        for version in ("Enrolled", "Introduced"):
            r = results.get((key, version))
            if r is None or r["error"]:
                continue
            if r["chars"] < MIN_EXTRACT_CHARS:
                if not_extractable_note is None:
                    not_extractable_note = (
                        f"A {version} document is on file (<{r['url']}>) but extraction "
                        f"yielded only {r['chars']} chars (< {MIN_EXTRACT_CHARS}) -- "
                        "recorded as not_extractable rather than fabricated. Snapshot "
                        f"kept at `_meta/snapshots/{r['snap_id']}.pdf`.")
                continue
            if primary is None:
                primary = r
            else:
                other_captured.append(r)

        primary_text = None
        if primary is not None:
            txt_path = SNAPSHOT_DIR / f"{primary['snap_id']}.txt"
            raw_txt = txt_path.read_text(encoding="utf-8", errors="replace")
            primary_text = clean_bill_text(raw_txt, prefix, number)
            extractable += 1
        elif not_extractable_note is not None:
            not_extractable += 1
        else:
            summary_only += 1

        relating_full = (m.get("RelatingToFull") or "").strip()
        cand_text = candidate_ors_citations(primary_text) if primary_text else []
        cand_relating = candidate_ors_citations(relating_full) if relating_full else []
        cand_text_total += len(cand_text)
        cand_relating_total += len(cand_relating)

        fm = build_frontmatter(m, session, session_name, doc_id, primary,
                               [o["version"] for o in other_captured],
                               cand_text, cand_relating)
        body = build_body(m, session, session_name, doc_id, primary, primary_text,
                          other_captured, not_extractable_note, metadata_sha)
        out_path = out_dir / f"{doc_id}.md"
        out_path.write_text("---\n" + dump_frontmatter(fm) + "---\n\n" + body, encoding="utf-8")
        written += 1

        catalog.setdefault(session, {}).setdefault("measures", {})[doc_id] = {
            "path": str(out_path.relative_to(REPO_ROOT)),
            "status": ("bill_text" if primary else
                      "not_extractable" if not_extractable_note else "summary_only"),
            "bill_text_version": primary["version"] if primary else None,
            "bill_text_chars": primary["chars"] if primary else None,
            "candidate_ors_bill_text": len(cand_text),
            "candidate_ors_relating_to_full": len(cand_relating),
        }

    catalog.setdefault(session, {}).update({
        "session_name": session_name,
        "metadata_snapshot": meta_snap_id,
        "metadata_sha256": metadata_sha,
        "measures_total_odata_count": m_total,
        "measure_documents_total_odata_count": d_total,
        "measures_processed_this_run": len(scope),
        "last_run": TODAY,
    })

    print(f"  wrote {written} doc(s): {extractable} with bill text, "
         f"{not_extractable} not_extractable, {summary_only} summary-only "
         f"(no Introduced/Enrolled on file)")
    print(f"  candidate ORS citations this run: {cand_text_total} from bill text, "
         f"{cand_relating_total} from RelatingToFull")
    return {
        "measures_total": m_total, "documents_total": d_total,
        "written": written, "extractable": extractable,
        "not_extractable": not_extractable, "summary_only": summary_only,
        "downloaded": downloaded, "cached": cached, "failed": failed,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sessions", nargs="+", help="e.g. 2025R1 2024R1")
    ap.add_argument("--limit", type=int, default=None,
                    help="only process the first N measures (by prefix,number) "
                         "this session -- for proving the pipeline, NOT for full runs "
                         "(a full session is ~1.7h at concurrency 4; see PHASE5-MCP-SPEC.md §7)")
    ap.add_argument("--appropriations-only", action="store_true",
                    help="mirror only appropriation-shaped measures (~6%% of a session). "
                         "Filters on metadata before downloading any bill text, and "
                         "records scope: appropriations-only in the catalog and index.")
    ap.add_argument("--concurrency", type=int, default=MAX_CONCURRENCY,
                    help=f"PDF-download concurrency, hard-capped at {MAX_CONCURRENCY}")
    args = ap.parse_args()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    catalog = {}
    if CATALOG_PATH.exists():
        catalog = yaml.safe_load(CATALOG_PATH.read_text()) or {}

    totals = {}
    for session in args.sessions:
        totals[session] = ingest_session(session, args.limit, args.concurrency, catalog,
                                         args.appropriations_only)
        # A partially-ingested session MUST say it is partial. Without this the catalog
        # and index report a session as mirrored while holding 6% of it, and any reader —
        # human or agent — would reasonably read absence as "no such measure".
        catalog.setdefault(session, {})["scope"] = (
            "appropriations-only" if args.appropriations_only else "complete")
        if args.appropriations_only:
            catalog[session]["scope_note"] = (
                "Only measures whose catch line, relating-to or summary matched an "
                "appropriation pattern were mirrored. The session's other measures exist "
                "upstream and are NOT absent from the legislature — they are absent from "
                "this mirror. The unfiltered metadata snapshot for the session is still "
                "committed under _meta/snapshots/.")
        CATALOG_PATH.write_text(yaml.safe_dump(catalog, sort_keys=False, allow_unicode=True, width=110))

    # regenerate measures/_index.md (mirrors ingest_ors.py's statutes/_index.md)
    lines = ["# Measures — index", "",
            "Mirrored Oregon Legislature measure metadata, one file per measure, plus",
            "Introduced/Enrolled bill text where a document is on file (§2.1b).",
            "**Non-authoritative** — this is a point-in-time mirror, never the live status.", "",
            "`Scope` says whether a session is mirrored **complete** or filtered to",
            "**appropriations-only**. A filtered session holds roughly 6% of its measures:",
            "what is missing exists upstream and is absent from this mirror, not from the",
            "legislature. `Measures (odata.count)` is always the session's true size.", "",
            "| Session | Session name | Measures (odata.count) | Documents (odata.count) | Mirrored | Scope |",
            "|---|---|---|---|---|---|"]
    for session, cat in sorted(catalog.items()):
        lines.append(f"| {session} | {cat.get('session_name','')} | "
                     f"{cat.get('measures_total_odata_count','?')} | "
                     f"{cat.get('measure_documents_total_odata_count','?')} | "
                     f"{len(cat.get('measures', {}))} | "
                     f"{cat.get('scope', 'complete')} |")
    lines += ["", "Per-measure status: [`_meta/catalog/measures.yml`](../_meta/catalog/measures.yml).", ""]
    MEASURES_DIR.mkdir(parents=True, exist_ok=True)
    (MEASURES_DIR / "_index.md").write_text("\n".join(lines))

    print("\n=== summary ===")
    for session, t in totals.items():
        print(f"{session}: {t}")


if __name__ == "__main__":
    main()
