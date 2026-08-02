# What sessions exist, and which is current?

`query_dataset("legislative-sessions")` — every session the Legislature's feed knows,
with begin/end dates and the `DefaultSession` flag marking the current one. Mirrored
coverage differs from feed coverage: this corpus mirrors 18 sessions (2017R1 onward;
2018S1 and 2021S1 genuinely produced no mirrored measures), while the feed reaches back
to 2007. A session in the feed but not the mirror can be queried live and read at the
Legislature's own site — it is not missing, it is out of this corpus's declared scope
(see `_meta/corpus.yml`).
