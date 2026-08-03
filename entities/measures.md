---
schema_version: 1
corpus: "oregon-legislature"
jurisdiction: "oregon"
id: measures
title: "Entity doc: Measures"
doc_type: entity_doc
citation: "Oregon Legislature OData API — Measures entity set"
issuing_body: "Oregon State Legislature"
source_url: "https://api.oregonlegislature.gov/odata/odataservice.svc/Measures"
source_format: odata
snapshot_policy: hash-only
status: current
last_verified: ''
verified_by: ""
maintainer: "@dzinck"
live_schema_hash: "3e0b220ce41000dbc341d43d5a0bfa541540fdba36593e7639180ab702100c29"
relationships:
  implements: []
  implemented_by: []
  references_external: []
  related:
  - measure-history-actions
  - legislative-sessions
  supersedes: []
tags:
- oregon-legislature
- odata
- entity-doc
- measures
- bills
---

> **NON-AUTHORITATIVE — AI-friendly reference only.** This describes the shape of
> a live API, not a snapshot of its data. It is not the official text of any bill.
> Always fetch the live record for a current answer:
> <https://api.oregonlegislature.gov/odata/odataservice.svc/Measures> (schema last
> checked 2026-07-26).

# Measures

OData entity set `Measures` (entity type `State.Or.Leg.API.OData.Measure`) —
Oregon Legislature's bills and resolutions. This is the entity spec cited by
`get_document("measure:*")` once `src/odata_backend.py` exists (step 4); today
this doc exists so an agent can learn the shape of a measure record *before*
that backend is built, through the ordinary `search_corpus`/`get_document` path
over this file.

## At a glance

A `Measure` is one bill/resolution in one session — HB 2049 in `2025R1` and HB
2049 in `2027R1` (if it recurred) are two different `Measure` rows, not one
row with a session column. 25 fields (verified 2026-07-26, both against
`$metadata` and one live record, HB 2049 / 2025R1). The `RelatingToFull` field
carries a prose amend-list that is a *candidate* bill→statute edge — see
"Cross-corpus note" below. PHASE5-MCP-SPEC.md §2.2 called this edge sparse at
**14%**, measured over one 500-measure sample **before bill text was mirrored**.
Now that it is, the edge is not sparse: **83.8%** of the 3,757 mirrored measures
carry at least one ORS citation. The 14% figure describes `RelatingToFull` alone,
and even that measures **31.3%** against the full corpus rather than 14%.

## Entity reference

_Everything below is nested under one heading, deliberately: `FileBackend`'s
FTS index only extracts body text from a `## Full text` section (verbatim
document archetype convention) or, failing that, `## Key provisions` — see
`corpus_toolkit/mcp/backends.py`. An entity doc has no verbatim source to
quote, but the facts below are exactly what a `search_corpus` query should be
able to find, so they live here rather than under un-indexed top-level
headings._

### Key

Composite: **(`MeasureNumber`, `MeasurePrefix`, `SessionKey`)** — this is the
literal order the `<Key>` element lists them in `$metadata`; functionally it is
an unordered set of three fields, and PHASE5-MCP-SPEC.md's own prose states the
same triple as `(SessionKey, MeasurePrefix, MeasureNumber)`. A measure number
alone is ambiguous across sessions — HB 2049 exists in every session that has
an HB 2049 — so any lookup keyed on measure number without a session is
underspecified. This is why `resolve_citation` for measure citations is
required to ask-or-default the session rather than guess (PHASE5-MCP-SPEC.md
§5.4, R6) — a step-5 concern, not implemented by this doc.

### Fields

Types are the literal EDM primitive types from `$metadata`; "nullable" reflects
the metadata's own `Nullable` attribute (a `Property` with no `Nullable`
attribute defaults to nullable per the CSDL spec — that default is not this
corpus's inference, it is what the schema declares). "Observed" is what the one
record examined (HB 2049, `2025R1`, fetched 2026-07-26) actually held — a
single record is not a claim about the field in general, only about this one
row.

