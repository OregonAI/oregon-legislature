#!/usr/bin/env python3
"""Semantic topic map of Oregon measures, coloured by what got enrolled.

  python3 src/build_topic_map.py            # -> viz/topic-map.html
  python3 src/build_topic_map.py --check     # exit 1 if stale (CI)

Reads the measure-level embeddings (src/build_measure_embeddings.py), projects them to 2-D
with UMAP, clusters in the FULL embedding space, and renders a canvas scatter with two
colour modes plus a ranked cluster panel.

THE FINDING THIS EXISTS TO SHOW: semantically similar bills share fates. Correlating a
bill's own outcome with the mean outcome of its 25 nearest neighbours gives r=+0.43 over
2025R1 bills (n=3,304, p~1e-149). It is not a measure-type artifact — it survives
restricting to HB+SB, which matters because resolutions enrol at 67-100% and joint
resolutions at 0%, so an uncontrolled view would show legislative FORM dressed as topic.

TWO DESIGN POINTS THAT ARE EASY TO GET WRONG:

1. Both sessions are projected in ONE shared UMAP space, then filtered. UMAP coordinates are
   arbitrary between runs, so projecting each session separately would produce two maps whose
   positions mean nothing relative to each other — and the session contrast is the point.

2. Clustering runs on the full 1024-D vectors, not the 2-D coordinates. The projection
   squashes distinct regions together; clustering the flattened view would invent structure
   that is an artifact of the layout.

OUTCOME IS INFERRED. There is no bill-status field in this mirror — 12 of the live API's 25
fields are unmirrored, and `status` is the constant `current` on every measure. "Enrolled"
means an Enrolled document exists, which happens only after a measure clears both chambers.
It is a proxy: not a ChapterNumber, and it lags anything enrolled after the ingest date. The
page says so.
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EMB = REPO_ROOT / "_meta/embeddings"
VECTORS, ROWS, META = EMB / "vectors.i8.npy", EMB / "rows.jsonl", EMB / "meta.json"
OUT = REPO_ROOT / "viz/topic-map.html"

SEED = 42
N_TOPICS = 24
BILL_PREFIXES = ("HB", "SB")

# Legislative boilerplate. Without a domain stoplist the TF-IDF labels degenerate into the
# scaffolding every catch line shares ("relating to", "declaring an emergency"). Tuned for
# THIS corpus — the sibling's list is Oregon-executive vocabulary (ors, oar, division) and
# does not overlap much.
DOMAIN_STOP = (
    "oregon state relating declaring emergency act measure bill provides provide "
    "requires require required directs direct modifies modify modifying changes change "
    "certain relates related person persons allows allow authorizes authorize "
    "establishes establish creating creates create prohibits prohibit specified "
    "operative effective date dates section sections purposes purpose"
).split()


def _topic_labels(docs, k):
    """Top distinctive terms per cluster (TF-IDF across clusters), de-duplicated.
    Ported from the sibling corpus's build_topic_projection.py:41."""
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
    vec = TfidfVectorizer(stop_words=list(ENGLISH_STOP_WORDS) + DOMAIN_STOP,
                          ngram_range=(1, 2), max_df=0.5, min_df=2,
                          token_pattern=r"[A-Za-z][A-Za-z]+")
    X = vec.fit_transform(docs)
    feats = vec.get_feature_names_out()
    labels = []
    for c in range(k):
        row = X[c].toarray().ravel()
        picked = []
        for j in row.argsort()[::-1]:
            if row[j] <= 0:
                break
            term = feats[j]
            words = term.split()
            if len(words) == 2 and words[0] == words[1]:
                continue
            if any(term in p or p in term for p in picked):
                continue
            picked.append(term)
            if len(picked) == 3:
                break
        labels.append(" · ".join(picked) if picked else f"cluster {c}")
    return labels


