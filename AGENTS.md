# AGENTS.md — Oregon Legislature — Measures, History, and Sessions (OData)

Corpus of the OregonAI civic corpus platform. Archetype: **api**.
Read `_meta/corpus.yml` for configuration; the platform rules live in
OregonAI/corpus-toolkit `docs/`.

## Purpose

Non-authoritative, AI-friendly description of the Oregon Legislature's public
OData feed (`https://api.oregonlegislature.gov/odata/odataservice.svc/`).
Never a source of truth — every answer about a live record (a bill's status, a
vote) must carry the executed query and the time it ran, and must never be
served from anything cached without that timestamp attached.

## What this corpus is NOT (read this before adding anything)

This is not a document-mirror corpus. It holds two kinds of thing, on purpose
kept structurally distinct — see README.md's table and PHASE5-MCP-SPEC.md
§5.1:

1. **Entity docs** (`entities/*.md`) and, later, **cookbook entries**
   (`cookbook/*.md`) — ordinary files in this repo, describing the API.
   `search_corpus`/`get_document` serve these through the unmodified
   FileBackend, exactly like a document-archetype corpus.
2. **Live records** — an actual measure, vote, or session. These are never
   ingested as files here. Fetched live, per call, once a retrieval backend
   exists (step 4). Do not create `measures/2025R1-HB2049.md` or anything
   resembling a per-record snapshot: that is precisely the "mirrored records"
   shape the seed spec rejects for this corpus.

**id namespace note.** PHASE5-MCP-SPEC.md §5.1 illustrates MCP-facing ids as
`entity:measures` and `measure:2025R1/HB2049`. Those colon-containing forms
are NOT valid frontmatter `id` values — the schema pattern
(`^[a-z0-9][a-z0-9._-]+$`) has no room for a colon, and the toolkit's own
validator requires `id` to equal the filename stem. Frontmatter ids in this
repo stay plain slugs (`measures`, `measure-history-actions`,
`legislative-sessions`); any `entity:`/`measure:` prefixing is a tool-surface
convention for whatever code builds MCP-facing ids from these files (step 4/5
work), not something to encode into the files themselves.

## Hard rules (anti-fabrication)

1. Never write content that does not exist in the pinned source. For a live
   API, "the pinned source" means an actual response you fetched and can
   quote — not model knowledge of how OData "usually" behaves, and not this
   API's presumed similarity to any other government OData feed. Could not
   reach/parse it → insert `<!-- TODO: human verification required -->` and
   stop.
2. **Field types and shapes come from `$metadata` and real fetched records,
   never from inference.** If a field's nullability, type, or behavior was
   not observed, say so explicitly ("not verified") rather than presenting a
   plausible guess as fact.
3. **A single observed record is a claim about that record, not the entity in
   general.** "Null on the record examined" — never "always null" or
   "unused" — unless multiple records confirm it, and even then, say how
   many.
4. Third-party copyrighted material: summary + official link only. (Not
   generally applicable here — entity docs describe API shape, not bill
   text — but applies if any future cookbook entry quotes measure text at
   length.)
5. Never invent or infer a citation. Unresolvable → say so.
6. **Live-data answers (this whole archetype) must carry the executed query
   and the `executed_at` timestamp** — PHASE5-MCP-SPEC.md §5.3. A timeout or
   an unreachable API is `upstream_status: "unavailable"`, never silently
   reported as "no such measure" — "could not check" and "not there" are
   different answers, and conflating them is the one failure mode this whole
   design exists to prevent (§3.2, §5.3).
7. **`RelatingToFull`-derived bill→statute edges are candidates, never
   findings** (PHASE5-MCP-SPEC.md §2.3). Label them as such, with the source
   quote, every time.
8. **No raw user OData ever reaches `$filter`.** Any future `query_dataset`
   implementation takes an entity name plus named, validated filters — never
   user text spliced into a query string (§7 guardrail #1).
9. **Client-side result cap, always enforced, always stated.** The server
   returns up to 2,000 rows with no `nextLink` — it will not protect you.
   Any capped result sets `truncated: true` explicitly; silent truncation
   reads as "that's all there is" (§7 guardrail #2).
10. All changes via PR. Do not set `last_verified`/`verified_by` on entity
    docs casually — it means "I re-checked this doc's fields against a live
    `$metadata`/record fetch on this date," not "I edited prose."
11. Update this knowledge body's CHANGELOG.md in the same PR as content
    changes.

## A known toolkit gap this build hit (step 3, 2026-07-26)

`corpus_toolkit`'s `verify-provenance` reusable workflow (as of tagged release
v1.2.0 / commit `2fcd796`) has a comment claiming "API/hybrid: verify entity
docs against live API schema (drift check)" — but its actual implementation
(`corpus_toolkit/validate/provenance.py`, `check_file()`) has no branch for
`doc_type: entity_doc` at all. Unconditionally, for every content file, it
requires a committed snapshot file at `_meta/snapshots/<id>.<source_format>`
unless `snapshot_policy: hash-only` is set — there is no entity-doc-aware
exemption. Every entity doc in this repo therefore carries
`snapshot_policy: hash-only` with no committed `.txt`/source file and no
`content_mode`, which is the only existing lever that avoids a guaranteed
"missing source snapshot" CI failure for a doc_type this CLI does not yet
understand. This is a real toolkit limitation, not a workaround to be proud
of — the schema-drift job the workflow's own header describes (per-entity
`live_schema_hash` comparison against a fresh `$metadata` fetch) does not
exist in code yet. That is real step 8 work, in the toolkit, not this repo's
Python (which this build deliberately does not touch — see below).

## Step-3 scope note

This build (step 3 of PHASE5-MCP-SPEC.md §9) is documentation-only: the repo
skeleton and the three entity docs, so that `search_corpus`/`get_document`
find them through the unmodified FileBackend machinery — no new code. No
`src/odata_backend.py`, no `src/citations.py`, no cookbook entries. Do not
add Python to this repo to "finish the job early" — later steps depend on
toolkit changes (the `RetrievalBackend` protocol, response envelope) that are
tracked separately in `corpus_toolkit`, and building ahead of them risks
disagreeing with what that toolkit work actually ships.

## Workflow

Discovery → human-approved source manifest → ingestion → human-reviewed PR.
See toolkit `docs/replication-guide.md`.
