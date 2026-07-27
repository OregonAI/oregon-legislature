"""OData client + hybrid backend. No network: every response is a recorded fixture.

The tests that matter most are the ones about being WRONG QUIETLY:
  - a paged fetch that returns 4,000 of 6,178 rows and looks complete
  - a dead feed that renders as "no results" instead of "could not check"
Both have already happened once in this project. These pin them shut.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import odata  # noqa: E402


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()
    def read(self):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def _serve(pages, calls=None):
    """Fake urlopen returning `pages` in order; records request URLs into `calls`."""
    it = iter(pages)
    def _open(req, timeout=None):
        if calls is not None:
            calls.append(req.full_url)
        try:
            nxt = next(it)
        except StopIteration:
            return _Resp({"value": []})
        if isinstance(nxt, Exception):
            raise nxt
        return _Resp(nxt)
    return _open


# ---------- $filter construction ----------

def test_build_filter_ands_equality_clauses():
    f = odata.build_filter(SessionKey="2025R1", MeasureNumber=2049)
    assert f == "SessionKey eq '2025R1' and MeasureNumber eq 2049"


def test_build_filter_escapes_single_quotes():
    """A measure prefix or session key containing a quote must not terminate the
    literal. Only equality over named fields is offered at all (spec §7.1), but the
    escaping still has to be right."""
    assert odata.build_filter(X="O'Brien") == "X eq 'O''Brien'"


def test_build_filter_skips_none():
    assert odata.build_filter(A="x", B=None) == "A eq 'x'"


# ---------- paging: the silent-truncation guard ----------

def test_fetch_all_pages_until_the_count_is_satisfied(monkeypatch):
    calls = []
    pages = [{"odata.count": "3", "value": [{"i": 1}, {"i": 2}]},
             {"odata.count": "3", "value": [{"i": 3}]}]
    monkeypatch.setattr(odata.urllib.request, "urlopen", _serve(pages, calls))
    monkeypatch.setattr(odata, "PAGE_SIZE", 2)
    r = odata.fetch_all("Measures")
    assert [x["i"] for x in r.rows] == [1, 2, 3]
    assert r.total_count == 3 and r.upstream_status == "live" and not r.truncated
    assert "%24skip=0" in calls[0] or "$skip=0" in calls[0]
    assert "%24skip=2" in calls[1] or "$skip=2" in calls[1]


def test_fetch_all_raises_rather_than_return_a_short_list(monkeypatch):
    """THE bug this guard exists for: the server says 6,178 rows exist, sends fewer,
    and stops. Returning what we got would look like a complete answer — which is
    exactly how the '66% of measures have a document' figure was produced."""
    pages = [{"odata.count": "6178", "value": [{"i": 1}]}, {"odata.count": "6178", "value": []}]
    monkeypatch.setattr(odata.urllib.request, "urlopen", _serve(pages))
    monkeypatch.setattr(odata, "PAGE_SIZE", 1)
    with pytest.raises(odata.IncompleteFetch, match="1 of 6178"):
        odata.fetch_all("MeasureDocuments")


def test_row_cap_truncates_loudly(monkeypatch):
    pages = [{"odata.count": "100", "value": [{"i": n} for n in range(10)]}]
    monkeypatch.setattr(odata.urllib.request, "urlopen", _serve(pages))
    monkeypatch.setattr(odata, "PAGE_SIZE", 10)
    r = odata.fetch_all("Measures", row_cap=5)
    assert len(r.rows) == 5
    assert r.truncated is True and r.upstream_status == "capped"
    assert r.envelope()["truncated"] is True and r.envelope()["total_count"] == 100


# ---------- failure is not emptiness ----------

def test_unreachable_feed_is_unavailable_not_empty(monkeypatch):
    monkeypatch.setattr(odata.urllib.request, "urlopen",
                        _serve([OSError("connection refused")] * (odata.MAX_RETRIES + 1)))
    r = odata.fetch("Measures", top=1)
    assert r.rows == []
    assert r.upstream_status == "unavailable" and r.ok is False
    assert "OSError" in r.detail


def test_fetch_all_unreachable_is_unavailable(monkeypatch):
    monkeypatch.setattr(odata.urllib.request, "urlopen", _serve([TimeoutError("slow")] * (odata.MAX_RETRIES + 1)))
    r = odata.fetch_all("Measures")
    assert r.rows == [] and r.upstream_status == "unavailable" and r.ok is False


def test_429_is_not_retried(monkeypatch):
    """A public API that starts rate-limiting is telling us to stop, not try harder."""
    import urllib.error
    calls = []
    def _open(req, timeout=None):
        calls.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
    monkeypatch.setattr(odata.urllib.request, "urlopen", _open)
    r = odata.fetch("Measures", top=1)
    assert r.upstream_status == "unavailable" and len(calls) == 1


# ---------- the envelope ----------

def test_every_result_carries_query_and_clock(monkeypatch):
    monkeypatch.setattr(odata.urllib.request, "urlopen", _serve([{"value": [{"a": 1}]}]))
    env = odata.fetch("Measures", filter_="SessionKey eq '2025R1'", top=1).envelope()
    assert set(env) >= {"executed_query", "executed_at", "source", "upstream_status"}
    assert "SessionKey eq '2025R1'" in env["executed_query"]   # unescaped, auditable
    assert env["executed_at"].endswith("Z")


# ---------- measure ids ----------

@pytest.mark.parametrize("doc_id,expected", [
    ("measure-2025r1-hb2049", ("2025R1", "HB", 2049)),
    ("measure-2024r1-sb1", ("2024R1", "SB", 1)),
    ("measures", None),
    ("entity-measures", None),
    ("", None),
])
def test_parse_measure_id(doc_id, expected):
    from odata_backend import parse_measure_id
    assert parse_measure_id(doc_id) == expected


# ---------- live status blocks ----------

def _backend(tmp_path):
    from odata_backend import HybridBackend
    class _Cfg:
        root = tmp_path
        index_headings = {}
    return HybridBackend.__new__(HybridBackend)


def test_unavailable_status_omits_found(monkeypatch, tmp_path):
    """`found: False` means the feed answered and has no such measure. When we could not
    ask, the key must be ABSENT — the two are opposite answers for a caller."""
    monkeypatch.setattr(odata.urllib.request, "urlopen", _serve([OSError("down")] * (odata.MAX_RETRIES + 1)))
    be = _backend(tmp_path)
    block = be.live_status("measure-2025r1-hb2049")
    assert block["unavailable"] is True
    assert "found" not in block
    assert block["as_of"]["upstream_status"] == "unavailable"


def test_found_false_when_feed_answers_with_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(odata.urllib.request, "urlopen", _serve([{"value": []}]))
    block = _backend(tmp_path).live_status("measure-2025r1-hb9999")
    assert block["found"] is False and "unavailable" not in block


def test_live_status_is_none_for_non_measures(tmp_path):
    assert _backend(tmp_path).live_status("measures") is None