def neighbourhood_correlation(V, y, k=25):
    """Correlation between a measure's own outcome and the enrolment rate of its k nearest
    semantic neighbours. This is the statistic the page leads with, so it is computed from
    the same vectors the map draws rather than quoted from a notebook."""
    import numpy as np
    from scipy.stats import pointbiserialr
    if len(y) < k + 5:
        return None, None
    S = V @ V.T
    np.fill_diagonal(S, -2.0)
    nn = np.argpartition(-S, k, axis=1)[:, :k]
    local = y[nn].mean(axis=1)
    r, p = pointbiserialr(y.astype(int), local)
    return float(r), float(p)


def build_data() -> dict:
    import numpy as np
    from sklearn.cluster import MiniBatchKMeans

    rows = [json.loads(l) for l in ROWS.read_text(encoding="utf-8").splitlines() if l]
    raw = np.load(VECTORS).astype(np.float32)
    if len(rows) != raw.shape[0]:
        sys.exit(f"rows/vectors mismatch: {len(rows)} vs {raw.shape[0]} — rebuild embeddings")
    # Renormalize: the artifact is int8 (unit vectors x 127), and cosine needs unit length.
    V = raw / np.linalg.norm(raw, axis=1, keepdims=True).clip(1e-9)

    y = np.array([r["enrolled"] for r in rows], dtype=bool)
    sess = np.array([r["session"] for r in rows])
    pre = np.array([r["prefix"] for r in rows])

    # --- one shared 2-D space for BOTH sessions (see module docstring) ---
    import umap
    xy = np.asarray(umap.UMAP(n_neighbors=25, min_dist=0.12, metric="cosine",
                              random_state=SEED, n_components=2,
                              verbose=False).fit_transform(V), dtype=np.float32)
    lo, hi = xy.min(0), xy.max(0)
    span = np.where(hi - lo > 0, hi - lo, 1.0)
    q = np.round((xy - lo) / span * 4095).astype(int)

    # --- cluster in the FULL embedding space, not on the 2-D coords ---
    cl = MiniBatchKMeans(n_clusters=N_TOPICS, random_state=SEED, n_init=5,
                         batch_size=2048).fit_predict(V)
    docs = [" ".join(rows[j]["catch"] for j in np.where(cl == c)[0]) for c in range(N_TOPICS)]
    labels = _topic_labels(docs, N_TOPICS)

    # Cluster stats are computed over BILLS ONLY. Including resolutions would let a cluster's
    # rate be driven by form (resolutions enrol at 67-100%) rather than subject.
    bills = np.isin(pre, BILL_PREFIXES)
    clusters = []
    for c in range(N_TOPICS):
        m = (cl == c)
        mb = m & bills
        clusters.append({
            "t": labels[c],
            "x": int(q[m, 0].mean()), "y": int(q[m, 1].mean()),
            "n": int(m.sum()),
            "nb": int(mb.sum()),
            "rate": round(float(y[mb].mean()), 4) if mb.sum() else None,
        })

    stats = {}
    for s in sorted(set(sess), reverse=True):
        for scope, mask in (("all", sess == s), ("bills", (sess == s) & bills)):
            r, p = neighbourhood_correlation(V[mask], y[mask])
            stats[f"{s}:{scope}"] = {
                "n": int(mask.sum()),
                "enrolled": int(y[mask].sum()),
                "rate": round(float(y[mask].mean()), 4) if mask.sum() else 0,
                "r": round(r, 3) if r is not None else None,
                "p": p,
            }

    sessions = sorted(set(sess), reverse=True)
    return {
        "n": len(rows), "grid": 4095,
        "x": q[:, 0].tolist(), "y": q[:, 1].tolist(),
        "cl": cl.tolist(),
        "en": [int(v) for v in y],
        "se": [sessions.index(s) for s in sess],
        "sl": sessions,
        "bi": [int(v) for v in bills],
        "titles": [r["catch"][:120] for r in rows],
        "ids": [r["id"] for r in rows],
        "clusters": clusters,
        "stats": stats,
        "base_rate": round(float(y[bills].mean()), 4),
        "note": ("Each point is one measure, positioned by the meaning of its catch line and "
                 "summary. \"Enrolled\" is inferred from an Enrolled document existing — a "
                 "measure only gets one after clearing both chambers. It is a proxy, not a "
                 "chapter number, and it lags anything enrolled after this corpus was "
                 "ingested. Cluster rates cover bills (HB/SB) only, because resolutions "
                 "enrol at 67-100% and would otherwise make form look like subject. "
                 "Non-authoritative."),
    }


