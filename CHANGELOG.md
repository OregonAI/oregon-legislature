# Changelog — Oregon Legislature — Measures, History, and Sessions (OData)

Keep a Changelog format; ISO dates. Change types: Added, Source-Updated,
Superseded, Repealed, Removed, Verified, Fixed, Security.
Repo-curation dates only — official effective dates live in frontmatter.

## [Unreleased]

### Added
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
