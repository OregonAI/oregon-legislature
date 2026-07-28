#!/usr/bin/env python3
"""Embed every measure for the semantic topic map (offline, run after ingest).

One vector per MEASURE, not per chunk. Outcome is a per-measure attribute, so one point per
measure is what the map needs — and it avoids the sibling corpus's caveat, where a chart
still says "one point per document" after the index moved to chunk granularity and each
document became several points.

WHAT IS EMBEDDED: catch_line + measure_summary — the measure's own one-line title and
digest. NOT the bill text. Bill text is dominated by legislative boilerplate ("Relating
to …; and declaring an emergency", section scaffolding, standard clauses), so embedding it
clusters measures by legislative FORM rather than subject. Measured: catch_line+summary
produces clean topical clusters; that is what the map is for.

  python3 src/build_measure_embeddings.py            # build/refresh
  python3 src/build_measure_embeddings.py --check    # exit 1 if stale (CI)

Artifact under _meta/embeddings/ (gitignored — derived, rebuildable, and the deploy host has
no GPU so it is a local step):
  vectors.i8.npy   int8 [n_measures, dim] — L2-normalized embedding x 127
  rows.jsonl       one JSON object per row, carrying the metadata the map needs
  meta.json        {backend, model, dim, n_rows, fingerprint, ...}

rows.jsonl carries title/session/prefix/enrolled deliberately. The sibling's projection
script reaches into _meta/graph.json purely for id -> title; this corpus has no graph, and
keeping metadata beside the vectors removes that dependency instead of recreating it.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MEASURES = REPO_ROOT / "measures"
EMB_DIR = REPO_ROOT / "_meta/embeddings"
VECTORS = EMB_DIR / "vectors.i8.npy"
ROWS = EMB_DIR / "rows.jsonl"
META = EMB_DIR / "meta.json"

DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_M2V = "minishlab/potion-retrieval-32M"
BATCH = 256


# ---------- reading measures ----------

def _field(fm: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
    return m.group(1).strip().strip("'\"") if m else ""


def _block_list(fm: str, key: str) -> list[str]:
    """A YAML block list, e.g.:

        bill_text_versions_available:
        - Enrolled
        - Introduced

    Parsed explicitly because the inline form (`[Enrolled, Introduced]`) does NOT appear in
    this corpus — an inline-only regex silently matches nothing and reports every measure as
    not-enrolled, which reads as a real finding rather than a parse failure.
    """
    m = re.search(rf"^{key}:\n((?:- .+\n)+)", fm, re.M)
    return re.findall(r"- (\S.*)", m.group(1)) if m else []


def measure_rows():
    """Yield one dict per measure: id, title, text-to-embed, and the metadata the map needs."""
    for p in sorted(MEASURES.rglob("*.md")):
        if p.name == "_index.md":
            continue
        raw = p.read_text(encoding="utf-8", errors="ignore")
        if not raw.startswith("---"):
            continue
        fm = raw.split("---", 2)[1]
        catch = _field(fm, "catch_line")
        # measure_summary runs to the next top-level key; strip the upstream's HTML tags and
        # tabs, which are in the source verbatim.
        m = re.search(r"^measure_summary:\s*(.+?)(?=\n[a-z_]+:)", fm, re.M | re.S)
        summary = re.sub(r"<[^>]+>|\s+", " ", m.group(1)).strip() if m else ""
        text = f"{catch} {summary}".strip()
        if not text:
            continue
        yield {
            "id": _field(fm, "id"),
            "title": _field(fm, "title"),
            "session": _field(fm, "session_key"),
            "prefix": _field(fm, "measure_prefix"),
            "catch": catch,
            # Passage proxy. An Enrolled document is produced only once a measure clears
            # both chambers — there is no bill-status field in this mirror to use instead.
            # Inferred, not authoritative: see the map's caption.
            "enrolled": "Enrolled" in _block_list(fm, "bill_text_versions_available"),
            "text": text[:2000],
        }


def corpus_fingerprint(rows) -> str:
    """Hash of the embeddable content — changes only when what we embed changes, not on
    unrelated commits."""
    h = hashlib.sha256()
    for r in rows:
        h.update(r["id"].encode())
        h.update(re.sub(r"\s+", " ", r["text"]).strip().encode())
        h.update(b"1" if r["enrolled"] else b"0")
    return h.hexdigest()


# ---------- embedders (ported from the sibling corpus, unchanged in behaviour) ----------

class HashingEmbedder:
    """Deterministic stdlib+numpy fallback. NOT semantic — for wiring and CI only."""
    name = "hashing"

    def __init__(self, dim=384, model="hashing-ngram-v1"):
        self.dim, self.model = dim, model or "hashing-ngram-v1"

    def encode(self, texts):
        import numpy as np
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for r, t in enumerate(texts):
            t = re.sub(r"\s+", " ", t.lower())
            for n in (3, 4, 5):
                for i in range(len(t) - n + 1):
                    b = int.from_bytes(hashlib.blake2b(t[i:i + n].encode(), digest_size=4).digest(),
                                       "little") % self.dim
                    out[r, b] += 1.0
            row = out[r]
            nz = row > 0
            row[nz] = 1.0 + np.log(row[nz])
            out[r] = row / (float(np.linalg.norm(row)) or 1.0)
        return out


class Model2VecEmbedder:
    """Static embeddings — CPU-fast fallback when no GPU is present."""
    name = "model2vec"

    def __init__(self, model=DEFAULT_M2V):
        import numpy as np
        from model2vec import StaticModel
        self.model = model or DEFAULT_M2V
        self._m = StaticModel.from_pretrained(self.model)
        self.dim = int(self._m.encode(["probe"]).shape[1])
        self._np = np

    def encode(self, texts):
        np = self._np
        v = self._m.encode(list(texts)).astype("float32")
        n = np.linalg.norm(v, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return v / n


class SentenceTransformerEmbedder:
    """Production backend. bge-m3 at 1024 dims; these texts are short (a catch line plus a
    digest), so max_seq_length is never the binding constraint here."""
    name = "sentence-transformers"

    def __init__(self, model=DEFAULT_MODEL):
        import torch
        from sentence_transformers import SentenceTransformer
        self.model = model or DEFAULT_MODEL
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._m = SentenceTransformer(self.model, device=self.device)
        if self.device == "cuda":
            self._m.half()
        get_dim = getattr(self._m, "get_embedding_dimension", None) or \
            self._m.get_sentence_embedding_dimension
        self.dim = get_dim()
        self.batch_size = 64 if self.device == "cuda" else 16

    def encode(self, texts):
        return self._m.encode(list(texts), normalize_embeddings=True,
                              batch_size=self.batch_size,
                              show_progress_bar=False).astype("float32")


def make_embedder(backend, dim, model=None):
    if backend == "hashing":
        return HashingEmbedder(dim=dim, model=model)
    if backend == "model2vec":
        return Model2VecEmbedder(model)
    if backend == "sentence-transformers":
        return SentenceTransformerEmbedder(model)
    try:
        import torch
        gpu = torch.cuda.is_available()
    except ImportError:
        gpu = False
    ctors = [lambda: SentenceTransformerEmbedder(model), lambda: Model2VecEmbedder(model)]
    if not gpu:
        ctors.reverse()
    for ctor in ctors:
        try:
            return ctor()
        except Exception:
            continue
    print("note: no embedding model available; using the hashing fallback (no semantic "
          "quality).", file=sys.stderr)
    return HashingEmbedder(dim=dim, model=model)


def quantize_int8(vecs):
    import numpy as np
    return np.clip(np.rint(vecs * 127.0), -127, 127).astype(np.int8)


# ---------- build ----------

def build(backend="auto", limit=None, dim=384, model=None):
    import time

    import numpy as np
    rows = list(measure_rows())
    if limit:
        rows = rows[:limit]
    if not rows:
        sys.exit("no measures found to embed")
    emb = make_embedder(backend, dim, model)

    print(f"embedding {len(rows)} measures ({emb.name}, {getattr(emb, 'model', '')}) …",
          flush=True)
    out = np.empty((len(rows), emb.dim), dtype=np.int8)
    t0 = time.time()
    for start in range(0, len(rows), BATCH):
        batch = [r["text"] for r in rows[start:start + BATCH]]
        out[start:start + len(batch)] = quantize_int8(emb.encode(batch))
        done = start + len(batch)
        if done % (BATCH * 4) == 0 or done == len(rows):
            rate = done / max(time.time() - t0, 1e-6)
            print(f"  {done}/{len(rows)} ({done * 100 // len(rows)}%) · {rate:.0f}/s",
                  flush=True)

    EMB_DIR.mkdir(parents=True, exist_ok=True)
    np.save(VECTORS, out)
    with ROWS.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({k: r[k] for k in
                                ("id", "title", "session", "prefix", "catch", "enrolled")},
                               ensure_ascii=False) + "\n")
    META.write_text(json.dumps({
        "backend": emb.name, "model": getattr(emb, "model", ""), "dim": int(emb.dim),
        "granularity": "measure", "n_rows": len(rows),
        "fingerprint": corpus_fingerprint(rows),
        "embedded_text": "catch_line + measure_summary",
        "note": ("One int8 vector per MEASURE (not per chunk), L2-normalized*127; cosine "
                 "~ int32 dot / 127^2. Text embedded is the catch line plus the measure "
                 "summary, NOT the bill text — bill text is boilerplate-heavy and clusters "
                 "by legislative form rather than subject."),
    }, indent=1) + "\n")
    enrolled = sum(r["enrolled"] for r in rows)
    print(f"embedded {len(rows)} measures (dim={emb.dim}) -> {VECTORS.relative_to(REPO_ROOT)}")
    print(f"  {enrolled} enrolled ({100 * enrolled / len(rows):.1f}%)")


def check():
    if not META.is_file():
        print("no embeddings artifact — build it with "
              "python3 src/build_measure_embeddings.py")
        sys.exit(1)
    meta = json.loads(META.read_text())
    if meta.get("fingerprint") != corpus_fingerprint(list(measure_rows())):
        print("_meta/embeddings is stale — run: python3 src/build_measure_embeddings.py")
        sys.exit(1)
    print(f"_meta/embeddings current ({meta['n_rows']} measures, {meta['backend']}).")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if the artifact is stale")
    ap.add_argument("--backend",
                    choices=["auto", "model2vec", "sentence-transformers", "hashing"],
                    default="auto")
    ap.add_argument("--limit", type=int, help="embed only the first N measures")
    ap.add_argument("--dim", type=int, default=384, help="dim for the hashing backend")
    ap.add_argument("--model", help="override the backend's default model")
    args = ap.parse_args()
    if args.check:
        check()
    else:
        build(args.backend, args.limit, args.dim, args.model)


if __name__ == "__main__":
    main()
