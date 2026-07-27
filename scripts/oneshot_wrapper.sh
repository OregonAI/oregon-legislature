#!/bin/bash
# One-shot wrapper: de-schedule FIRST, then run.
#
# crontab has no one-shot mode, and the request was for a single overnight run — not a
# nightly job that opens a PR every morning unattended. Removing the entry BEFORE the
# ingest (not after) means a hang or a crash still cannot cause a second run tomorrow.
set -uo pipefail

MARKER="# oregon-legislature-oneshot-ingest"
crontab -l 2>/dev/null | grep -v "$MARKER" | crontab - 2>/dev/null
echo "$(date -Is) de-scheduled; starting ingest" \
  >> /tmp/claude-1000/-home-dzinck/360a7307-aa70-4f3a-a652-47c68b1481ee/scratchpad/oneshot.log

exec /home/dzinck/oregon-legislature/scripts/nightly_ingest.sh