def build_html(data: dict) -> str:
    return TEMPLATE.replace("/*DATA*/", json.dumps(data, ensure_ascii=False,
                                                   separators=(",", ":")))


def outputs():
    return {OUT: build_html(build_data())}


def main():
    if "--check" in sys.argv:
        outs = outputs()
        stale = [p for p, t in outs.items() if not p.exists() or p.read_text() != t]
        if stale:
            print(f"{OUT.relative_to(REPO_ROOT)} is stale — run: python3 src/build_topic_map.py")
            sys.exit(1)
        print("topic-map.html is current.")
        return
    d = build_data()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_html(d), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO_ROOT)}: {d['n']:,} measures, {N_TOPICS} clusters")
    for k, v in d["stats"].items():
        print(f"  {k:<16} n={v['n']:<5} enrolled={v['rate']:.1%}  neighbourhood r={v['r']}")
    ranked = sorted((c for c in d["clusters"] if c["rate"] is not None),
                    key=lambda c: -c["rate"])
    print(f"  highest: {ranked[0]['rate']:.0%} ({ranked[0]['nb']}) {ranked[0]['t']}")
    print(f"  lowest:  {ranked[-1]['rate']:.0%} ({ranked[-1]['nb']}) {ranked[-1]['t']}")


# Palette validated with the dataviz skill's validate_palette.js:
#   outcome accent  #184f95 --mode light            -> ALL CHECKS PASS
#                   #3987e5 --mode dark             -> ALL CHECKS PASS
#   cluster ramp    #86b6ef,#5598e7,#2a78d6,#1c5cab,#104281 --mode light --ordinal -> PASS
#                   #184f95,#256abf,#3987e5,#6da7ec,#b7d3f6 --mode dark  --ordinal -> PASS
# The de-emphasis gray for "not enrolled" is intentionally a furniture role, not a
# categorical slot — it fails the chroma floor by design, exactly as in the citations chart.
# The outcome pair measures dE 30-36 all-pairs under protan and deutan, far above the >=8
# target.
#
# NOT the sibling's golden-angle HSL for clusters: generating 24 hues is what the dataviz
# skill forbids outright, and colouring clusters by enrolment rate encodes the finding
# rather than merely telling clusters apart.
TEMPLATE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Oregon measures — a semantic map of what got enrolled</title>
<meta name="description" content="Every Oregon measure positioned by meaning, coloured by whether it was enrolled. Non-authoritative.">
<style>
  :root{
    --bg:#f6f7f9;--surface:#fcfcfb;--ink:#0b0b0b;--muted:#52514e;--line:#e4e8ee;--gold:#8a6d1f;
    --shadow:0 1px 3px rgba(20,25,40,.09);
    --dim:#b4b3a9; --acc:#184f95;
    --r0:#86b6ef;--r1:#5598e7;--r2:#2a78d6;--r3:#1c5cab;--r4:#104281;
  }
  @media (prefers-color-scheme:dark){:root{
    --bg:#0e1116;--surface:#1a1a19;--ink:#fff;--muted:#c3c2b7;--line:#232a33;--gold:#d9b45a;
    --shadow:0 1px 3px rgba(0,0,0,.5);
    --dim:#4f4e49; --acc:#3987e5;
    --r0:#184f95;--r1:#256abf;--r2:#3987e5;--r3:#6da7ec;--r4:#b7d3f6;
  }}
  :root[data-theme=light]{--bg:#f6f7f9;--surface:#fcfcfb;--ink:#0b0b0b;--muted:#52514e;--line:#e4e8ee;--gold:#8a6d1f;
    --dim:#b4b3a9;--acc:#184f95;--r0:#86b6ef;--r1:#5598e7;--r2:#2a78d6;--r3:#1c5cab;--r4:#104281}
  :root[data-theme=dark]{--bg:#0e1116;--surface:#1a1a19;--ink:#fff;--muted:#c3c2b7;--line:#232a33;--gold:#d9b45a;
    --dim:#4f4e49;--acc:#3987e5;--r0:#184f95;--r1:#256abf;--r2:#3987e5;--r3:#6da7ec;--r4:#b7d3f6}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
  a{color:inherit}
  .disc{background:var(--gold);color:#1a1400;font-size:13px;text-align:center;padding:7px 14px;font-weight:600}
  .wrap{max-width:1180px;margin:0 auto;padding:0 22px 60px}
  header{padding:36px 0 14px}
  .eyebrow{text-transform:uppercase;letter-spacing:.14em;font-size:12px;color:var(--muted);font-weight:700;margin-bottom:11px}
  h1{font-size:clamp(25px,4.2vw,38px);line-height:1.1;margin:0 0 13px;letter-spacing:-.02em;font-weight:800;text-wrap:balance}
  .lede{font-size:17.5px;color:var(--muted);max-width:70ch;margin:0}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:13px;margin:24px 0 6px}
  .kpi{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow)}
  .kpi .v{font-size:32px;font-weight:800;letter-spacing:-.02em;font-variant-numeric:tabular-nums;line-height:1}
  .kpi .l{font-weight:650;margin-top:5px;font-size:14px}
  .kpi .s{color:var(--muted);font-size:12.5px;margin-top:3px}
  .panel{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:16px;margin-top:20px;align-items:start}
  @media (max-width:900px){.panel{grid-template-columns:minmax(0,1fr)}}
  figure{margin:0;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:var(--shadow);
    display:flex;flex-direction:column;min-width:0}
  .bar{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:11px}
  select,button{min-width:0;max-width:100%;font:inherit;font-size:13.5px;font-weight:650;padding:6px 11px;border-radius:9px;
    border:1px solid var(--line);background:var(--bg);color:var(--ink);cursor:pointer}
  #cvwrap{position:relative;width:100%;aspect-ratio:4/3;min-height:330px}
  canvas{width:100%;height:100%;display:block;border-radius:10px;background:var(--surface);cursor:crosshair}
  .legend{display:flex;flex-wrap:wrap;gap:14px;margin-top:11px;font-size:13px;color:var(--muted)}
  .legend span{display:inline-flex;align-items:center;gap:6px}
  .sw{width:12px;height:12px;border-radius:50%;flex:0 0 auto}
  figcaption{color:var(--muted);font-size:12.5px;margin-top:12px;line-height:1.5}
  h2{font-size:13px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:0 0 12px;font-weight:700}
  /* Fill the card rather than clipping at a fixed height: a hard max-height left the
     last row sliced in half with dead space under it. */
  .rank{flex:1;min-height:0;overflow:auto}
  .row{display:grid;grid-template-columns:46px 1fr auto;gap:9px;align-items:center;padding:5px 0;
    border-bottom:1px solid var(--line);font-size:13px;cursor:pointer}
  .row:hover{background:var(--bg)}
  .row.on{background:var(--bg);outline:2px solid var(--acc);outline-offset:-2px;border-radius:6px}
  .pct{font-weight:750;font-variant-numeric:tabular-nums;text-align:right}
  .trk{height:7px;border-radius:4px;background:var(--bg);position:relative;overflow:hidden}
  .fil{height:100%;border-radius:4px}
  .cnt{color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
  .tip{position:fixed;pointer-events:none;opacity:0;transition:opacity .1s;background:var(--ink);color:var(--bg);
    padding:7px 10px;border-radius:8px;font-size:12.5px;line-height:1.45;z-index:9;max-width:300px;box-shadow:var(--shadow)}
  #theme{position:fixed;top:12px;right:12px;width:36px;height:36px;border-radius:10px;border:1px solid var(--line);
    background:var(--surface);color:var(--ink);cursor:pointer;font-size:16px;z-index:5;box-shadow:var(--shadow)}
  footer{color:var(--muted);font-size:13px;margin-top:22px}
</style>
</head><body>
<button id="theme" title="Toggle light/dark" aria-label="Toggle theme">◑</button>
<div class="disc">NON-AUTHORITATIVE — outcome is inferred from document presence, not official status. Always verify against the Legislature.</div>
<div class="wrap">
<header>
  <div class="eyebrow">Oregon Legislature · 2024 &amp; 2025 regular sessions</div>
  <h1>Bills that look alike share a fate</h1>
  <p class="lede">Every measure placed by the meaning of its own title and summary. Bills
    whose semantic neighbours were enrolled tend to be enrolled themselves — and where that
    fails, it fails in a pattern. The six clusters of bills directing an agency to
    <b>study</b> something hold <b id="studyn">—</b> bills and enrol at
    <b id="studyr">—</b>, against a <b id="studybase">—</b> base.</p>
</header>

<div class="kpis" id="kpis"></div>

<div class="panel">
  <figure>
    <div class="bar">
      <select id="mode">
        <option value="outcome">Colour: enrolled or not</option>
        <option value="rate">Colour: cluster enrolment rate</option>
      </select>
      <select id="sess"><option value="-1">Both sessions</option></select>
      <select id="scope">
        <option value="bills">Bills only (HB/SB)</option>
        <option value="all">All measure types</option>
      </select>
      <button id="reset">Reset zoom</button>
    </div>
    <div id="cvwrap"><canvas id="cv"></canvas></div>
    <div class="legend" id="legend"></div>
    <figcaption id="cap"></figcaption>
  </figure>

  <figure>
    <h2>Clusters by enrolment rate <span id="scopenote" style="text-transform:none;letter-spacing:0"></span></h2>
    <div class="rank" id="rank"></div>
  </figure>
</div>

<footer>
  Scroll or drag to zoom and pan the map. <a href="./">Corpus home</a> ·
  <a href="https://github.com/OregonAI/oregon-legislature">Repository</a>
</footer>
</div>
<div class="tip" id="tip" role="status"></div>
<script>
const D = /*DATA*/;
const $ = s => document.querySelector(s);
const cv = $("#cv"), ctx = cv.getContext("2d");
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const RAMP = ["--r0","--r1","--r2","--r3","--r4"];
let mode = "outcome", sessIdx = -1, scope = "bills", pick = -1, selCluster = -1;
let view = {s:1, x:0, y:0};

D.sl.forEach((s,i) => $("#sess").insertAdjacentHTML("beforeend", `<option value="${i}">${s}</option>`));

function visible(i){
  if (sessIdx >= 0 && D.se[i] !== sessIdx) return false;
  if (scope === "bills" && !D.bi[i]) return false;
  if (selCluster >= 0 && D.cl[i] !== selCluster) return false;
  return true;
}
// Cluster rate drives the ramp step; nulls (no bills in cluster) fall back to the dim colour.
function rampFor(rate){
  if (rate == null) return css("--dim");
  const k = Math.min(RAMP.length-1, Math.floor(rate / 0.20));
  return css(RAMP[k]);
}

function stats(){
  let n=0, en=0;
  for (let i=0;i<D.n;i++) if (visible(i)){ n++; en += D.en[i]; }
  return {n, en, rate: n ? en/n : 0};
}

// Derived from the clustering, never hardcoded: labels and membership shift if the corpus
// or K changes, and prose baked into the template would quietly go stale.
function studyStats(){
  const st = D.clusters.filter(c=>c.rate!=null && /study/.test(c.t));
  const n = st.reduce((a,c)=>a+c.nb,0), en = st.reduce((a,c)=>a+c.rate*c.nb,0);
  return {k: st.length, n, rate: n ? (100*en/n).toFixed(0)+"%" : "—"};
}

function kpis(){
  const key = (sessIdx>=0 ? D.sl[sessIdx] : "2025R1") + ":" + scope;
  const st = D.stats[key] || D.stats["2025R1:bills"];
  const s = stats();
  $("#kpis").innerHTML = [
    {v:(s.rate*100).toFixed(0)+"%", l:"of shown measures enrolled", s:`${s.en.toLocaleString()} of ${s.n.toLocaleString()}`},
    {v:"r = "+(st.r ?? "—"), l:"outcome vs its 25 nearest neighbours", s:`${key} · n=${st.n.toLocaleString()}`},
    // State the study finding directly. A threshold count ("clusters under 8%") read as
    // contradicting the lede's "six study clusters", because the two sets are not the same.
    {v:studyStats().rate, l:"enrolment for bills directing a study", s:`${studyStats().n.toLocaleString()} bills across ${studyStats().k} clusters`},
  ].map(k=>`<div class="kpi"><div class="v">${k.v}</div><div class="l">${k.l}</div><div class="s">${k.s}</div></div>`).join("");
}

function draw(){
  const dpr = devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== w*dpr || cv.height !== h*dpr){ cv.width = w*dpr; cv.height = h*dpr; }
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,w,h);
  const pad = 14, sc = Math.min(w-2*pad, h-2*pad) / D.grid;
  const r = Math.max(1.9, 2.0*Math.sqrt(view.s));
  const dim = css("--dim"), acc = css("--acc");
  for (let i=0;i<D.n;i++){
    if (!visible(i)) continue;
    const px = pad + D.x[i]*sc*view.s + view.x, py = pad + (D.grid-D.y[i])*sc*view.s + view.y;
    if (px < -8 || py < -8 || px > w+8 || py > h+8) continue;
    if (mode === "outcome"){ ctx.fillStyle = D.en[i] ? acc : dim; }
    else { ctx.fillStyle = rampFor(D.clusters[D.cl[i]].rate); }
    ctx.globalAlpha = mode === "outcome" && !D.en[i] ? 0.5 : 0.82;
    ctx.beginPath(); ctx.arc(px, py, r, 0, 6.2832); ctx.fill();
  }
  ctx.globalAlpha = 1;
  // Cluster labels only when zoomed in enough to place them without collision.
  if (view.s > 1.6){
    ctx.font = "600 11px -apple-system,system-ui,sans-serif";
    ctx.fillStyle = css("--muted"); ctx.textAlign = "center";
    D.clusters.forEach((c,ci)=>{
      if (selCluster>=0 && ci!==selCluster) return;
      const px = pad + c.x*sc*view.s + view.x, py = pad + (D.grid-c.y)*sc*view.s + view.y;
      if (px>0 && py>0 && px<w && py<h) ctx.fillText(c.t.split(" · ")[0], px, py);
    });
  }
  legend();
}

