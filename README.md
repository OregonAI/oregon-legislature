# Oregon Legislature — Measures, History, and Sessions (OData)

> ## ⚠️ NON-AUTHORITATIVE — AI-friendly reference only
> Curated descriptions of a live API, not the official legislative record.
> Always fetch the live source linked in each document. See
> [DISCLAIMER.md](DISCLAIMER.md).

Part of the OregonAI civic corpus platform
([reference architecture](https://github.com/OregonAI/corpus-toolkit)).
Archetype (`_meta/corpus.yml`): **hybrid**, MCP interface contract v1.

This paragraph used to say the archetype was "still `api`, not yet flipped to
`hybrid`", and that `authority_chain`/`issuing_body_profile` were therefore not
offered. The flip has since happened — `_meta/corpus.yml` declares
`archetype: "hybrid"` — and the tool claim was never how the toolkit decides.
What the server actually registers for this corpus, listed by building it:

| tool | offered? | gated on |
|---|---|---|
| `search_corpus`, `get_document`, `resolve_citation`, `corpus_overview` | yes | mandatory core, every archetype |
| `graph_neighbors` | **yes** | mandatory core — registered unconditionally, archetype irrelevant |
| `authority_chain` | **yes** | archetype in (`document`, `hybrid`) |
| `issuing_body_profile` | **no** | `plugins.issuing_body_registry`, which this corpus does not set — **not** the archetype |
| `list_datasets`, `query_dataset`, `join_lookup` | **no** | `plugins.tools_module`, unset — see issue #11 |

The `issuing_body_profile` row is the one worth reading twice: the old text
reached the right answer for the wrong reason, so flipping the archetype would
not have changed it and nobody would have known why.

Note `graph_neighbors` and `authority_chain` being offered is not the same as
their being useful here: there is no `_meta/graph.json` yet (step 7+), so they
correctly report that the corpus has no relationship graph — on
corpus-toolkit >= v1.7.0. On the pinned v1.5.2 they instead deny that the
document exists at all; see `_meta/corpus.yml` and corpus-toolkit#5.

| Entry point | For |
|---|---|
| [llms.txt](llms.txt) | Machine-readable index — AI agents start here |
| [AGENTS.md](AGENTS.md) | Agent rules and anti-fabrication requirements |
| [STATUS.md](STATUS.md) | Generated health: freshness, coverage, drift |
| `_meta/corpus.yml` | Corpus configuration |

## What is here, and what is not (read this first)

Per PHASE5-MCP-SPEC.md §5.1 (rewritten 2026-07-26, see its own §1.1), this
corpus's **target design** is hybrid: mirror what an agent would search for,
proxy what changes. (The `archetype:` field in `_meta/corpus.yml` is still
`api` — see the note at the top of this file; that flip is step 3b, not done
by this build.) There are three different kinds of thing an agent might mean
by "a document" here, served differently:

| kind | example | where it lives | how it is served |
|---|---|---|---|
| **repo docs** — descriptions of the API's shape | `entities/measures.md` | this repo, ordinary hand-authored markdown | today's file-backed search/get machinery, unchanged |
| **mirrored measures** — a measure's identity + CatchLine/MeasureSummary/RelatingTo(Full) + (where filed) Introduced/Enrolled bill text | `measures/2025R1/measure-2025r1-hb2049.md` | this repo, machine-written by `src/ingest_measures.py` | same file-backed search/get machinery as repo docs — **never hand-edited** |
| **live records** — a measure's CURRENT status, history, or votes | HB 2049's location today | the Oregon Legislature's own OData feed, fetched per call | not yet implemented (step 5) — no live-proxy backend exists in this repo today |

`search_corpus` today reaches the entity documentation **and** the mirrored
measures (both are ordinary content files); it does not and will not reach
live status/history/votes — a remote API's current state cannot be mirrored
without becoming stale the moment it's fetched, which is exactly the failure
mode PHASE5-MCP-SPEC.md §7 guardrail #4 forbids presenting as current.

## Current build status

This is through **step 4** of a staged build (see `PHASE5-MCP-SPEC.md` in the
parent directory of this repo's checkout, §9/§10 "Build order"). What exists
today:

- `entities/`: 3 entity docs — `measures`, `measure-history-actions`,
  `legislative-sessions` — one per OData entity set, describing fields, keys,
  relationships, and measured quirks. Every fact in them was read from the
  live API on 2026-07-26, not invented; see each doc's own "Verification"
  section for the exact calls made.
- `measures/2025R1/`: **20 measures** (HB 2001–2020), a `--limit 20` proof
  run of `src/ingest_measures.py` — not a full session. Each file mirrors the
  measure's identity/CatchLine/MeasureSummary/RelatingTo(Full) and, where an
  Introduced or Enrolled `MeasureDocument` PDF exists, its extracted full
  text under `## Full text`, with candidate ORS citations (regex, both from
  `RelatingToFull` and from the bill text itself) recorded as candidates, not
  findings (§2.2). See [measures/_index.md](measures/_index.md) for the
  running per-session index and `_meta/catalog/measures.yml` for per-measure
  status. **A full-session run has deliberately not been executed** — §7's
  politeness guardrail (concurrency capped at 4) estimates ~1.7h for one
  session; running it is left to a human operator.
- `cookbook/`: a placeholder. No entries — see
  [cookbook/README.md](cookbook/README.md) for why and what belongs there
  (step 9).

What does **not** exist yet, on purpose: `src/odata_backend.py` (step 5, the
actual `RetrievalBackend` that would let `get_document("measure:*")` attach a
live status block, and the `measure_status`/`measure_votes`/`scheduled_for`
tools), `src/citations.py` (step 6, `"HB 2049"` citation parsing with session
inference), cross-corpus ORS resolution against `oregon-policy-repo` (step
8), and the schema-drift CI job plus real cookbook entries (step 9). This
corpus can now answer "what is HB 2049 about" and search across mirrored
measure text, but not "what is the current status of HB 2049" — that split
is the intended, honest state of a hybrid corpus with the mirror half built
and the live half not yet.

## Citing

Entity docs are internal to this repo's own documentation, not third-party
citations. There is no citation scheme registered yet for measure ids (`HB
2049` etc.) — that is step 5. For now, refer to an entity doc by its filename
stem: `measures`, `measure-history-actions`, `legislative-sessions`.

## License

Content (curated government material): CC0-1.0. Tooling, structure,
metadata: MIT.
