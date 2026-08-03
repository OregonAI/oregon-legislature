---
schema_version: 1
corpus: "oregon-legislature"
jurisdiction: "oregon"
id: legislative-sessions
title: "Entity doc: LegislativeSessions"
doc_type: entity_doc
citation: "Oregon Legislature OData API — LegislativeSessions entity set"
issuing_body: "Oregon State Legislature"
source_url: "https://api.oregonlegislature.gov/odata/odataservice.svc/LegislativeSessions"
source_format: odata
snapshot_policy: hash-only
status: current
last_verified: ''
verified_by: ""
maintainer: "@dzinck"
live_schema_hash: "925869e2e18b43ee51418af08d1b4ee60a68dca5e88ef49d91584ed21a844bf8"
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
- sessions
---

> **NON-AUTHORITATIVE — AI-friendly reference only.** This describes the shape of
> a live API, not a snapshot of its data. It is not the official legislative
> record. Always fetch the live record for a current answer:
> <https://api.oregonlegislature.gov/odata/odataservice.svc/LegislativeSessions>
> (schema last checked 2026-07-26).

# LegislativeSessions

OData entity set `LegislativeSessions` (entity type
`State.Or.Leg.API.OData.LegislativeSession`) — the session calendar (regular,
special, and interim sessions) that every `Measure` and `MeasureHistoryAction`
is scoped under via `SessionKey`. This is the entity `resolve_citation`'s
ask-or-default session inference (PHASE5-MCP-SPEC.md §5.4, R6) will need to
read once implemented (step 5) — specifically the `DefaultSession` field, see
"Quirks" below. Not implemented here; this doc only records the shape.

## At a glance

7 fields (verified 2026-07-26 against `$metadata` and 5 live records — the
first 5 rows returned with no `$filter`/`$orderby`, `$top=5`). Every session
this API knows about, going back to at least 2007 (the oldest of the 5 rows
examined is `SessionKey: "2007I1"`, a 2007-2008 interim session).

## Entity reference

_Everything below is nested under one heading, deliberately: `FileBackend`'s
FTS index only extracts body text from a `## Full text` section (verbatim
document archetype convention) or, failing that, `## Key provisions` — see
`corpus_toolkit/mcp/backends.py`. An entity doc has no verbatim source to
quote, but the facts below are exactly what a `search_corpus` query should be
able to find, so they live here rather than under un-indexed top-level
headings._

### Key

Single field: **`SessionKey`** (`Edm.String`, max length 10, not nullable).
Observed values follow a `<year><type><n>` pattern: `2007I1` (interim),
`2007R1` (regular), `2008S1` (special), `2009I1`, `2009R1` — i.e. `I` =
interim, `R` = regular, `S` = special, in the 5 rows examined. This is a
pattern observed across 5 rows, not a documented format guarantee from the API
itself — PHASE5-MCP-SPEC.md's own worked example, `2025R1`, is consistent with
it.

### Fields

Types and nullability are the literal `$metadata` declaration (a `Property`
with no `Nullable` attribute defaults to nullable per the CSDL spec).
"Observed" summarizes the 5 rows examined (`$top=5`, no filter, fetched
2026-07-26) — these are the 5 *oldest* sessions the API returns in default
order, not a representative or recent sample.

| Field | Type | Nullable | Observed across the 5 rows examined |
|---|---|---|---|
| `SessionKey` | Edm.String (max 10) | no | `"2007I1"`, `"2007R1"`, `"2008S1"`, `"2009I1"`, `"2009R1"` |
| `SessionName` | Edm.String (max 30) | no | e.g. `"2007 - 2008 Interim"`, `"2007 Regular Session"`, `"2008 Special Session"` |
| `BeginDate` | Edm.DateTime (precision 3) | no | non-null on all 5, e.g. `"2007-06-30T00:00:00"` |
| `EndDate` | Edm.DateTime (precision 3) | yes | **null on the `2008S1` row examined**; non-null on the other 4 |
| `CreatedDate` | Edm.DateTime (precision 3) | no | non-null on all 5 |
| `ModifiedDate` | Edm.DateTime (precision 3) | yes | non-null on all 5 examined, and identical (`"2025-12-12T09:32:00"`) across all 5 — see "Quirks" |
| `DefaultSession` | Edm.Boolean | no | `false` on all 5 rows examined (all 5 are historical sessions from 2007-2009; the current/default session was not in this sample — see "Quirks") |

