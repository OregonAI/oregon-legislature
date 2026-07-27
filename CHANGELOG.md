# Changelog — Oregon Legislature — Measures, History, and Sessions (OData)

Keep a Changelog format; ISO dates. Change types: Added, Source-Updated,
Superseded, Repealed, Removed, Verified, Fixed, Security.
Repo-curation dates only — official effective dates live in frontmatter.

## [Unreleased]

### Added
- 2026-07-26 — `src/ingest_measures.py` (PHASE5-MCP-SPEC.md step 4): the
  mirror pipeline. Fetches `Measures` (identity + CatchLine/MeasureSummary/
  RelatingTo(Full)) and `MeasureDocuments` for a session, both fully
  paginated with `$skip` and verified against `odata.count` (the server
  emits no `nextLink`); downloads Introduced/Enrolled bill-text PDFs only,
  concurrency-capped at 4; extracts text with `pypdf` (no `pdftotext` binary
  in this environment — PHASE5-MCP-SPEC.md §2.1b names both as acceptable);
  writes one `measures/<session>/measure-<session>-<prefix><number>.md` per
  measure, `doc_type: dataset_doc`, `source_sha256` always via
  `corpus_toolkit.repo.hash_snapshot()`. Candidate ORS citations extracted
  by regex from both `RelatingToFull` and the bill text itself, recorded as
  candidates (§2.2), never findings.
- 2026-07-26 — `measures/2025R1/` — **20-measure proof run** (HB 2001–2020,
  `--limit 20`), not a full session (deliberately — see AGENTS.md). All 20
  have Introduced and/or Enrolled bill text; 28 PDFs downloaded in 48.8s at
  concurrency 4. `corpus-validate-frontmatter` and `corpus-verify-provenance`
  both pass (20/20 full-text sections mechanically verified against their
  PDF snapshots, in-order, 96–100% coverage); re-running the same command
  downloads zero PDFs (28/28 cached) and reproduces byte-identical output.
  `measures/2024R1/` — a 3-measure slice (HB 4001–4003, `--limit 3`) added
  solely to prove multi-session argv actually works end to end (a smaller
  session: 291 measures/1 page, 808 documents/1 page, vs. 2025R1's
  3466/2 pages and 6178/4 pages) — also not a full session.
  `_meta/corpus.yml` `content_roots` gained a `measures` entry
  (`doc_type: dataset_doc`). `requirements.txt` added (`pypdf`,
  `corpus-toolkit`). `AGENTS.md`/README.md/`llms.txt` updated — their
  original "this corpus does not mirror records" framing was written under
  the seed-spec pure-proxy design PHASE5-MCP-SPEC.md's own §1.1 superseded
  the same day; see AGENTS.md's "Superseded 2026-07-26" note.
  **Not done in this change:** a full-session run (~1.7h at the mandated
  concurrency cap — left to a human operator); flipping
  `_meta/corpus.yml`'s `archetype` to `hybrid` (step 3b, a separate
  prerequisite); wiring `verify-provenance` into `ci.yml` (currently
  commented out for entity-doc reasons that no longer apply to `measures/`,
  but enabling it was left to the operator).
- 2026-07-26 — Repo skeleton instantiated from `corpus-template`
  (PHASE5-MCP-SPEC.md step 3): `_meta/corpus.yml` (`archetype: "api"`),
  README/AGENTS/DISCLAIMER/CONTRIBUTING/STATUS/llms.txt, CI workflows,
  CODEOWNERS.
- 2026-07-26 — 3 entity docs added under `entities/`: `measures`,
  `measure-history-actions`, `legislative-sessions` — one per OData entity
  set (`Measures`, `MeasureHistoryActions`, `LegislativeSessions`). Fields,
  types, keys, and relationships read from a live `$metadata` fetch; sample
  values read from live records (`Measures` and `MeasureHistoryActions`
  filtered to HB 2049 / `2025R1`; `LegislativeSessions` unfiltered,
  `$top=5`). 5 total API calls made (one `$metadata` call failed with HTTP
  415 on a JSON `Accept` header and was retried without it — see
  `entities/measures.md` "Quirks"). Each doc's `live_schema_hash` and the
  exact method to recompute it are recorded in its own "Verification"
  section. `last_verified`/`verified_by` ARE set here (unlike the
  document-archetype convention of leaving them for human review at
  approval) because for `doc_type: entity_doc` they specifically mean "the
  fields below were checked against a live schema fetch on this date" —
  the fetch itself, not a curatorial edit, is what they attest to.
- 2026-07-26 — `cookbook/README.md` added: explains what will live in
  `cookbook/` and why nothing does yet (no query has been executed against
  the live API for this purpose). `cookbook/` is deliberately not yet a
  `content_roots` entry in `_meta/corpus.yml`.
- 2026-07-26 — `AGENTS.md` records a real toolkit gap hit during this build:
  `corpus_toolkit`'s `verify-provenance.yml` (v1.2.0) has no `entity_doc`-
  aware branch despite its own header comment claiming API-archetype
  support; entity docs use `snapshot_policy: hash-only` as the only existing
  lever that avoids a guaranteed CI failure, not because a large source file
  was deliberately left uncommitted.
