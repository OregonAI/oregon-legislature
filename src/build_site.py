#!/usr/bin/env python3
"""Build the GitHub Pages site into ./site/ (gitignored; produced at deploy time).

    python3 src/build_site.py

MIGRATED onto `corpus_toolkit.site`. The theme-aware CSS, tile markup, theme toggle and
corpus-index.json emission were a copy of what two other corpora carried and seven now share;
they live in the toolkit. What stays here is this corpus's numbers, its prose, and the two
visualisations it publishes.

This still REPLACES the reusable publish-index workflow — the two must never both exist here,
because they fight over the `pages` concurrency group.
"""
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from corpus_toolkit import config as config_mod                       # noqa: E402
from corpus_toolkit.site import Page, Section, Tile, build            # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent

VIZZES = [
    ("Bill → statute citations", "bill-statute-citations.html",
     "Which ORS chapters the Legislature has been amending, by session."),
    ("Semantic topic map", "topic-map.html",
     "A 2-D projection of measure text: proximity means similar subject matter."),
]


def stats() -> dict:
    cat = yaml.safe_load((REPO / "_meta/catalog/measures.yml").read_text())
    sessions, measures, with_text, cites = [], 0, 0, 0
    for key in sorted(cat, reverse=True):
        ms = cat[key].get("measures", {}) or {}
        measures += len(ms)
        with_text += sum(1 for m in ms.values() if (m.get("bill_text_chars") or 0) > 0)
        cites += sum(m.get("candidate_ors_bill_text") or 0 for m in ms.values())
        sessions.append(key)
    return {"measures": measures, "sessions": sessions, "with_text": with_text,
            "cites": cites}


def main() -> int:
    s = stats()
    cards = "\n".join(
        f'      <a class="card" href="{fn}"><b>{t}</b><span>{d}</span></a>'
        for t, fn, d in VIZZES)

    out = build(Page(
        config=config_mod.load(REPO / "_meta/corpus.yml"),
        repo="oregon-legislature",
        title="Oregon Legislature — measures, history and sessions",
        description=("A non-authoritative, machine-readable mirror of Oregon legislative "
                     "measures and bill text, with live status proxied from the "
                     "Legislature's OData feed."),
        eyebrow="Oregon · Legislative Assembly",
        headline="The bill end of the bill → statute → rule chain",
        lede_html=(
            f"<b>{s['measures']:,} measures</b> across {len(s['sessions'])} sessions, "
            f"<b>{s['with_text']:,} with full bill text</b>, mirrored so a question about "
            "what a bill actually says does not depend on a search box being generous."),
        disclaimer=("NON-AUTHORITATIVE reference — not the official measure text. Always "
                    "verify against the Oregon Legislative Assembly."),
        tiles=[
            Tile("Measures mirrored", f"{s['measures']:,}",
                 f"sessions: {', '.join(sorted(s['sessions']))}"),
            Tile("With full bill text", f"{s['with_text']:,}",
                 "the rest carry metadata and live status only"),
            Tile("Candidate ORS citations", f"{s['cites']:,}",
                 "sections a bill's text names — candidates, not confirmed amendments"),
        ],
        sections=[
            Section("Explore", f'    <div class="cards">\n{cards}\n    </div>'),
            Section("Mirrored text, proxied status", """
    <ul class="plain">
      <li><b>Text is mirrored; status is live.</b> The design started as a pure OData proxy
        and was changed after measuring: the feed's <code>substringof()</code> search missed
        <b>84 of 121</b> relevant bills. Mirroring the text and proxying only the status is
        what that measurement bought.</li>
      <li><b>A citation found in bill text is a candidate.</b> A bill naming an ORS section
        is not proof it amended it — bills reference statutes they leave untouched — so the
        edge is recorded as a candidate and labelled as one.</li>
      <li>Where a measure became law, the resulting statute lives in
        <a href="https://oregonai.github.io/executive-regulatory-frameworks/">Executive
        Regulatory Frameworks</a>, and the money it authorized in
        <a href="https://oregonai.github.io/oregon-budget/">Budget &amp; Expenditure</a>.</li>
    </ul>"""),
            Section("For agents", """
    <ul class="plain">
      <li><b>MCP server</b> — the document tools plus live measure-status lookups against
        the Legislature's OData feed.</li>
      <li><b>Every mirrored measure carries provenance</b> — source URL, retrieval date and
        a content hash.</li>
    </ul>"""),
        ],
        footer_note=("Unofficial and non-authoritative; not affiliated with the Oregon "
                     "Legislative Assembly."),
        extra_files=[REPO / "viz" / fn for _, fn, _ in VIZZES],
    ))
    print(f"built site/ — {s['measures']:,} measures, {len(s['sessions'])} sessions")
    print(f"  corpus-index.json: {out['index']}")
    missing = [c for c in out["copied"] if c.startswith("MISSING")]
    if missing:
        print(f"  {len(missing)} MISSING: {', '.join(missing)}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