| Field | Type | Nullable | Observed on HB 2049 / 2025R1 |
|---|---|---|---|
| `SessionKey` | Edm.String (max 10) | no | `"2025R1"` |
| `MeasurePrefix` | Edm.String (max 3) | no | `"HB"` |
| `MeasureNumber` | Edm.Int32 | no | `2049` |
| `CatchLine` | Edm.String (max 2000) | yes | non-null, one sentence |
| `MinorityCatchLine` | Edm.String (max 2000) | yes | **null on the record examined** |
| `MeasureSummary` | Edm.String (max 4000) | yes | non-null, multi-paragraph digest |
| `CurrentVersion` | Edm.String (max 1) | yes | **null on the record examined** |
| `RelatingToFull` | Edm.String (max 4000) | yes | non-null: `"Relating to sex offenders; amending ORS 137.225, 163A.040 and 163A.215.\n\t"` (trailing whitespace present on the wire) |
| `RelatingTo` | Edm.String (max 2000) | yes | non-null: `"Relating to sex offenders."` |
| `AtTheRequestOf` | Edm.String (max 1000) | yes | **null on the record examined** |
| `ChapterNumber` | Edm.String (max 10) | yes | **null on the record examined** (not yet chaptered/enacted) |
| `CurrentLocation` | Edm.String (max 250) | no | `"In House Committee"` |
| `CurrentCommitteeCode` | Edm.String (max 6) | yes | `"HJUD"` |
| `CurrentSubCommittee` | Edm.String (max 6) | yes | **null on the record examined** |
| `FiscalImpact` | Edm.String (max 250) | yes | non-null, free text ("May have fiscal impact, but no statement yet issued") |
| `RevenueImpact` | Edm.String (max 250) | yes | non-null, free text (same pattern as `FiscalImpact`) |
| `EmergencyClause` | Edm.Boolean | yes | `false` |
| `EffectiveDate` | Edm.DateTime (precision 3) | yes | **null on the record examined** (not yet effective) |
| `FiscalAnalyst` | Edm.String (max 91) | yes | non-null, a person's name |
| `RevenueEconomist` | Edm.String (max 91) | yes | non-null, a person's name |
| `LCNumber` | Edm.Int32 | yes | `276` |
| `Vetoed` | Edm.Boolean | yes | `false` |
| `CreatedDate` | Edm.DateTime (precision 3) | no | `"2024-12-31T13:18:07"` |
| `ModifiedDate` | Edm.DateTime (precision 3) | yes | non-null: `"2025-01-21T08:16:43"` |
| `PrefixMeaning` | Edm.String (max 250) | no | `"House Bill"` |

Field count: **25**, matching PHASE5-MCP-SPEC.md §2.2's own count.

### Relationships (OData navigation properties, from `$metadata`)

All are unlabeled-cardinality `NavigationProperty` elements in `$metadata` — the
document does not state one-to-many vs. one-to-one anywhere; cardinality below
is inferred from the target entity's shape (e.g. `MeasureHistoryActions` is
plural and a measure plainly has many history rows), not asserted by the schema
itself, and is flagged as such.

| Navigation property | Target entity set | Cardinality (inferred, not schema-asserted) |
|---|---|---|
| `LegislativeSession` | `LegislativeSessions` | many Measures -> one LegislativeSession |
| `MeasureHistoryActions` | `MeasureHistoryActions` | one Measure -> many history rows |
| `MeasureSponsors` | `MeasureSponsors` | one Measure -> many sponsors |
| `MeasureDocuments` | `MeasureDocuments` | one Measure -> many documents |
| `MeasureAnalysisDocuments` | `MeasureAnalysisDocuments` | one Measure -> many analysis documents |
| `CommitteeAgendaItems` | `CommitteeAgendaItems` | one Measure -> many agenda appearances |
| `CommitteeMeetingDocuments` | `CommitteeMeetingDocuments` | one Measure -> many |
| `FloorSessionAgendaItems` | `FloorSessionAgendaItems` | one Measure -> many |
| `FloorLetters` | `FloorLetters` | one Measure -> many |
| `MeasureVote` | `MeasureVotes` | one Measure -> many (name is singular in `$metadata`; the target set is plural) |
| `CommitteeVotes` | `CommitteeVotes` | one Measure -> many |

