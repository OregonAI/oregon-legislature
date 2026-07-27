# STATUS

Not yet generated. This file is produced by `corpus-generate-status`
(see the `scheduled` workflow); it will be overwritten on first run.

Note for the api archetype: `corpus-generate-status` (as shipped in
`corpus_toolkit` up to v1.2.0) reports document counts/freshness generically
via `content_files()` and frontmatter — it has no archetype-specific text yet,
so its first real run will summarize `entities/*.md` the same way it would any
other content root (counts, `last_verified` age). It does not yet report
anything API-specific (entity-set coverage vs. the live 20, schema-drift
state) — that reporting is part of the still-unbuilt step-8 tooling, not a
regression to fix in this file.
