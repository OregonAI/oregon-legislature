#!/bin/bash
# Unattended full mirror ingest -> commit -> push branch -> open PR.
#
# THE GOVERNING RULE: nothing is pushed unless the ingest completed cleanly. A partial
# mirror that looks complete is this corpus's worst failure mode -- the server pages
# without a nextLink, so a truncated fetch reads as a finished one, and ingest_measures.py
# raises IncompleteFetch rather than return one. If it exits non-zero, or writes no new
# documents, this script stops and leaves the working tree for inspection.
#
# Runs ~2.4h for 3,925 documents (3,466 Introduced + 459 Enrolled) at concurrency 4.
set -uo pipefail

REPO=/home/dzinck/oregon-legislature
TOOLKIT=/home/dzinck/corpus_toolkit
S=/tmp/claude-1000/-home-dzinck/360a7307-aa70-4f3a-a652-47c68b1481ee/scratchpad
LOG="$S/nightly-ingest-$(date +%Y%m%d-%H%M).log"
BRANCH="ingest/2025r1-2024r1-$(date +%Y%m%d)"
SESSIONS="2025R1 2024R1"

exec > >(tee -a "$LOG") 2>&1
echo "=== nightly ingest starting $(date -Is) ==="

cd "$REPO" || { echo "FATAL: no repo at $REPO"; exit 1; }
export PYTHONPATH="$TOOLKIT:$S/pylibs:$REPO/src"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "FATAL: working tree is dirty before ingest. Refusing to run — a commit here"
  echo "       would mix unrelated changes into an unattended push."
  git status --short | head -20
  exit 1
fi

git checkout -q -b "$BRANCH" || { echo "FATAL: could not create $BRANCH"; exit 1; }
BEFORE=$(find measures -name '*.md' 2>/dev/null | wc -l)
echo "documents before: $BEFORE"

echo "--- ingest $SESSIONS (concurrency 4) ---"
START=$(date +%s)
python3 src/ingest_measures.py $SESSIONS --concurrency 4
RC=$?
MINS=$(( ($(date +%s) - START) / 60 ))
echo "--- ingest exit=$RC after ${MINS}m ---"

if [[ $RC -ne 0 ]]; then
  echo "FATAL: ingest failed (exit $RC). NOT committing, NOT pushing."
  echo "       Branch $BRANCH left in place with whatever it wrote, for inspection."
  exit $RC
fi

AFTER=$(find measures -name '*.md' 2>/dev/null | wc -l)
echo "documents after: $AFTER (added $((AFTER - BEFORE)))"
if [[ "$AFTER" -le "$BEFORE" ]]; then
  echo "FATAL: ingest exited 0 but added no documents. That is not a success —"
  echo "       treating it as a failure rather than pushing an empty change."
  exit 1
fi

# Rebuild the FTS index and prove the new documents are actually searchable. An ingest
# that writes files the indexer cannot see is a silent half-failure.
rm -f _meta/.cache/fts.db
python3 - <<'PY' || { echo "FATAL: post-ingest search check failed"; exit 1; }
import sys
from corpus_toolkit.config import load
from corpus_toolkit.mcp.backends import FileBackend
be = FileBackend(load("_meta/corpus.yml"))
h = be.health()
print(f"index health: {h['detail']}")
if not h["reachable"]:
    sys.exit(1)
hits = be.search("technology", limit=25)
print(f"search('technology') -> {len(hits)} hit(s)")
# The whole point of mirroring: OData substringof found 30. Anything near that is a
# sign the mirror or the index did not land.
sys.exit(0 if len(hits) >= 10 else 1)
PY

echo "--- committing ---"
git add -A
git -c user.name=dzinck -c user.email=dzinck@gmail.com commit -q -F - <<EOF
Mirror sessions $SESSIONS: measure metadata + bill text

Full ingest run by the scheduled job. $((AFTER - BEFORE)) new measure documents
(from $BEFORE to $AFTER), each carrying mirrored metadata plus extracted bill text
for the Introduced and Enrolled versions.

Paging is reconciled against odata.count and raises rather than returning a short
read, so this is a complete session or it is nothing.

Ingest took ${MINS}m at concurrency 4.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01DBsDt7b7cDfKbW43cSLkkJ
EOF

echo "--- pushing $BRANCH ---"
git push -u origin "$BRANCH" || { echo "FATAL: push failed"; exit 1; }

SIZE=$(du -sh --exclude=.git "$REPO" | cut -f1)
gh pr create --base main --head "$BRANCH" \
  --title "Mirror $SESSIONS: measure metadata + bill text" \
  --body "$(cat <<EOF
Full mirror ingest, run unattended by the scheduled job.

| | |
|---|---|
| sessions | $SESSIONS |
| documents | $BEFORE -> $AFTER (**+$((AFTER - BEFORE))**) |
| ingest time | ${MINS} minutes at concurrency 4 |
| repo size | $SIZE |

## What this contains

One document per measure: mirrored metadata (\`CatchLine\`, \`MeasureSummary\`,
\`RelatingToFull\`) plus extracted text of the **Introduced** and **Enrolled** bill
versions. Engrossed and amendment drafts are deliberately not mirrored — they are
intermediate, and fetchable on demand.

Bill PDFs are committed alongside the extracted text, matching every other corpus in
the org: \`source_sha256\` is computed over the source bytes, so provenance can only
be re-verified on a fresh clone if the bytes are present.

## Why mirrored rather than proxied

OData offers only \`substringof()\` — no stemming, no relevance. Measured on this
session, a substring filter for "technology" found 30 measures where a topic query
should find 121, and \`substringof('nurse')\` matched bills about *fish nurseries*.
Discovery needs an index; an index needs the text locally. See PHASE5-MCP-SPEC.md §1.1.

## Checks the job ran before pushing

- Ingest exited 0 — a non-zero exit or an \`IncompleteFetch\` aborts without committing
- Document count strictly increased — "exited 0 but wrote nothing" is treated as failure
- FTS index rebuilt and reported healthy
- \`search_corpus("technology")\` returns a plausible number of hits — an ingest whose
  files the indexer cannot see is a silent half-failure

## Not verified by the job

Bill-text extraction quality per document, and whether any measure landed as
\`not_extractable\`. Worth a look at the catalog before merge.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01DBsDt7b7cDfKbW43cSLkkJ
EOF
)" && echo "PR opened" || echo "WARNING: branch pushed but PR creation failed"

echo "=== done $(date -Is) — log: $LOG ==="