None of these navigation paths were exercised (no `$expand` call was made) —
this table is the declared shape from `$metadata` only, not a verified fetch.

### Cross-corpus note: the `RelatingToFull` edge (candidate, not a finding)

`RelatingToFull` sometimes names ORS sections a bill amends, creates, or
repeals, in prose. The one record examined here illustrates the pattern:

> `"Relating to sex offenders; amending ORS 137.225, 163A.040 and 163A.215."`

**Re-measured 2026-07-27 against the full mirrored corpus** (3,757 measures),
superseding the 500-measure sample in PHASE5-MCP-SPEC.md §2.2:

| via | measures | distinct ORS sections |
|---|---|---|
| `RelatingToFull` only | **31.3%** (1,208) | — |
| bill text | **83.7%** (3,146) | — |
| either | **83.8%** (3,147) | **10,907** |

The spec's figures — 14% and 518 sections — predate bill-text mirroring and are
off by roughly 2x and 21x respectively. The spec itself predicted this, saying
mirroring bill text "turns the sparse 14% bill→statute edge into something far
denser." It did. The field remains a *summary*, not the authoritative amend
list — the operative text lives in the bill itself.
**An edge derived from `RelatingToFull` is a candidate, never a finding**, and
resolving it against `oregon-policy-repo`'s ORS ids is step 7 work, not
implemented here.

### Quirks (measured, this build — 2026-07-26)

- `$metadata` itself is XML-only: requesting it with `Accept: application/json`
  returned **HTTP 415** ("Unsupported media type requested" /
  `Microsoft.Data.OData.ODataContentTypeException`). Every other call made
  (`Measures`, `MeasureHistoryActions`, `LegislativeSessions`, all with
  `$top`/`$filter`) honored `Accept: application/json` normally. Any tooling
  that fetches `$metadata` must not send `Accept: application/json`, or must
  fall back to XML on 415.
- The single-record `Measures` fetch (`$filter=... and MeasureNumber eq
  2049&$top=1`) took **15.4s** — at the high end of, not matching,
  PHASE5-MCP-SPEC.md's own ~5.4s median for single-record calls. This build
  made too few calls (3 data calls total) to say why; recorded as observed,
  not reconciled.
- `RelatingToFull`'s trailing whitespace (`"...163A.215.\n\t"`) was present on
  the wire on the one record examined — worth trimming in any consumer, not
  evidence of a broader formatting rule.

### Verification

- **Method**: `curl -H "Accept: application/json"` against
  `https://api.oregonlegislature.gov/odata/odataservice.svc/$metadata` (fetched
  without the JSON `Accept` header, per the quirk above) for field names/types,
  and `Measures?$filter=SessionKey eq '2025R1' and MeasureNumber eq
  2049&$top=1` for one live record. Both calls made 2026-07-26.
- **`live_schema_hash` computation** (so the step-8 drift job can reproduce it):
  from `$metadata`, take the `<EntityType Name="Measure">` element's direct
  `<Property>` children only (navigation properties excluded). Build
  `"Name:Type"` for each (e.g. `"SessionKey:Edm.String"`), sort these strings
  ascending by field name, join with `|`, and take the sha256 hex digest of the
  UTF-8 bytes. `MaxLength`/`Precision`/`Nullable` attributes are **not** part of
  the hash — only the (name, base EDM type) set — so a length-limit change
  would not trip this hash; a field being added, removed, renamed, or having
  its EDM type changed would.
- `live_schema_hash: 3e0b220ce41000dbc341d43d5a0bfa541540fdba36593e7639180ab702100c29`
- **Not verified**: whether `$select`/`$expand`/`$orderby` behave as OData v3
  spec would predict for this entity (not called); whether any field's
  `MaxLength` is enforced server-side on write (this corpus is read-only, so
  moot); behavior of any field on a chaptered/enacted/vetoed measure (the one
  record examined is an in-committee bill with `ChapterNumber`, `EffectiveDate`
  all null) — those states are plausible from the schema but not observed.
