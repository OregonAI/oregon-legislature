"""HybridBackend — mirrored files for retrieval, live OData for volatile state.

WHY IT SUBCLASSES FileBackend RATHER THAN REPLACING IT. This corpus's *retrieval* is
genuinely file-based: search runs over mirrored measure metadata and bill text, because
OData offers only `substringof()` and no relevance ranking (PHASE5-MCP-SPEC.md §1.1).
What the feed is for is the half that changes — current location, history, votes,
schedules. So the live source ENRICHES retrieval; it does not perform it.

That split is also what keeps the failure modes separate. If the feed is down, search
still works and `get_document` still returns the mirrored record — with an explicit
`upstream_status: "unavailable"` on the status block rather than a missing or empty
one. A reader can always tell which half of the answer is which.

WHAT THIS DOES NOT DO. `measure_status`, `scheduled_for` and `measure_votes` (spec §5.5)
are not here, because the toolkit has no way for a corpus to register its own MCP tools —
`build_server()` hardcodes the seven. That gap is recorded as G3; until it is closed, the
live data reaches callers through `get_document` enrichment only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from corpus_toolkit.mcp.backends import FileBackend

# The toolkit's plugin loader puts the REPO ROOT on sys.path (so "src.odata_backend"
# resolves), not src/ itself — so a bare `import odata` fails at server startup with
# ModuleNotFoundError. Same pattern the policy repo's src modules use.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import odata  # noqa: E402

# measure-2025r1-hb2049 -> ("2025R1", "HB", 2049)
_MEASURE_ID = re.compile(r"^measure-(?P<session>\d{4}[a-z]\d)-(?P<prefix>[a-z]+)(?P<num>\d+)$")

# Fields worth showing as "current state". Deliberately NOT the fields the mirror holds:
# re-fetching CatchLine live would invite a reader to wonder which copy is right.
STATUS_SELECT = ("MeasurePrefix,MeasureNumber,SessionKey,CurrentLocation,"
                 "CurrentCommitteeCode,CurrentSubCommittee,ChapterNumber,"
                 "EffectiveDate,Vetoed,EmergencyClause,ModifiedDate")


def parse_measure_id(doc_id: str):
    """(SessionKey, MeasurePrefix, MeasureNumber) or None if not a measure id."""
    m = _MEASURE_ID.match(doc_id or "")
    if not m:
        return None
    return m["session"].upper(), m["prefix"].upper(), int(m["num"])


class HybridBackend(FileBackend):
    """FileBackend + a live status block on measure documents."""

    name = "hybrid-odata"

    def __init__(self, config, semantic=None):
        super().__init__(config, semantic)
        self._live_enabled = True

    # ---------- live enrichment ----------

    def live_status(self, doc_id: str) -> dict | None:
        """Current state for one measure, always envelope-stamped. None if `doc_id` is
        not a measure (entity docs and cookbook pages have no live counterpart)."""
        key = parse_measure_id(doc_id)
        if key is None:
            return None
        session, prefix, number = key
        r = odata.fetch(
            "Measures",
            filter_=odata.build_filter(SessionKey=session, MeasurePrefix=prefix,
                                       MeasureNumber=number),
            select=STATUS_SELECT, top=1)
        block = {"as_of": r.envelope()}
        if not r.ok:
            # Explicitly NOT an empty status: a caller must be able to tell "the feed is
            # down" from "this measure has no current location".
            block["unavailable"] = True
            return block
        if not r.rows:
            block["found"] = False
            return block
        row = r.rows[0]
        block["found"] = True
        block["current"] = {k: row.get(k) for k in
                            ("CurrentLocation", "CurrentCommitteeCode",
                             "CurrentSubCommittee", "ChapterNumber", "EffectiveDate",
                             "Vetoed", "EmergencyClause", "ModifiedDate")}
        return block

    def get(self, doc_id: str, *, part: str = "auto") -> dict:
        rec = super().get(doc_id, part=part)
        if rec.get("error") and "id" not in rec:
            return rec
        if not self._live_enabled:
            return rec
        status = self.live_status(doc_id)
        if status is not None:
            # `live_status` is a separate key, never merged into the mirrored fields.
            # Interleaving them would make it impossible to tell, field by field, which
            # commit or which query an answer came from.
            rec["live_status"] = status
        return rec

    # ---------- health covers BOTH halves ----------

    def health(self) -> dict:
        """Mirror health from FileBackend, plus a live reachability probe.

        Reported together and separately: a corpus with a healthy mirror and a dead feed
        is a real, serviceable state, and flattening the two into one boolean would hide
        which is which."""
        mirror = super().health()
        live = odata.health()
        return {"reachable": mirror["reachable"],          # search works iff the mirror does
                "checked_at": live["checked_at"],
                "detail": f"mirror: {mirror['detail']}; live: {live['detail']}",
                "mirror": mirror,
                "live": live}

    def overview(self) -> dict:
        o = super().overview()
        o["live_source"] = odata.health()
        return o
