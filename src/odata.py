"""A small OData v3 client for the Oregon Legislature feed.

Deliberately hand-rolled over urllib rather than taking an OData dependency: the service
is v3 (`odata.metadata`, `$inlinecount`, `Microsoft.Data.OData` in its errors) and the
current generation of client libraries target v4. See PHASE5-MCP-SPEC.md §2.

THREE BEHAVIOURS HERE ARE LOAD-BEARING. Each exists because getting it wrong produces a
plausible-looking wrong answer rather than an error:

1. PAGING. The server honours `$top` up to at least 4,000 and emits NO `nextLink`, while
   2025R1 alone has 6,178 MeasureDocuments. A single request looks complete and is not.
   `fetch_all` pages with `$skip` and RAISES if it cannot reconcile against
   `odata.count`. A truncated result must never be returned quietly. (The spec's own
   "66% of measures have a document" figure was this bug: 4,000 of 6,178 rows read as a
   complete answer.)

2. FAILURE IS NOT EMPTINESS. A timeout, a 5xx, or a connection error yields
   `upstream_status="unavailable"` with `rows=[]` — and every caller must branch on the
   status, never on `len(rows)`. This mirrors the toolkit's sibling-index protocol, which
   already distinguishes "the sibling says it has no such document" from "we could not
   consult the sibling": opposite answers for a caller.

3. EVERY RESULT CARRIES ITS QUERY AND ITS CLOCK. A hybrid corpus tempts a reader to
   assume one as-of date for everything. The mirrored half has a commit; this half does
   not, and says so per call.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

BASE = "https://api.oregonlegislature.gov/odata/odataservice.svc"
USER_AGENT = ("oregon-civic-corpus/0.1 (+https://github.com/OregonAI/oregon-legislature; "
              "contact: dzinck@gmail.com)")

# Measured 2026-07-26: no throttling observed to concurrency 8, but that was 45 requests
# and proves nothing about sustained load. Half the tested ceiling.
MAX_CONCURRENCY = 4
# The server will not protect us (no nextLink); the client must. A caller asking for
# "every measure ever" gets a truncated answer that SAYS it is truncated.
DEFAULT_ROW_CAP = 5000
PAGE_SIZE = 2000
TIMEOUT_S = 60
# ~5.4s is the measured floor for a single-record query, so a short retry budget buys
# nothing. One retry, then report unavailable.
MAX_RETRIES = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ODataResult:
    """Rows plus the provenance envelope required by PHASE5-MCP-SPEC.md §5.4.

    `upstream_status` is the field callers must branch on:
      live        — the feed answered
      unavailable — we could not reach or parse it; rows is EMPTY BUT MEANINGLESS
      capped      — the feed answered, and there is more than we returned
    """
    rows: list = field(default_factory=list)
    executed_query: str = ""
    executed_at: str = ""
    source: str = BASE
    upstream_status: str = "live"
    total_count: int | None = None
    truncated: bool = False
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.upstream_status != "unavailable"

    def envelope(self) -> dict:
        """The provenance block to attach to any MCP response built from this."""
        env = {"executed_query": self.executed_query,
               "executed_at": self.executed_at,
               "source": self.source,
               "upstream_status": self.upstream_status}
        if self.truncated:
            env["truncated"] = True
            env["total_count"] = self.total_count
        if self.detail:
            env["detail"] = self.detail
        return env


def _quote(value: str) -> str:
    """Escape a string literal for an OData $filter. Single quotes double."""
    return "'" + str(value).replace("'", "''") + "'"


def build_filter(**equals) -> str:
    """An $filter of ANDed equality clauses, values escaped.

    Only equality, and only over caller-named fields — user text never reaches $filter
    as an expression (spec §7.1). That is both an injection guard and the reason the
    `executed_query` in the envelope is always something a human can audit.
    """
    parts = []
    for key, val in equals.items():
        if val is None:
            continue
        parts.append(f"{key} eq " + (_quote(val) if isinstance(val, str) else str(val)))
    return " and ".join(parts)


def _request(path: str, timeout: int) -> dict:
    url = f"{BASE}/{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch(entity: str, *, filter_: str = "", select: str = "", top: int | None = None,
          order_by: str = "", timeout: int = TIMEOUT_S) -> ODataResult:
    """One page. For anything that can exceed a page, use fetch_all."""
    q = {}
    if filter_:
        q["$filter"] = filter_
    if select:
        q["$select"] = select
    if order_by:
        q["$orderby"] = order_by
    if top is not None:
        q["$top"] = top
    path = f"{entity}?{urllib.parse.urlencode(q)}" if q else entity
    started = _utc_now()
    last = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            body = _request(path, timeout)
            return ODataResult(rows=body.get("value", []),
                               executed_query=urllib.parse.unquote_plus(path),
                               executed_at=started)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code == 429:
                # Back off rather than hammer; a public government API that starts
                # rate-limiting is telling us to stop, not to try harder.
                break
            if e.code < 500:
                break
        except Exception as e:                        # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        if attempt < MAX_RETRIES:
            time.sleep(2)
    return ODataResult(rows=[], executed_query=urllib.parse.unquote_plus(path),
                       executed_at=started, upstream_status="unavailable", detail=last)


def fetch_all(entity: str, *, filter_: str = "", select: str = "",
              row_cap: int = DEFAULT_ROW_CAP, timeout: int = TIMEOUT_S) -> ODataResult:
    """Every matching row, paged with $skip and reconciled against odata.count.

    Raises IncompleteFetch if the server reports more rows than we could collect and we
    are NOT at the cap — that is a paging bug, and returning a short list would look
    like a complete answer. Hitting the cap is different: it is deliberate, and reported
    as `truncated`.
    """
    started = _utc_now()
    rows: list = []
    total: int | None = None
    skip = 0
    base_q = {}
    if filter_:
        base_q["$filter"] = filter_
    if select:
        base_q["$select"] = select
    shown = f"{entity}?{urllib.parse.urlencode(base_q)}" if base_q else entity

    while True:
        q = dict(base_q, **{"$inlinecount": "allpages", "$top": PAGE_SIZE, "$skip": skip})
        path = f"{entity}?{urllib.parse.urlencode(q)}"
        try:
            body = _request(path, timeout)
        except Exception as e:                        # noqa: BLE001
            return ODataResult(rows=[], executed_query=urllib.parse.unquote_plus(shown),
                               executed_at=started, upstream_status="unavailable",
                               detail=f"{type(e).__name__}: {e}", total_count=total)
        page = body.get("value", [])
        if total is None:
            try:
                total = int(body.get("odata.count"))
            except (TypeError, ValueError):
                total = None
        rows += page
        skip += PAGE_SIZE
        if not page:
            break
        if len(rows) >= row_cap:
            return ODataResult(rows=rows[:row_cap], executed_query=urllib.parse.unquote_plus(shown),
                               executed_at=started, upstream_status="capped",
                               total_count=total, truncated=True,
                               detail=f"row_cap={row_cap} reached; {total} row(s) exist")
        if total is not None and len(rows) >= total:
            break

    if total is not None and len(rows) < total:
        raise IncompleteFetch(
            f"{entity}: collected {len(rows)} of {total} rows and the server sent no more. "
            "Refusing to return a partial result as if it were complete.")
    return ODataResult(rows=rows, executed_query=urllib.parse.unquote_plus(shown),
                       executed_at=started, total_count=total)


class IncompleteFetch(RuntimeError):
    """Paging could not account for every row the server said exists."""


def health(timeout: int = 20) -> dict:
    """Is the feed reachable? Cheapest possible probe.

    Reported separately from any query so `corpus_overview` can say the live half is
    down without a caller having to infer it from an empty search."""
    r = fetch("LegislativeSessions", select="SessionKey", top=1, timeout=timeout)
    return {"reachable": r.ok, "checked_at": r.executed_at,
            "detail": r.detail or f"{len(r.rows)} row(s) returned", "source": BASE}
