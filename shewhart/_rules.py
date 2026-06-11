"""Run rules for control charts, built from four primitives.

Each rule operates on the standardized distances z = (x - center) / sigma and
returns point-index tuples, one per violation. Rule definitions follow
Nelson (Journal of Quality Technology 16(4), 1984) and the Western Electric
Statistical Quality Control Handbook (1956).

Rule sets are selected by name and forever-stable alias:

    "nelson"            Nelson rules 1-8
    "western_electric"  WE zone tests 1-4
    "none"              limit checks only, no run rules
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Iterable

import numpy as np

Points = tuple[int, ...]


# -- primitives ---------------------------------------------------------------


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Maximal runs of True in mask as (start, end) inclusive."""
    out: list[tuple[int, int]] = []
    start: int | None = None
    for i, flag in enumerate(mask):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def _run_rule(mask: np.ndarray, k: int) -> list[Points]:
    """Maximal runs of at least k consecutive True points."""
    return [tuple(range(s, e + 1)) for s, e in _runs(mask) if e - s + 1 >= k]


def _merge(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping/adjacent (start, end) windows."""
    if not windows:
        return []
    windows = sorted(windows)
    merged = [windows[0]]
    for s, e in windows[1:]:
        ps, pe = merged[-1]
        if s <= pe + 1:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def _m_of_n(z: np.ndarray, m: int, n: int, threshold: float) -> list[Points]:
    """m out of n consecutive points beyond threshold, same side."""
    out: list[Points] = []
    for side in (1.0, -1.0):
        beyond = side * z > threshold
        windows = [
            (i - n + 1, i)
            for i in range(n - 1, len(z))
            if int(beyond[i - n + 1 : i + 1].sum()) >= m
        ]
        for s, e in _merge(windows):
            out.append(tuple(i for i in range(s, e + 1) if beyond[i]))
    return sorted(out)


def _points_beyond(z: np.ndarray, k: float) -> list[Points]:
    return [(int(i),) for i in np.flatnonzero(np.abs(z) > k)]


def _same_side(z: np.ndarray, k: int) -> list[Points]:
    return sorted(_run_rule(z > 0, k) + _run_rule(z < 0, k))


def _trending(z: np.ndarray, k: int) -> list[Points]:
    d = np.diff(z)
    out: list[Points] = []
    for mask in (d > 0, d < 0):
        for s, e in _runs(mask):
            if e - s + 1 >= k - 1:
                out.append(tuple(range(s, e + 2)))
    return sorted(out)


def _alternating(z: np.ndarray, k: int) -> list[Points]:
    d = np.diff(z)
    if len(d) < 2:
        return []
    alt = d[:-1] * d[1:] < 0
    return [
        tuple(range(s, e + 3)) for s, e in _runs(alt) if (e - s + 3) >= k
    ]


# -- rule table ---------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Rule:
    key: str
    note: str
    fn: Callable[[np.ndarray], list[Points]]


RULES: dict[str, Rule] = {
    r.key: r
    for r in [
        Rule("nelson_1", "1 point beyond 3 sigma", lambda z: _points_beyond(z, 3.0)),
        Rule("nelson_2", "9 in a row on one side of center", lambda z: _same_side(z, 9)),
        Rule("nelson_3", "6 in a row steadily increasing or decreasing", lambda z: _trending(z, 6)),
        Rule("nelson_4", "14 in a row alternating up and down", lambda z: _alternating(z, 14)),
        Rule("nelson_5", "2 of 3 beyond 2 sigma, same side", lambda z: _m_of_n(z, 2, 3, 2.0)),
        Rule("nelson_6", "4 of 5 beyond 1 sigma, same side", lambda z: _m_of_n(z, 4, 5, 1.0)),
        Rule("nelson_7", "15 in a row within 1 sigma", lambda z: _run_rule(np.abs(z) < 1.0, 15)),
        Rule("nelson_8", "8 in a row beyond 1 sigma, either side", lambda z: _run_rule(np.abs(z) > 1.0, 8)),
        Rule("we_1", "1 point beyond 3 sigma", lambda z: _points_beyond(z, 3.0)),
        Rule("we_2", "2 of 3 beyond 2 sigma, same side", lambda z: _m_of_n(z, 2, 3, 2.0)),
        Rule("we_3", "4 of 5 beyond 1 sigma, same side", lambda z: _m_of_n(z, 4, 5, 1.0)),
        Rule("we_4", "8 in a row on one side of center", lambda z: _same_side(z, 8)),
    ]
}

RULESETS: dict[str, tuple[str, ...]] = {
    "nelson": tuple(f"nelson_{i}" for i in range(1, 9)),
    "western_electric": ("we_1", "we_2", "we_3", "we_4"),
    "none": (),
}


def resolve_ruleset(name: str | None) -> tuple[str, ...]:
    if name is None:
        return ()
    try:
        return RULESETS[name]
    except KeyError:
        options = ", ".join(sorted(RULESETS))
        raise ValueError(
            f"Unknown rule set {name!r}. Available: {options}. "
            'Example: sw.imr(df, value="x", rules="nelson")'
        ) from None


def apply_rules(
    z: np.ndarray, ruleset: Iterable[str]
) -> list[tuple[str, str, Points]]:
    """Apply rules to standardized values; returns (rule_key, note, points)."""
    found: list[tuple[str, str, Points]] = []
    for key in ruleset:
        rule = RULES[key]
        for points in rule.fn(z):
            found.append((rule.key, rule.note, points))
    return found