Field count: **7**.

### Relationships (OData navigation properties, from `$metadata`)

| Navigation property | Target entity set | Cardinality (inferred, not schema-asserted) |
|---|---|---|
| `Measures` | `Measures` | one LegislativeSession -> many Measures |
| `Committees` | `Committees` | one LegislativeSession -> many Committees |
| `Legislators` | `Legislators` | one LegislativeSession -> many Legislators |
| `ConveneTimes` | `ConveneTimes` | one LegislativeSession -> many ConveneTimes |
| `FloorSessionAgendaItems` | `FloorSessionAgendaItems` | one LegislativeSession -> many |
| `FloorLetters` | `FloorLetters` | one LegislativeSession -> many |
| `CommitteeMembers` | `CommitteeMembers` | one LegislativeSession -> many |

No `$expand` call was made against any of these — this table is the declared
shape from `$metadata` only. Only the `Measures` edge is in scope for this
build (the other two entity docs shipped here); the rest are recorded because
they are in `$metadata`, not because they have been explored.

### Quirks (measured, this build — 2026-07-26)

- **`DefaultSession` was not observed `true` on any row in this sample.** The
  call made (`$top=5`, no filter) returned the 5 *oldest* sessions the service
  knows about (2007-2009); it did not verify that exactly one row has
  `DefaultSession: true` somewhere in the full set, or which session that is.
  This matters directly for the future ask-or-default session-inference logic
  (PHASE5-MCP-SPEC.md §5.4, R6): that logic will need to query for
  `DefaultSession eq true` (or fetch a larger page and find it) rather than
  assume a value — it has not been confirmed to exist in the data at all by
  this build.
- **All 5 `ModifiedDate` values were identical** (`"2025-12-12T09:32:00"`)
  across sessions spanning 2007-2009 — i.e. rows describing sessions that
  ended over a decade ago all show the same recent modification timestamp.
  This is consistent with a bulk backend update/reindex touching every row on
  that date (a plausible, unconfirmed explanation) rather than any of these
  specific historical sessions having been individually edited then. Recorded
  as observed, not explained.
- No `$orderby` was passed; the 5 rows came back in ascending `SessionKey`
  order. As with the `MeasureHistoryActions` doc, this is an observation from
  one call, not a documented guarantee — a consumer needing a specific order
  should pass `$orderby` explicitly.
- This call also took ~15.1s despite `$top=5` and no filter — consistent with
  the same latency quirk noted on the other two entity docs; recorded, not
  reconciled with PHASE5-MCP-SPEC.md's ~5.4s median figure.

### Verification

- **Method**: `curl -H "Accept: application/json"` against
  `https://api.oregonlegislature.gov/odata/odataservice.svc/$metadata` (fetched
  without the JSON `Accept` header — see `entities/measures.md` "Quirks" for
  why) for field names/types, and `LegislativeSessions?$top=5` for five live
  records. Both calls made 2026-07-26.
- **`live_schema_hash` computation** (identical method to the other entity
  docs, so the step-8 drift job can reproduce it the same way for every
  entity): from `$metadata`, take the `<EntityType Name="LegislativeSession">`
  element's direct `<Property>` children only (navigation properties
  excluded). Build `"Name:Type"` for each, sort ascending by field name, join
  with `|`, sha256 hex digest of the UTF-8 bytes. `MaxLength`/`Precision`/
  `Nullable` are **not** part of the hash.
- `live_schema_hash: 925869e2e18b43ee51418af08d1b4ee60a68dca5e88ef49d91584ed21a844bf8`
- **Not verified**: whether any session has `DefaultSession: true` (not
  observed in this 5-row, oldest-first sample); the current/most-recent
  session's `SessionKey` (2025R1 is used throughout this build only because
  PHASE5-MCP-SPEC.md's own worked examples use it, not because this doc
  queried for it); behavior of `$filter=DefaultSession eq true` or any
  `$orderby` (neither was called).
