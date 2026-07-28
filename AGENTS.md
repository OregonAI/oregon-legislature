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

**Superseded 2026-07-26 — read this note before the numbered list below.**
PHASE5-MCP-SPEC.md was rewritten the same day this file was first written
(see its own §1.1): the seed-spec pure-proxy design this section originally
described turned out unable to answer "what bills are about X" (substring
search misses 69% of a real query and produces false positives on others —
see §1.1's nurse/nursery example). The spec now mandates a **hybrid**
archetype that DOES mirror measure metadata and bill text. Point 2 below
(as first written) said "do not create `measures/2025R1-HB2049.md`... that is
precisely the mirrored-records shape the seed spec rejects" — that is no
longer this corpus's design. `src/ingest_measures.py` (step 4) now writes
exactly that shape, deliberately, under `measures/<session>/`. What
survives from the two points below: entity docs are still hand-authored
API-shape documentation, never generated; and nothing under `measures/`
is hand-authored either — every file there is machine-written by
`src/ingest_measures.py`, never edited by hand. Re-running the script is
how a `measures/*.md` file changes, not a manual edit.

This corpus holds three kinds of thing, kept structurally distinct — see
README.md's table and PHASE5-MCP-SPEC.md §5.1:

1. **Entity docs** (`entities/*.md`) and, later, **cookbook entries**
   (`cookbook/*.md`) — ordinary, hand-authored files in this repo, describing
   the API's shape. `search_corpus`/`get_document` serve these through the
   unmodified FileBackend, exactly like a document-archetype corpus.
2. **Mirrored measures** (`measures/<session>/*.md`) — one file per
   `Measure` record (CatchLine/MeasureSummary/RelatingTo(Full)/identity) plus,
   where an Introduced or Enrolled `MeasureDocument` PDF exists, its extracted
   bill text under `## Full text`. Written and re-written ONLY by
   `src/ingest_measures.py <session> [<session> ...]` — never hand-edited.
   `doc_type: dataset_doc`; frontmatter's `retrieved`/`source_sha256`/
   `snapshot_id` describe whichever single source (a bill-text PDF, or the
   session's shared metadata JSON snapshot when no bill text was captured)
   backs that file's own provenance chain — see the script's module
   docstring and `build_frontmatter`'s comments for exactly which.
3. **Live records** — a measure's CURRENT status, history, or votes. Never
   mirrored (guardrail #6 below) — fetched live, per call, once a retrieval
   backend exists (step 5, not built yet).

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

**Update, step 4 (2026-07-26):** this gap is entity-doc-specific and does NOT
affect `measures/*.md` — those carry a real `snapshot_policy` (unset, i.e.
always-commit), a real `content_mode` (`verbatim` when bill text was
captured, `summary` otherwise), and a real committed snapshot
(`_meta/snapshots/<snapshot_id>.pdf`+`.txt`, or the shared per-session
`measures-<session>.json`). `corpus-verify-provenance` runs a genuine,
non-trivial check against them today (mechanical full-text-in-order
verification against the snapshot, coverage ratio) — confirmed manually
against the 20-measure proof run (20/20 full-text sections verified,
coverage 96–100%). It is not yet wired into `ci.yml` (still commented out
there, entity-doc-scoped reasoning only) — enabling it now would exercise
real checks for `measures/` while remaining a no-op for `entities/`, but that
edit to `ci.yml` was left to the operator rather than made by this build.

## Step-3/step-4 scope note

Step 3 (PHASE5-MCP-SPEC.md §9) was documentation-only: the repo skeleton and
the three entity docs. **Step 4 (2026-07-26) added `src/ingest_measures.py`**
— the mirror pipeline for `measures/<session>/*.md` — per the spec rewrite
(§1.1). This is the only Python this repo has; it was proven end-to-end with
`--limit 20` against 2025R1 (frontmatter validated, provenance mechanically
verified, pagination proven against `odata.count`, re-run confirmed to
download nothing new) but **a full-session run was deliberately NOT
executed** — §7's politeness guardrail estimates ~1.7h at the mandated
concurrency-4 cap, and running it is explicitly left to a human operator,
not automated by this build.

Still not built: `src/odata_backend.py` (step 5, the live proxy half —
`measure_status`/`measure_votes`/`scheduled_for`), `src/citations.py` (step 6,
"HB 2049" parsing with session inference), cross-corpus ORS resolution
(step 8), schema-drift CI + real cookbook entries (step 9). Building those
ahead of the toolkit changes they may depend on risks disagreeing with what
that work actually ships — don't get ahead of the build order in §9/§10 of
PHASE5-MCP-SPEC.md.

## Found a bug you are not fixing right now? Open an issue. Period.

This is not optional and has no size threshold.

If you discover a defect and do not fix it in the change you are working on, **open a
GitHub issue before you finish the task**. Not a note in the commit message, not a
paragraph in the PR body, not a line in your summary to the user. Those are not a work
queue — nobody greps closed PRs six months later, and the next agent rediscovers the same
bug from scratch, usually the expensive way.

This applies to every one of these, not just crashes:

- a check that passes without checking anything
- a documented command, flag, or path that does not exist or does not work
- a claim in a README, docstring, or catalog note that is no longer true
- data known to be wrong, stale, or incomplete
- a guard that cannot fire, or fires on the wrong condition
- something you worked around instead of fixing

**File it in the repo that owns the fix, which may not be the repo you are in.** A parser
defect here, a registry gap in a sibling corpus, and a validator gap in `corpus-toolkit`
are three different issues in three different repos. Say plainly in each which repo the
work belongs to.

An issue must answer four things, because an issue that only says "X is broken" costs the
next person the whole investigation again:

1. **What is wrong** — the specific behaviour, not a category
2. **How it was found** — the command, the data, the failing case
3. **What it breaks** — who or what gets a wrong answer, and how silently
4. **What would fix it**, or what still needs measuring before anyone can know

Prefer counts and reproductions over adjectives. "126 appropriations unjoined, of which 59
are an extraction gap and 41 are correct" is actionable; "agency matching needs work" is
not, and will be re-derived by someone else.

If you genuinely cannot open one — no network, no permission — say so explicitly in your
final message to the user and hand them the text to file. Silently dropping it is the one
outcome that is never acceptable.

## Workflow

Discovery → human-approved source manifest → ingestion → human-reviewed PR.
See toolkit `docs/replication-guide.md`.
