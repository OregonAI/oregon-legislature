# Where is this bill right now?

The mirrored document answers what a bill *says*; the live feed answers where it *is*.

1. Resolve the citation — `resolve_citation("HB 2049 (2025R1)")` → `measure-2025r1-hb2049`
   (the bare form `"HB 2049"` returns every session that holds one, newest first).
2. `get_document("measure-2025r1-hb2049")` — the mirror, enriched with a `live_status`
   block (current location, committee, chapter number if enacted), envelope-stamped with
   when the feed was asked.
3. For the full docket history: `query_dataset("measure-history-actions",
   session="2025R1", prefix="HB", number=2049)` — every action with dates and vote text,
   ordered by ActionDate, with `executed_query` showing exactly what was asked of the feed.

The feed answers in ~5–15 s and this corpus never caches it: a `live_status` or
`query_dataset` answer is as fresh as its `executed_at` says, no fresher.
