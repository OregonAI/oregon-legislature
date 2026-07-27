# Oregon Legislature — Measures, History, and Sessions (OData)

> ## ⚠️ NON-AUTHORITATIVE — AI-friendly reference only
> Curated descriptions of a live API, not the official legislative record.
> Always fetch the live source linked in each document. See
> [DISCLAIMER.md](DISCLAIMER.md).

Part of the OregonAI civic corpus platform
([reference architecture](https://github.com/OregonAI/corpus-toolkit)).
Archetype: **api**. MCP interface: contract v1.

| Entry point | For |
|---|---|
| [llms.txt](llms.txt) | Machine-readable index — AI agents start here |
| [AGENTS.md](AGENTS.md) | Agent rules and anti-fabrication requirements |
| [STATUS.md](STATUS.md) | Generated health: freshness, coverage, drift |
| `_meta/corpus.yml` | Corpus configuration |

## What is here, and what is not (read this first)

This corpus is **not** a mirror of the Oregon Legislature's records. Per
PHASE5-MCP-SPEC.md §5.1, there are two different kinds of thing an agent might
mean by "a document" here, and they are served completely differently:

| kind | example | where it lives | how it is served |
|---|---|---|---|
| **repo docs** — descriptions of the API's shape | `entities/measures.md` | this repo, ordinary markdown | today's file-backed search/get machinery, unchanged |
| **live records** — an actual bill, vote, or session | HB 2049 in session 2025R1 | the Oregon Legislature's own OData feed, fetched per call | not yet implemented (step 4) — no backend exists in this repo today |

`search_corpus` on this corpus searches **the entity documentation**, never
the legislature's live records — a remote API cannot be full-text indexed, and
this is stated here (and in the entity docs) rather than left to be
discovered by a confusing empty result.

## Current build status

This is **step 3** of a staged build (see `PHASE5-MCP-SPEC.md` in the parent
directory of this repo's checkout, §9 "Build order"). What exists today:

- `entities/`: 3 entity docs — `measures`, `measure-history-actions`,
  `legislative-sessions` — one per OData entity set, describing fields, keys,
  relationships, and measured quirks. Every fact in them was read from the
  live API on 2026-07-26, not invented; see each doc's own "Verification"
  section for the exact calls made.
- `cookbook/`: a placeholder. No entries — see
  [cookbook/README.md](cookbook/README.md) for why and what belongs there
  (step 8).

What does **not** exist yet, on purpose: `src/odata_backend.py` (step 4, the
actual `RetrievalBackend` that would let `get_document("measure:*")` fetch a
live record), `src/citations.py` (step 5, `"HB 2049"` citation parsing with
session inference), `query_dataset`/`measure_history` tools (step 6),
cross-corpus ORS links (step 7), and the schema-drift CI job plus real
cookbook entries (step 8). Until step 4 lands, this corpus can answer "what
does a Measure record look like" but not "what is the status of HB 2049" —
that is the intended, honest state of a documentation-only step.

## Citing

Entity docs are internal to this repo's own documentation, not third-party
citations. There is no citation scheme registered yet for measure ids (`HB
2049` etc.) — that is step 5. For now, refer to an entity doc by its filename
stem: `measures`, `measure-history-actions`, `legislative-sessions`.

## License

Content (curated government material): CC0-1.0. Tooling, structure,
metadata: MIT.
