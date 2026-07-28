#!/usr/bin/env python3
"""Build the static GitHub Pages site into ./site/ (gitignored; produced at deploy time).

A curated landing page for the corpus — NOT a render of all 3,757 measures (the repo, the
MCP server, and llms.txt already serve those). It shows live corpus stats read from the
measure catalog, and links to the visualization, llms.txt, the MCP server, and the repo.

  python3 src/build_site.py        # writes ./site/{index.html, <viz>.html, llms.txt, corpus-index.json}

Wired into .github/workflows/pages.yml, which runs this and deploys ./site/ on push to main.

THIS REPLACES the reusable publish-index workflow. That workflow publishes corpus-index.json
alone and its own header warns not to call it from a corpus that deploys Pages itself — two
workflows deploying to one Pages site fight over the `pages` concurrency group. So this
script must keep emitting corpus-index.json at the same URL: the org landing page reads it
for live document counts, and oregon-records-retention resolves citations INTO this corpus
through it. Dropping it would silently break a sibling.
"""
import json
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"
REPO_URL = "https://github.com/OregonAI/oregon-legislature"
MCP_URL = "https://oregonai.morficflux.com/oregon-legislature/mcp"

# (title, filename, one-line description) — copied into site/ and shown in the gallery
VIZZES = [
    ("Bills that look alike share a fate", "topic-map.html",
     "Every measure placed by meaning, coloured by whether it was enrolled. Bills whose "
     "semantic neighbours were enrolled tend to be enrolled themselves — and the clusters "
     "asking an agency to <em>study</em> something enrol at 8% against a 21% base."),
    ("Statutes said vs statutes cited", "bill-statute-citations.html",
     "A measure's summary field names a minority of the statutes its own text references — "
     "and almost never one the text misses. The measured case for mirroring bill text."),
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


def commas(n: int) -> str:
    return f"{n:,}"


def build_html() -> str:
    s = stats()
    tiles = [
        ("Measures mirrored", commas(s["measures"]),
         f"across {len(s['sessions'])} sessions: {', '.join(sorted(s['sessions']))}"),
        ("With full bill text", commas(s["with_text"]),
         "PDF extracted to searchable text, not metadata alone"),
        ("ORS citations found", commas(s["cites"]),
         "candidates parsed from bill text — references, not an amend list"),
    ]
    tile_html = "\n".join(
        f'<div class="tile"><div class="num">{v}</div><div class="lbl">{name}</div>'
        f'<div class="sub">{sub}</div></div>' for name, v, sub in tiles)
    viz_html = "\n".join(
        f'<div class="card"><h3>{t}</h3><p>{d}</p>'
        f'<a class="go" href="{f}">Open the visualization →</a></div>'
        for t, f, d in VIZZES)
    return (TEMPLATE
            .replace("<!--TILES-->", tile_html)
            .replace("<!--VIZ-->", viz_html)
            .replace("__REPO__", REPO_URL)
            .replace("__MCP__", MCP_URL)
            .replace("__MEASURES__", commas(s["measures"]))
            .replace("__TODAY__", date.today().isoformat()))


def build_corpus_index(site: Path) -> str:
    """Publish the cross-corpus resolution index — see the module docstring for why this
    script owns it rather than the reusable publish-index workflow.

    Built at deploy time, never committed: a committed index is a generated file that can
    silently fall behind its own corpus, and that failure surfaces in SOMEONE ELSE's
    repository when their resolver returns stale titles and paths.
    """
    from corpus_toolkit import config as config_mod
    from corpus_toolkit.index import build_index

    index = build_index(config_mod.load(str(REPO / "_meta/corpus.yml")))
    out = site / "corpus-index.json"
    out.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    return f"{index['n_documents']:,} documents, {out.stat().st_size / 1048576:.1f} MiB"


def main():
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(build_html(), encoding="utf-8")
    missing = []
    for src in [f for _, f, *_ in VIZZES] + ["llms.txt"]:
        p = REPO / ("llms.txt" if src == "llms.txt" else f"viz/{src}")
        if p.exists():
            shutil.copyfile(p, SITE / src)
        else:
            missing.append(str(p.relative_to(REPO)))
    if missing:
        # A landing page linking to a viz that was never generated ships a dead link, and
        # the gallery card gives no hint it is broken. Fail the build instead.
        sys.exit(f"ERROR: missing site input(s): {', '.join(missing)} — "
                 f"run the viz generators first (python3 src/build_measure_citations.py)")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built site/ ({stats()['measures']:,} measures) -> {SITE.relative_to(REPO)}")
    print(f"  corpus-index.json: {build_corpus_index(SITE)}")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Oregon Legislature — mirrored measures, an AI-agent-friendly corpus</title>
<meta name="description" content="A non-authoritative, machine-readable mirror of Oregon legislative measures — metadata and full bill text — with an MCP server.">
<style>
  :root{
    --bg:#f6f7f9; --panel:#fcfcfb; --ink:#0b0b0b; --muted:#52514e; --line:#e4e8ee;
    --accent:#1f6feb; --accent-ink:#0b4bc0; --gold:#8a6d1f;
    --shadow:0 1px 2px rgba(20,25,40,.06),0 8px 30px rgba(20,25,40,.07);
  }
  @media (prefers-color-scheme:dark){
    :root{--bg:#0e1116; --panel:#1a1a19; --ink:#ffffff; --muted:#c3c2b7; --line:#232a33;
      --accent:#5a9bff; --accent-ink:#8fbaff; --gold:#d9b45a;
      --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 34px rgba(0,0,0,.45);}
  }
  :root[data-theme="light"]{--bg:#f6f7f9;--panel:#fcfcfb;--ink:#0b0b0b;--muted:#52514e;--line:#e4e8ee;--accent:#1f6feb;--accent-ink:#0b4bc0;--gold:#8a6d1f}
  :root[data-theme="dark"]{--bg:#0e1116;--panel:#1a1a19;--ink:#fff;--muted:#c3c2b7;--line:#232a33;--accent:#5a9bff;--accent-ink:#8fbaff;--gold:#d9b45a}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
  a{color:var(--accent-ink);text-decoration:none} a:hover{text-decoration:underline}
  .wrap{max-width:960px;margin:0 auto;padding:0 22px}
  .disc{background:var(--gold);color:#1a1400;font-size:13px;text-align:center;padding:7px 14px;font-weight:600}
  header{padding:60px 0 26px;border-bottom:1px solid var(--line)}
  .eyebrow{text-transform:uppercase;letter-spacing:.14em;font-size:12px;color:var(--muted);font-weight:700;margin-bottom:14px}
  h1{font-size:clamp(28px,5vw,44px);line-height:1.08;margin:0 0 16px;letter-spacing:-.02em;font-weight:800;text-wrap:balance}
  .lede{font-size:19px;color:var(--muted);max-width:64ch;margin:0}
  .cta{display:flex;flex-wrap:wrap;gap:12px;margin-top:26px}
  .btn{display:inline-flex;align-items:center;gap:8px;padding:11px 18px;border-radius:10px;font-weight:650;font-size:15px;
    border:1px solid var(--line);background:var(--panel);color:var(--ink);box-shadow:var(--shadow)}
  .btn.primary{background:var(--accent);color:#fff;border-color:transparent}
  .btn:hover{text-decoration:none;transform:translateY(-1px)}
  section{padding:44px 0}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
  .tile{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px;box-shadow:var(--shadow)}
  .tile .num{font-size:32px;font-weight:800;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
  .tile .lbl{font-weight:650;margin-top:2px}
  .tile .sub{color:var(--muted);font-size:13.5px;margin-top:5px;line-height:1.45}
  h2{font-size:14px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:0 0 18px;font-weight:700}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px;box-shadow:var(--shadow);display:flex;flex-direction:column}
  .card h3{margin:0 0 8px;font-size:18px;letter-spacing:-.01em}
  .card p{margin:0 0 16px;color:var(--muted);font-size:14.5px;flex:1}
  .card .go{font-weight:650;font-size:14.5px}
  code{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-size:13px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
  ul.plain{margin:0;padding-left:20px;color:var(--muted);font-size:14.5px}
  ul.plain li{margin:8px 0}
  footer{border-top:1px solid var(--line);padding:30px 0 60px;color:var(--muted);font-size:13.5px}
  footer p{margin:6px 0}
  #theme{position:fixed;top:14px;right:14px;width:36px;height:36px;border-radius:10px;border:1px solid var(--line);
    background:var(--panel);color:var(--ink);cursor:pointer;box-shadow:var(--shadow);font-size:16px;z-index:5}
</style>
</head>
<body>
<button id="theme" title="Toggle light/dark" aria-label="Toggle theme">◑</button>
<div class="disc">NON-AUTHORITATIVE point-in-time mirror — not the official record, and never live status. Always verify against each measure's cited source.</div>
<div class="wrap">
  <header>
    <div class="eyebrow">Oregon Legislature · measures · bill text</div>
    <h1>Oregon legislative measures, readable by machines</h1>
    <p class="lede">__MEASURES__ measures mirrored from the Legislature's OData feed —
      metadata and the full text of each bill — so an agent can search, cite, and quote them
      instead of recalling them. Live status is proxied on demand, never mirrored.</p>
    <div class="cta">
      <a class="btn primary" href="bill-statute-citations.html">See the data →</a>
      <a class="btn" href="__REPO__">Repository</a>
      <a class="btn" href="llms.txt">llms.txt</a>
    </div>
  </header>

  <section><div class="grid"><!--TILES--></div></section>

  <section>
    <h2>Visualizations</h2>
    <div class="cards"><!--VIZ--></div>
  </section>

  <section>
    <h2>For agents</h2>
    <ul class="plain">
      <li><b>MCP server</b> — <code>__MCP__</code>. Tools: <code>search_corpus</code>,
        <code>get_document</code>, <code>resolve_citation</code>, <code>corpus_overview</code>,
        <code>graph_neighbors</code>, <code>authority_chain</code>.</li>
      <li><b>Hybrid corpus.</b> Measure text is mirrored and searchable; current status is
        proxied live from the Legislature's OData feed at query time, because a stale status
        presented as current is the failure this design refuses.</li>
      <li><b>Citations are candidates, not findings.</b> ORS references are extracted from
        bill text by pattern match and include boilerplate cross-references. A measure may
        cite a statute without changing it.</li>
      <li><b>Cross-corpus.</b> Sibling corpora resolve citations into this one through the
        published <code>corpus-index.json</code>.</li>
    </ul>
  </section>

  <footer>
    <p>Built __TODAY__ from the mirrored corpus. Unofficial and non-authoritative; not
      affiliated with the State of Oregon or the Oregon Legislative Assembly.</p>
    <p>Part of the <a href="https://oregonai.github.io/">OregonAI Civic Corpus Platform</a>.</p>
  </footer>
</div>
<script>
(function(){
  var b=document.getElementById('theme'),r=document.documentElement;
  try{var s=localStorage.getItem('theme'); if(s) r.setAttribute('data-theme',s);}catch(e){}
  b.addEventListener('click',function(){
    var cur=r.getAttribute('data-theme')||
      (matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
    var next=cur==='dark'?'light':'dark';
    r.setAttribute('data-theme',next);
    try{localStorage.setItem('theme',next);}catch(e){}
  });
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
