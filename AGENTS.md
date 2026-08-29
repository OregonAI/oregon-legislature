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

## Found a defect? Fix it. Filing an issue is the exception, and it has a cost.

**The default is to fix it in the change you are already making.** You are in the file with
the context loaded, which is the cheapest this fix will ever be. Filing an issue converts a
ten-minute fix into a future session that has to rebuild everything you currently know.

**Open an issue only when one of these is true:**

1. **It needs a decision you are not allowed to make** — a judgement about what the corpus
   means, a trade-off with a real cost, anything a grilling session would have put to the
   operator. Label it `ready-for-human`.
2. **It is large enough to need its own review** — if fixing it would make this change's diff
   hard for a reviewer to follow, it is separate work.
3. **It is in a file this change does not touch**, and reaching into it would widen the change
   beyond what its own review covers.

**If none of those is true, fix it now.** "I noticed it while doing something else" is not a
reason to defer; it is the reason it is cheap.

### An issue must name its trigger

Every issue states **what would make this matter** — the condition under which it stops being
latent. "Nothing currently escapes this" with no trigger is not a ticket. It is a comment at
the site, where the next person who can act on it will actually be standing.

**A comment in the code beats a ticket in a queue** whenever the person who would fix it is
the next person reading that code. Reserve the queue for work that has to be found by someone
who is *not* already in that file.

### Review findings are not issues

A code-review finding applied in the same change is already tracked by that review. Do not
also file it. An issue opened and closed within the hour adds a row to the backlog and tells
nobody anything.

### At most two issues per task

If you found more than two things worth another person's attention, the finding is that this
module needs work — and that is **one** issue naming the pattern, not five naming instances.
Ranking is the point: the third-most-important thing you noticed is usually a comment.

### Why this replaced "open an issue, period"

Measured in `executive-regulatory-frameworks` on 2026-08-29: **49 issues opened in two days,
20 closed, the backlog 19 → 48.** Of the 20 closures, 8 were review findings filed and fixed
inside the same hour — tracked already, and pure ceremony. Of the 29 left open, 3 needed a
human decision and roughly 12 were things the agent could have fixed while it was already in
the file.

The old rule's justification was that "nobody greps closed PRs six months later." True — and
nobody greps a 48-issue backlog either. A backlog nobody works is not a record; it is where a
defect goes to be forgotten with a clear conscience, and it buries the few issues that
genuinely need a person.

These all count as a defect, not just crashes:

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

## OCR — the default stack is tesseract + PaddleOCR

When a source PDF has no text layer (`0 chars extracted`), this is the stack. Do not
hand-roll a renderer, and do not substitute a hosted or generative model.

**Primary: `ocrmypdf` (tesseract).** Writes a text layer into a COPY beside the
original — never over it, so `source_sha256` keeps hashing the bytes upstream served.

```
ocrmypdf -l eng --optimize 0 --output-type pdf --rotate-pages --deskew in.pdf out.pdf
```

**Cross-check: PaddleOCR (PP-OCRv6).** Reads the ORIGINAL scan, so the two engines
share nothing but the pixels — corroborating against the other engine's output is an
echo, not evidence. Measured word-sequence agreement across the six oregon-kpm scans:
**0.82–0.93**, every one clearing the 0.80 bar.

**Tiebreaker: docTR (DBNet + CRNN).** Not the default — it agrees with tesseract less
than Paddle does on every document (0.75–0.86), so it would lower every score. Reach
for it when the primary pair disagrees, and when orientation is in doubt: it straightens
pages itself and was the only engine that read a 180°-rotated scan correctly with no
document-specific retry.

**Every engine needs its orientation handling verified separately**, or the
corroboration check quietly becomes an orientation check. Measured: with Paddle's
`use_doc_orientation_classify=False`, a rotated scan scored **0.050** against tesseract;
with it on, **0.929**. Same page, same engines. Tesseract needs
`--rotate-pages-threshold 0` on that document — at default OSD confidence it leaves page
1 upside down and emits `:Peusiiqnd` for `Published:`, thousands of characters of
confident garbage that passes every length check.

**`pdftotext -layout` (poppler) is for a different fault** — a text layer that extracts
letter-spaced (`A c t u a l 9 3 %`) or in column rather than reading order. That is not
a scan; OCR is the wrong tool, and re-extracting with another engine recovers the real
spacing instead of guessing it back.

### Promotion into `## Full text`

Governed by the **two-engine rule** in `oregon-policy-repo/AGENTS.md`. A single
engine's output is never promotable. Reference implementations:
`oregon-policy-repo/src/ocr_fallback_eo.py` and `oregon-kpm/src/ocr_corroborate.py`.

Two traps worth inheriting, both found by measurement:

* **Never build the dictionary from a corpus that already contains OCR output.** The
  errors enter the vocabulary that judges them — `pernitted` becomes a recognised word —
  and every OCR'd document scores 100% dictionary-recognizable however badly it was
  read. A gate that cannot fail is worse than no gate, because it looks like evidence.
  Exclude `text_source: ocr` documents when building the vocabulary.
* **Score the figures separately from the words.** The reference metric counts
  `[a-z]{2,}` and so excludes every digit. On the oregon-kpm scans, word agreement ran
  88–98% while agreement on the FIGURES ran **69–85%** — digits are exactly where two
  engines diverge, and the headline number hides it. In any corpus whose payload is
  numbers, report both; a low figure score means human review, not rejection.

**OCR text is a machine reading of an image, not the source's own text.** Agreement is
evidence the words are on the page. It is NOT evidence they were read correctly, and two
engines can misread the same smudged digit identically. Record the engines, both
agreement rates and the dictionary ratio in `conversion_notes`, end with
`NOT human-verified`, and warn the reader in the document body.

## Agent skills

### Issue tracker

GitHub Issues on `OregonAI/oregon-legislature`, via the `gh` CLI. See
`docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles, each label string equal to its name. See
`docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` and `docs/adr/` at the repo root. See
`docs/agents/domain.md`.