function legend(){
  if (mode === "outcome"){
    $("#legend").innerHTML =
      `<span><i class="sw" style="background:var(--acc)"></i>Enrolled</span>
       <span><i class="sw" style="background:var(--dim)"></i>Not enrolled</span>`;
  } else {
    $("#legend").innerHTML = "<span>Cluster enrolment rate:</span>" + RAMP.map((v,i)=>
      `<span><i class="sw" style="background:var(${v})"></i>${i*20}–${(i+1)*20}%</span>`).join("");
  }
}

function rank(){
  const rows = D.clusters.map((c,i)=>({...c, i})).filter(c=>c.rate!=null).sort((a,b)=>b.rate-a.rate);
  $("#scopenote").textContent = `— bills only, base ${(D.base_rate*100).toFixed(0)}%`;
  $("#rank").innerHTML = rows.map(c=>`
    <div class="row ${c.i===selCluster?'on':''}" data-c="${c.i}" title="Click to isolate this cluster">
      <div class="pct">${(c.rate*100).toFixed(0)}%</div>
      <div><div style="margin-bottom:3px">${c.t}</div>
        <div class="trk"><div class="fil" style="width:${Math.max(2,c.rate*100)}%;background:${rampFor(c.rate)}"></div></div></div>
      <div class="cnt">${c.nb}</div>
    </div>`).join("");
  $("#rank").querySelectorAll(".row").forEach(el=>el.addEventListener("click",()=>{
    const c = +el.dataset.c; selCluster = selCluster===c ? -1 : c; rank(); draw(); kpis();
  }));
}

