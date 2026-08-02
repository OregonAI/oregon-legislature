"""Citation schemes: "HB 2049" and friends resolve to mirrored measures.

Closes oregon-legislature#10 — the contract's own resolve_citation example was `HB 2049`,
and this corpus returned `unresolved` while holding the document (search_fallback found
it in the same response). The hook existed, commented out, since step 5.

THE BARE FORM IS GENUINELY AMBIGUOUS, and the scheme says so instead of guessing: the
same bill number recurs across sessions (HB 2049 exists in 2025R1 and elsewhere). The
resolver emits candidate ids for EVERY known session, newest first, and lets
resolve_citation's per-candidate existence filtering keep the real ones — no I/O here,
and "which sessions actually have it" is decided by the corpus's holdings, not by this
file's opinion. A session-qualified citation ("HB 2049 (2020R1)") resolves exactly.

ALL TEN PREFIXES, not just HB/SB: hjr/sjr/hcr/scr/hjm/sjm/hr/sr are 261 mirrored
documents (~4% of the corpus) that a two-prefix scheme would silently orphan.
"""
from __future__ import annotations

from corpus_toolkit.mcp.framework import register_scheme

# Every session with a measures/ directory, NEWEST FIRST — the order candidates are
# offered when a bare citation matches several sessions' holdings. 2018S1 and 2021S1
# hold zero mirrored measures; they stay listed (existence filtering makes them free)
# so the constant is "sessions that exist", not "sessions we happened to mirror".
SESSIONS = ("2026r1", "2025s1", "2025r1", "2024s1", "2024r1", "2023r1", "2022r1",
            "2021s2", "2021s1", "2021r1", "2020s3", "2020s2", "2020s1", "2020r1",
            "2019r1", "2018s1", "2018r1", "2017r1")

_PREFIXES = r"(?:HB|SB|HJR|SJR|HCR|SCR|HJM|SJM|HR|SR)"


def _bare(m, nodes=None):
    prefix, num = m.group("prefix").lower(), int(m.group("num"))
    cands = [f"measure-{s}-{prefix}{num}" for s in SESSIONS]
    return cands, (f"'{m.group(0)}' names no session and bill numbers recur across "
                   f"them — every session holding this measure is returned, newest "
                   f"first; cite as '{m.group('prefix')} {num} (2025R1)' to pin one")


# Registration order matters even under v1.19.0's accumulate-all matching: the exact-id
# and session-qualified schemes are listed first so their precise candidates lead the
# merged list. The bare pattern declines to fire when a parenthetical session follows —
# the qualified scheme owns that text, and an 18-candidate fan plus its ambiguity note
# would be noise on a citation that is not ambiguous.
register_scheme(
    "measure-id",
    r"\bmeasure-(?P<session>\d{4}[rs]\d)-(?P<prefix>[a-z]{2,3})(?P<num>\d{1,5})\b",
    id_template="measure-{session}-{prefix}{num}")

register_scheme(
    "measure-session-qualified",
    rf"\b(?P<prefix>{_PREFIXES})\.?\s*(?P<num>\d{{1,5}})\s*\((?P<session>\d{{4}}[RSrs]\d)\)",
    resolver=lambda m: [f"measure-{m.group('session').lower()}-"
                        f"{m.group('prefix').lower()}{int(m.group('num'))}"])

register_scheme(
    "measure-bare",
    rf"\b(?P<prefix>{_PREFIXES})\.?\s*(?P<num>\d{{1,5}})\b(?!\s*\()",
    resolver=_bare)
