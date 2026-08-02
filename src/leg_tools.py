"""Hybrid extension tools: the live-OData half of the contract this corpus declares.

Registered via `plugins.tools_module` (corpus-toolkit >= 1.6.0). This closes
oregon-legislature#11: the corpus declared `archetype: hybrid` while serving only the six
core tools, and from toolkit v1.19.0 that configuration refuses to start — the archetype
is a promise about the tool surface, enforced.

DESIGN RULES CARRIED OVER FROM oregon-budget/src/budget_tools.py, the org's precedent:

  * `query_dataset` takes NAMED, TYPED filters and builds the OData query itself. It does
    not accept a raw `$filter` string — passing one through would let a caller reshape the
    query into something whose `executed_query` no longer describes what was asked, and
    the contract requires that field to be auditable.
  * An allow-list of entity sets, not a passthrough: the feed exposes 20; the three
    offered here are the three this corpus has MEASURED and documented (entities/*.md).
    An entity name reaching the URL unchecked is the same class of hole as a raw $filter.
  * Every response spreads the ODataResult envelope (executed_query, executed_at,
    upstream_status) and carries the non-authoritative disclaimer.
  * A failed upstream call is NOT a result of zero, and says so.

Latency, measured (corpus.yml api block, 2026-07-26): ~5.4-15 s per call — the feed is
slow, and both tools say so up front rather than letting the first call feel broken.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Same trick as odata_backend.py: the toolkit's plugin loader puts the REPO ROOT on
# sys.path, not src/ itself.
sys.path.insert(0, str(Path(__file__).parent))
import odata  # noqa: E402

MAX_ROWS = 200            # a tool response is read by a model; a session's 3,466 measures
                          # are a mirror query (search_corpus), not a live-feed answer.

LATENCY_NOTE = ("the Legislature's OData feed answers in ~5-15 s; prefer the mirrored "
                "documents (search_corpus/get_document) for anything that does not need "
                "to be live")

# The three entity sets this corpus has measured and documented — entities/<file>.md is
# the contract for each. `filters` maps tool argument -> OData column; `numeric` columns
# pass to build_filter unquoted.
DATASETS = {
    "measures": {
        "entity": "Measures",
        "doc": "entities/measures.md",
        "filters": {"session": "SessionKey", "prefix": "MeasurePrefix",
                    "number": "MeasureNumber", "current_committee": "CurrentCommitteeCode"},
        "numeric": {"number"},
        "select": ("MeasurePrefix,MeasureNumber,SessionKey,CatchLine,CurrentLocation,"
                   "CurrentCommitteeCode,ChapterNumber,EffectiveDate,Vetoed,ModifiedDate"),
        "order_by": None,
    },
    "measure-history-actions": {
        "entity": "MeasureHistoryActions",
        "doc": "entities/measure-history-actions.md",
        "filters": {"session": "SessionKey", "prefix": "MeasurePrefix",
                    "number": "MeasureNumber", "chamber": "Chamber"},
        "numeric": {"number"},
        "select": ("SessionKey,MeasurePrefix,MeasureNumber,Chamber,ActionDate,"
                   "ActionText,VoteText"),
        "order_by": "ActionDate",
    },
    "legislative-sessions": {
        "entity": "LegislativeSessions",
        "doc": "entities/legislative-sessions.md",
        "filters": {"session": "SessionKey"},
        "numeric": set(),
        "select": "SessionKey,SessionName,BeginDate,EndDate,DefaultSession",
        "order_by": "BeginDate",
    },
}

DISCLAIMER = ("non-authoritative live proxy of the Oregon Legislature's OData feed; "
              "verify at the endpoint shown")


def register(mcp, framework):
    """Called by corpus-mcp-serve after every built-in tool."""

    @mcp.tool()
    def list_datasets() -> dict:
        """The live OData entity sets this corpus can query, with their filterable
        columns. Call this before query_dataset. Live queries are SLOW (~5-15 s);
        the mirrored measures answer most questions faster via search_corpus."""
        return {
            "datasets": [
                {"dataset": key,
                 "entity_set": d["entity"],
                 "entity_doc": d["doc"],
                 "filterable": sorted(d["filters"]),
                 "columns_returned": d["select"].split(","),
                 "endpoint": f"{odata.BASE}{d['entity']}"}
                for key, d in DATASETS.items()],
            "note": LATENCY_NOTE,
            "disclaimer": DISCLAIMER,
        }

    @mcp.tool()
    def query_dataset(dataset: str, session: str = "", prefix: str = "",
                      number: int = 0, chamber: str = "",
                      current_committee: str = "", limit: int = 50) -> dict:
        """Query a live OData entity set with named filters (see list_datasets).
        Examples: dataset='measures', session='2025R1', prefix='HB', number=2049;
        dataset='measure-history-actions' for a bill's full action history.
        Live and slow (~5-15 s); results carry executed_query for auditability."""
        d = DATASETS.get(dataset)
        if d is None:
            return {"error": f"unknown dataset {dataset!r}",
                    "datasets": sorted(DATASETS),
                    "note": "call list_datasets first"}
        supplied = {"session": session, "prefix": prefix, "number": number,
                    "chamber": chamber, "current_committee": current_committee}
        unknown = [k for k, v in supplied.items() if v and k not in d["filters"]]
        if unknown:
            return {"error": f"{dataset!r} does not filter on {', '.join(unknown)}",
                    "filterable": sorted(d["filters"])}
        filters = {}
        for arg, col in d["filters"].items():
            v = supplied.get(arg)
            if not v:
                continue
            filters[col] = int(v) if arg in d["numeric"] else str(v).upper() \
                if arg in ("prefix", "chamber") else str(v)
        limit = max(1, min(int(limit or 50), MAX_ROWS))
        r = odata.fetch(d["entity"],
                        filter_=odata.build_filter(**filters) if filters else "",
                        select=d["select"], top=limit, order_by=d["order_by"] or "")
        out = {**r.envelope(), "dataset": dataset, "disclaimer": DISCLAIMER}
        if not r.ok:
            out["note"] = ("the live feed could not be queried — this is NOT a result "
                           "of zero, and must not be reported as one")
            return out
        out["rows"] = r.rows
        out["n_rows"] = len(r.rows)
        if len(r.rows) >= limit:
            out["truncated"] = True
            out["note"] = (f"row cap {limit} reached; narrow the filters — "
                          f"{LATENCY_NOTE}")
        return out