function caption(){
  // Computed from the data, never hardcoded — the clustering is seeded but the labels and
  // membership shift if the corpus or K changes, and stale prose would quietly become false.
  const ss = studyStats();
  $("#studyn").textContent = ss.n.toLocaleString();
  $("#studyr").textContent = ss.rate;
  $("#studybase").textContent = (D.base_rate*100).toFixed(0)+"%";

  // The two appropriation clusters need explaining or they read as a bug: their TF-IDF
  // labels are near-identical because the vocabulary genuinely is, while their rates sit at
  // opposite ends. Reading the bills is what separates them.
  $("#cap").innerHTML = D.note +
    "<br><br><b>On the two appropriation clusters.</b> They carry almost the same label and " +
    "very different rates. That is not an error: one holds agency <i>biennial budget</i> " +
    "bills, which have to pass, and the other holds <i>targeted</i> appropriations for a " +
    "particular programme or project, which mostly do not. The label cannot tell them apart " +
    "because the wording cannot — click either cluster to read its bills.";
}

// --- interaction ---
let drag = null;
cv.addEventListener("pointerdown", e=>{ drag = {x:e.clientX, y:e.clientY, vx:view.x, vy:view.y}; });
addEventListener("pointerup", ()=> drag = null);
addEventListener("pointermove", e=>{
  if (drag){ view.x = drag.vx + (e.clientX-drag.x); view.y = drag.vy + (e.clientY-drag.y); draw(); return; }
});
cv.addEventListener("wheel", e=>{
  e.preventDefault();
  const f = e.deltaY < 0 ? 1.12 : 1/1.12;
  const rect = cv.getBoundingClientRect(), mx = e.clientX-rect.left, my = e.clientY-rect.top;
  view.x = mx - (mx - view.x)*f; view.y = my - (my - view.y)*f;
  view.s = Math.max(1, Math.min(40, view.s*f));
  draw();
}, {passive:false});
$("#reset").addEventListener("click", ()=>{ view = {s:1,x:0,y:0}; selCluster=-1; rank(); draw(); kpis(); });

