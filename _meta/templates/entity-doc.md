---
schema_version: 1
corpus: "oregon-legislature"
jurisdiction: "oregon"
id:
title: "Entity doc: {EntitySetName}"
doc_type: entity_doc
citation: "Oregon Legislature OData API — {EntitySetName} entity set"
issuing_body: "Oregon State Legislature"
source_url: "https://api.oregonlegislature.gov/odata/odataservice.svc/{EntitySetName}"
source_format: odata
snapshot_policy: hash-only
status: current
last_verified:
verified_by: ""
maintainer: ""
live_schema_hash: ""
relationships:
  implements: []
  implemented_by: []
  references_external: []
  related: []
  supersedes: []
tags:
- oregon-legislature
- odata
- entity-doc
---

> **NON-AUTHORITATIVE — AI-friendly reference only.** This describes the shape of
> a live API, not a snapshot of its data. Always fetch the live source for a
> current answer: <{source_url}> (schema last checked {last_verified}).

# {EntitySetName}

_One or two sentences: what real-world thing does one row of this entity
represent, and where does it fit relative to the entity docs already in this
repo (Measures, MeasureHistoryActions, LegislativeSessions)?_

## At a glance

_Field count, and any single fact that most changes how an agent should think
about this entity (e.g. Measures: one row per bill PER SESSION, not per bill)._

## Key

_The literal `<Key>` from `$metadata`, in its declared order. State plainly
whether it is a single field or composite, and what ambiguity (if any) a
partial key would create._

## Fields

_Table: Field | Type | Nullable | Observed on {sample record(s) actually
fetched}. Type/Nullable straight from `$metadata`. "Observed" is what a real
fetched record held — never invented, and phrased as "null/non-null on the
record(s) examined," not "always" or "never," unless multiple records
genuinely confirm it._

## Relationships (OData navigation properties, from `$metadata`)

_Table: navigation property | target entity set | cardinality (state plainly
if this is INFERRED rather than schema-asserted — OData v3 `NavigationProperty`
elements here do not declare cardinality directly)._

## Quirks (measured, {date})

_Only things actually observed during this doc's own verification calls —
latency, unexpected nulls, ordering behavior without `$orderby`, content-type
gotchas. Not behavior copied from another entity doc's quirks list on the
assumption it also applies here._

## Verification

- **Method**: the exact `curl`/query calls made, with dates.
- **`live_schema_hash` computation**: from `$metadata`, take this entity
  type's direct `<Property>` children only (navigation properties excluded).
  Build `"Name:Type"` for each, sort ascending by field name, join with `|`,
  sha256 hex digest of the UTF-8 bytes. `MaxLength`/`Precision`/`Nullable` are
  NOT part of the hash — keep this method identical across every entity doc in
  this repo so the step-8 drift job can apply one procedure to all of them.
- `live_schema_hash: {computed value}`
- **Not verified**: state plainly what this doc's own calls did NOT establish
  (fields never observed non-null, `$expand`/`$orderby` behavior, states not
  seen in the sample record(s)) — do not leave this section empty just
  because everything else looks confirmed.
