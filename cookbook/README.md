# Cookbook

Empty. Nothing has been ingested here yet — this file only explains what will
land in this directory and why nothing is here now.

## What this is

Per the seed spec (`corpus-seeds/oregon-legislature.md`) and
PHASE5-MCP-SPEC.md §6, `cookbook/*.md` will hold **real executed queries and
their measured shapes** — not a manual of hypothetical OData calls. Each entry
answers one recurring question an agent would otherwise have to rediscover the
`$filter` syntax for, e.g. (categories named in the seed spec, none of these
have been run):

- all measures amending a given ORS chapter
- votes by legislator
- bills in committee X this session
- measure history for HB NNNN

None of these have been executed against the live API by this build. Writing
an entry for one without having actually run it and pasted its real response
shape would be exactly the fabrication this project's anti-fabrication rules
(AGENTS.md) exist to prevent — see PHASE5-MCP-SPEC.md's replication-guide
note: "build the query cookbook from real executed queries (paste actual
responses' shapes, never invented ones)."

## What an entry must carry, once written (step 8)

Per PHASE5-MCP-SPEC.md §5.3/§7, every entry must record:

- the exact query executed (entity + `$filter`/`$select`/`$top`, no raw
  user-supplied OData — `query_dataset` guardrail #1),
- the `executed_at` timestamp and the fact that the shown result is a
  point-in-time snapshot, never presented as current without that stamp,
- the actual response shape observed (field names/types/nullability as
  returned, not as imagined),
- `truncated: true` noted explicitly if the result hit the client-side result
  cap, never silently,
- for any bill->statute edge drawn from `RelatingToFull`: labeled a
  *candidate*, with the source quote, per §2.3 — never presented as the
  authoritative amend list.

## Why this isn't a content root yet

`_meta/corpus.yml`'s `content_roots` intentionally does not include
`cookbook/` yet (see the comment there). Once real entries exist, whoever
writes them needs to decide what `doc_type` they carry —
`corpus_toolkit`'s current frontmatter schema (`entity_doc`, `dataset_doc`,
and the law-document types) has no obvious fit for "a worked example query and
its shape," and inventing a new enum value is a toolkit change, not a content
one. That decision belongs to step 8, alongside the entries themselves, not to
this scaffolding step.

- [live-bill-status.md](live-bill-status.md) — citation → mirror → live location → full docket history
- [session-roster.md](session-roster.md) — sessions, the current one, and feed-vs-mirror coverage