const tip = $("#tip");
cv.addEventListener("pointermove", e=>{
  if (drag) return;
  const rect = cv.getBoundingClientRect(), w = cv.clientWidth, h = cv.clientHeight;
  const pad = 14, sc = Math.min(w-2*pad, h-2*pad)/D.grid;
  const mx = e.clientX-rect.left, my = e.clientY-rect.top;
  let best = -1, bd = 100;
  for (let i=0;i<D.n;i++){
    if (!visible(i)) continue;
    const px = pad + D.x[i]*sc*view.s + view.x, py = pad + (D.grid-D.y[i])*sc*view.s + view.y;
    const d = (px-mx)**2 + (py-my)**2;
    if (d < bd){ bd = d; best = i; }
  }
  if (best < 0){ tip.style.opacity = 0; return; }
  tip.innerHTML = `<b>${D.titles[best]}</b><br>${D.sl[D.se[best]]} · ${D.ids[best].replace(/^measure-\w+-/,'').toUpperCase()} · `
    + (D.en[best] ? "enrolled" : "not enrolled");
  tip.style.opacity = 1;
  tip.style.left = Math.min(e.clientX+14, innerWidth-315)+"px";
  tip.style.top = (e.clientY+18)+"px";
});
cv.addEventListener("pointerleave", ()=> tip.style.opacity = 0);

$("#mode").addEventListener("change", e=>{ mode = e.target.value; draw(); });
$("#sess").addEventListener("change", e=>{ sessIdx = +e.target.value; draw(); kpis(); });
$("#scope").addEventListener("change", e=>{ scope = e.target.value; draw(); kpis(); });
addEventListener("resize", draw);

(function(){
  const b = $("#theme"), r = document.documentElement;
  try { const s = localStorage.getItem("theme"); if (s) r.setAttribute("data-theme", s); } catch(e){}
  b.addEventListener("click", ()=>{
    const cur = r.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light");
    r.setAttribute("data-theme", cur==="dark"?"light":"dark");
    try { localStorage.setItem("theme", r.getAttribute("data-theme")); } catch(e){}
    draw(); rank();
  });
})();

kpis(); rank(); caption(); draw();
</script>
</body></html>
"""


if __name__ == "__main__":
    main()
