---
schema_version: 1
corpus: "oregon-legislature"
jurisdiction: "oregon"
id: measure-history-actions
title: "Entity doc: MeasureHistoryActions"
doc_type: entity_doc
citation: "Oregon Legislature OData API — MeasureHistoryActions entity set"
issuing_body: "Oregon State Legislature"
source_url: "https://api.oregonlegislature.gov/odata/odataservice.svc/MeasureHistoryActions"
source_format: odata
snapshot_policy: hash-only
status: current
last_verified: ''
verified_by: ""
maintainer: "@dzinck"
live_schema_hash: "1b2eef0c802d1d83ea028145e8c75951be27e6269e5fe0069fb4fcf73bc3cb03"
relationships:
  implements: []
  implemented_by: []
  references_external: []
  related:
  - measures
  supersedes: []
tags:
- oregon-legislature
- odata
- entity-doc
- measure-history
- bill-status
---

> **NON-AUTHORITATIVE — AI-friendly reference only.** This describes the shape of
> a live API, not a snapshot of its data. It is not the official legislative
> record. Always fetch the live record for a current answer:
> <https://api.oregonlegislature.gov/odata/odataservice.svc/MeasureHistoryActions>
> (schema last checked 2026-07-26).

# MeasureHistoryActions

OData entity set `MeasureHistoryActions` (entity type
`State.Or.Leg.API.OData.MeasureHistoryAction`) — one row per procedural action
taken on a measure ("First reading", "Referred to Judiciary", "In committee
upon adjournment", ...). This is the entity that will back the `measure_history`
convenience tool described in PHASE5-MCP-SPEC.md §5.4 — the "what happened to
HB NNNN" answer — once `src/odata_backend.py` exists (step 4/6). Not
implemented here; this doc only records the entity's shape.

## At a glance

11 fields (verified 2026-07-26 against `$metadata` and three live records: the
first, second, and third history rows for HB 2049 / `2025R1`, fetched with
`$top=3`, no `$orderby` applied). Each row belongs to exactly one `Measure` via
`(SessionKey, MeasurePrefix, MeasureNumber)` — the same triple that composes
`Measure`'s own key, but here it is a plain (non-key) foreign reference, not
part of *this* entity's key.

## Entity reference

_Everything below is nested under one heading, deliberately: `FileBackend`'s
FTS index only extracts body text from a `## Full text` section (verbatim
document archetype convention) or, failing that, `## Key provisions` — see
`corpus_toolkit/mcp/backends.py`. An entity doc has no verbatim source to
quote, but the facts below are exactly what a `search_corpus` query should be
able to find, so they live here rather than under un-indexed top-level
headings._

### Key

Single field: **`MeasureHistoryId`** (`Edm.Int32`, not nullable). The three
records examined had ids `614013`, `616222`, `660816` — non-sequential-looking
gaps, consistent with a shared id sequence across all measures' history rows
rather than one counter per measure (not confirmed against another measure;
inferred from the gap sizes on a single measure's own rows).

### Fields

Types and nullability are the literal `$metadata` declaration (a `Property`
with no `Nullable` attribute defaults to nullable per the CSDL spec). "Observed"
summarizes the three rows examined (HB 2049 / `2025R1`, `$top=3`, fetched
2026-07-26) — three rows, not a corpus-wide claim.

| Field | Type | Nullable | Observed across the 3 rows examined |
|---|---|---|---|
| `MeasureHistoryId` | Edm.Int32 | no | `614013`, `616222`, `660816` |
| `SessionKey` | Edm.String (max 10) | no | `"2025R1"` on all 3 |
| `MeasurePrefix` | Edm.String (max 3) | no | `"HB"` on all 3 |
| `MeasureNumber` | Edm.Int32 | no | `2049` on all 3 |
| `Chamber` | Edm.String (max 1) | no | `"H"` on all 3 |
| `ActionDate` | Edm.DateTime (precision 3) | no | e.g. `"2025-01-13T08:01:32"` |
| `ActionText` | Edm.String (max 1000) | yes | non-null on all 3, e.g. `"First reading. Referred to Speaker's desk."`, `"Referred to Judiciary."`, `"In committee upon adjournment."` |
| `VoteText` | Edm.String (max 3000) | yes | **null on all 3 rows examined** — none of the three sampled actions was a recorded vote |
| `CreatedDate` | Edm.DateTime (precision 3) | no | non-null on all 3 |
| `ModifiedDate` | Edm.DateTime (precision 3) | yes | **null on all 3 rows examined** |
| `PublicNotification` | Edm.Boolean | yes | `false` on all 3 |

Field count: **11**.

### Relationships (OData navigation properties, from `$metadata`)

| Navigation property | Target entity set | Cardinality (inferred, not schema-asserted) |
|---|---|---|
| `Measure` | `Measures` | many MeasureHistoryActions -> one Measure, via `(SessionKey, MeasurePrefix, MeasureNumber)` |
| `MeasureVotes` | `MeasureVotes` | one MeasureHistoryAction -> many vote rows (relevant when `VoteText` is non-null; not observed on the 3 rows examined here) |

No `$expand` call was made against either navigation property — this table is
the declared shape from `$metadata` only.

### Quirks (measured, this build — 2026-07-26)

- `VoteText` and `ModifiedDate` were **both null on all three rows examined**.
  For `VoteText` this is plausibly because none of the three actions sampled
  was itself a floor/committee vote (the action text is procedural: first
  reading, referral, adjournment) — a vote-carrying `MeasureHistoryAction`
  would be expected to populate it, but that was not observed here. For
  `ModifiedDate`, all three rows show a populated `CreatedDate` but a null
  `ModifiedDate` — consistent with "never revised since creation" for these
  specific rows, not evidence that the field is unused in general.
- The default (no `$orderby`) ordering across the 3 rows returned matched
  `ActionDate` ascending (2025-01-13, 2025-01-17, 2025-06-27) — but this was
  observed on one `$filter`+`$top=3` call, not confirmed as a documented or
  guaranteed server default. Any consumer that needs a specific order should
  pass `$orderby` explicitly rather than rely on this observation.
- This call, like the `Measures` single-record call, took ~15.2s despite
  `$top=3` — see the same latency quirk noted in `entities/measures.md`.

### Verification

- **Method**: `curl -H "Accept: application/json"` against
  `https://api.oregonlegislature.gov/odata/odataservice.svc/$metadata` (fetched
  without the JSON `Accept` header — see `entities/measures.md` "Quirks" for
  why) for field names/types, and
  `MeasureHistoryActions?$filter=SessionKey eq '2025R1' and MeasureNumber eq
  2049&$top=3` for three live records. Both calls made 2026-07-26.
- **`live_schema_hash` computation** (identical method to the other entity
  docs, so the step-8 drift job can reproduce it the same way for every
  entity): from `$metadata`, take the `<EntityType Name="MeasureHistoryAction">`
  element's direct `<Property>` children only (navigation properties excluded).
  Build `"Name:Type"` for each, sort ascending by field name, join with `|`,
  sha256 hex digest of the UTF-8 bytes. `MaxLength`/`Precision`/`Nullable` are
  **not** part of the hash.
- `live_schema_hash: 1b2eef0c802d1d83ea028145e8c75951be27e6269e5fe0069fb4fcf73bc3cb03`
- **Not verified**: whether `VoteText`/`ModifiedDate` are ever non-null on any
  record (not observed in this 3-row sample); the entity's behavior under
  `$orderby`, `$expand`, or `$inlinecount` (none called against this entity
  set); whether `MeasureHistoryId` is genuinely a single shared sequence across
  all measures (inferred from gap sizes on one measure's rows only, not
  cross-checked against a second measure).
