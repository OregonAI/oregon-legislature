# Contributing

All changes via PR with CODEOWNER review. Before merge, the PR checklist
requires: every field/type/quirk claim in an entity doc traceable to an
actual `$metadata` fetch or a real fetched record made during that PR (never
inferred or copied from a different OData service's conventions); `$filter`,
`$top`, and any other query parameters used recorded verbatim in the doc;
`live_schema_hash` recomputed and its method unchanged (or the change to the
method itself called out); disclaimer present; relationships resolve;
CHANGELOG updated. Reviewers set `last_verified`/`verified_by` at approval.
Agent-assisted commits carry an `Assisted-by:` trailer.

Cookbook entries (once step 8 begins) additionally require: the query was
actually executed against the live API during that PR (not invented, not
copied from an entity doc's own worked example), `executed_at` recorded, and
any `RelatingToFull`-derived bill→statute link labeled a candidate with its
source quote.
