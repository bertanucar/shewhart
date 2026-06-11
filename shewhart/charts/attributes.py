"""Attribute control charts: p, np, c, u.

Terminology follows the AIAG SPC manual: p/np charts track nonconforming
UNITS (defectives), c/u charts track nonconformities (defects). The p and u
charts accept varying subgroup sizes and produce per-point stair-step limits;
the table carries lcl/ucl columns for every point.

Run rules: attribute charts support the four tests that are standard for
attribute data (beyond limits, 9 on one side, 6 trending, 14 alternating),
selected with rules="nelson". Zone tests (Nelson 5-8) assume symmetric
normal zones and are not offered here.
"""

from __future__ import annotations

import math
import pathlib
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .._registry import register
from .._result import Baseline, Result, Signal, data_hash, utcnow
from .._rules import RULES
from .._version import __version__

_ATTR_RUN_RULES = ("nelson_2", "nelson_3", "nelson_4")


def _attr_ruleset(rules: str | None, fname: str) -> bool:
    """True if run rules requested; teaching error for unsupported sets."""
    if rules in (None, "none"):
        return False
    if rules == "nelson":
        return True
    raise ValueError(
        f"{fname}() supports rules=\"nelson\" (the four attribute-chart tests) "
        f'or rules="none", got {rules!r}. Zone tests are for variables charts.'
    )


def _counts(data: Any, column: str | None, what: str, fname: str) -> tuple[pd.Series, Any]:
    if isinstance(data, pd.DataFrame):
        if column is None or column not in data.columns:
            raise ValueError(
                f"{fname}() got a DataFrame, so {what}= must name the count "
                f"column. Columns: {list(data.columns)}. "
                f'Example: sw.{fname}(df, {what}="{what}", size="inspected")'
            )
        s = data[column]
    else:
        s = pd.Series(np.asarray(data, dtype="float64"))
    s = s.dropna().astype("float64")
    if len(s) < 2:
        raise ValueError(f"{fname}() needs at least 2 periods, got {len(s)}.")
    if (s < 0).any() or (s % 1 != 0).any():
        raise ValueError(
            f"{fname}() expects non-negative integer counts in {what}, "
            f"found values like {s[(s < 0) | (s % 1 != 0)].head(3).tolist()}."
        )
    return s, s.index


def _sizes(data: Any, size: Any, index, k: int, fname: str, integral: bool = True) -> np.ndarray:
    if size is None:
        raise ValueError(
            f"{fname}() requires size= (subgroup size per period): a column "
            f"name, a constant, or a sequence. "
            f'Example: sw.{fname}(df, defectives="rejects", size="inspected")'
        )
    if isinstance(size, str):
        if not isinstance(data, pd.DataFrame) or size not in data.columns:
            raise ValueError(
                f'{fname}(): size="{size}" must be a column of the DataFrame. '
                f"Columns: {list(data.columns) if isinstance(data, pd.DataFrame) else 'n/a'}"
            )
        arr = data[size].loc[index].to_numpy("float64")
    elif np.isscalar(size):
        arr = np.full(k, float(size))
    else:
        arr = np.asarray(size, dtype="float64")
        if len(arr) != k:
            raise ValueError(
                f"{fname}(): size sequence has length {len(arr)}, expected {k}."
            )
    if (arr <= 0).any() or (integral and (arr % 1 != 0).any()):
        raise ValueError(f"{fname}(): sizes must be positive" + (" integers." if integral else "."))
    return arr


def _resolve(limits: Any, chart: str, keys: tuple[str, ...]) -> Baseline:
    if isinstance(limits, (str, pathlib.Path)):
        limits = Baseline.load(limits)
    if isinstance(limits, Baseline):
        if limits.chart != chart:
            raise ValueError(
                f"This baseline was fitted for {limits.chart!r}, not {chart!r}."
            )
        return limits
    if isinstance(limits, Mapping):
        missing = [k for k in keys if k not in limits]
        if missing:
            raise ValueError(
                f"limits mapping is missing {missing}. Required: {list(keys)}. "
                f"Easiest fix: sw.{chart}(df_hist, ...).baseline"
            )
        return Baseline(chart=chart, stats={k: float(limits[k]) for k in keys},
                        n=int(limits.get("n", 0)), created_at="", version="")
    raise TypeError(
        f"limits must be a Baseline, mapping, or path, got {type(limits).__name__}."
    )


def _run_rule_signals(values: np.ndarray, center: float, use_rules: bool) -> list[Signal]:
    if not use_rules:
        return []
    out: list[Signal] = []
    centered = values - center
    for key in _ATTR_RUN_RULES:
        rule = RULES[key]
        for points in rule.fn(centered):
            out.append(Signal(rule=key, chart="attr", points=points, note=rule.note))
    return out


def _assemble(
    *,
    method: str,
    plotted: np.ndarray,
    lcl: np.ndarray,
    ucl: np.ndarray,
    center: float,
    use_rules: bool,
    table_cols: dict,
    index,
    stats: dict,
    params: dict,
    baseline: Baseline,
    source: str,
    n_points: int,
    hashed: np.ndarray,
) -> Result:
    beyond = (plotted > ucl) | (plotted < lcl)
    signals = [
        Signal(rule="nelson_1", chart="attr", points=(int(i),),
               note="1 point beyond control limits")
        for i in np.flatnonzero(beyond)
    ]
    signals += _run_rule_signals(plotted, center, use_rules)
    signals.sort(key=lambda s: (s.rule, s.points))

    flagged = {p for s in signals for p in s.points}
    table = pd.DataFrame(
        {**table_cols, "lcl": lcl, "ucl": ucl,
         "signal": [i in flagged for i in range(n_points)]},
        index=index,
    )
    return Result(
        method=method,
        params=params,
        stats=stats,
        signals=tuple(signals),
        meta={
            "n": n_points,
            "version": __version__,
            "input": data_hash(hashed),
            "computed_at": utcnow(),
            "source": source,
        },
        baseline=baseline,
        _table=table,
    )


@register("p_chart")
def p_chart(data: Any, *, defectives: str | None = None, size: Any = None,
            rules: str | None = "nelson", limits: Any = None) -> Result:
    """p chart: proportion of nonconforming units, varying sizes supported.

        r = sw.p_chart(df, defectives="rejects", size="inspected")
    """
    d, index = _counts(data, defectives, "defectives", "p_chart")
    n = _sizes(data, size, index, len(d), "p_chart")
    dv = d.to_numpy("float64")
    if (dv > n).any():
        raise ValueError("p_chart(): defectives cannot exceed size in any period.")

    prop = dv / n
    if limits is None:
        center = float(dv.sum() / n.sum())
        baseline = Baseline("p_chart", {"p_center": center}, int(n.sum()),
                            utcnow(), __version__)
        source = "fitted (Phase I)"
    else:
        baseline = _resolve(limits, "p_chart", ("p_center",))
        center = float(baseline.stats["p_center"])
        source = "frozen baseline (Phase II)"

    sigma = np.sqrt(center * (1.0 - center) / n)
    lcl = np.maximum(0.0, center - 3.0 * sigma)
    ucl = np.minimum(1.0, center + 3.0 * sigma)

    stats = {"p_center": center}
    if len(set(n)) == 1:
        stats["p_lcl"], stats["p_ucl"] = float(lcl[0]), float(ucl[0])

    return _assemble(
        method="p_chart", plotted=prop, lcl=lcl, ucl=ucl, center=center,
        use_rules=_attr_ruleset(rules, "p_chart"),
        table_cols={"defectives": dv, "size": n, "proportion": prop},
        index=index, stats=stats,
        params={"defectives": defectives, "size": size if np.isscalar(size) else str(size),
                "rules": rules, "limits": "frozen" if limits is not None else "fitted"},
        baseline=baseline, source=source, n_points=len(dv), hashed=np.vstack([dv, n]),
    )


@register("np_chart")
def np_chart(data: Any, *, defectives: str | None = None, size: Any = None,
             rules: str | None = "nelson", limits: Any = None) -> Result:
    """np chart: count of nonconforming units, constant subgroup size.

        r = sw.np_chart(df, defectives="rejects", size=50)
    """
    d, index = _counts(data, defectives, "defectives", "np_chart")
    n = _sizes(data, size, index, len(d), "np_chart")
    if len(set(n)) != 1:
        raise ValueError(
            "np_chart() requires a constant subgroup size; got varying sizes. "
            "Use sw.p_chart() for varying sizes."
        )
    n0 = float(n[0])
    dv = d.to_numpy("float64")
    if (dv > n0).any():
        raise ValueError("np_chart(): defectives cannot exceed size.")

    if limits is None:
        p = float(dv.sum() / (n0 * len(dv)))
        baseline = Baseline("np_chart", {"p_center": p, "n_sub": n0},
                            int(n0 * len(dv)), utcnow(), __version__)
        source = "fitted (Phase I)"
    else:
        baseline = _resolve(limits, "np_chart", ("p_center", "n_sub"))
        if float(baseline.stats["n_sub"]) != n0:
            raise ValueError(
                f"Baseline subgroup size n={baseline.stats['n_sub']:g} does not "
                f"match the data (n={n0:g}). Limits depend on n."
            )
        p = float(baseline.stats["p_center"])
        source = "frozen baseline (Phase II)"

    center = n0 * p
    sigma = math.sqrt(center * (1.0 - p))
    lcl = np.full(len(dv), max(0.0, center - 3.0 * sigma))
    ucl = np.full(len(dv), center + 3.0 * sigma)

    return _assemble(
        method="np_chart", plotted=dv, lcl=lcl, ucl=ucl, center=center,
        use_rules=_attr_ruleset(rules, "np_chart"),
        table_cols={"defectives": dv},
        index=index,
        stats={"np_center": center, "np_lcl": float(lcl[0]), "np_ucl": float(ucl[0])},
        params={"defectives": defectives, "size": n0, "rules": rules,
                "limits": "frozen" if limits is not None else "fitted"},
        baseline=baseline, source=source, n_points=len(dv), hashed=dv,
    )


@register("c_chart")
def c_chart(data: Any, *, defects: str | None = None,
            rules: str | None = "nelson", limits: Any = None) -> Result:
    """c chart: nonconformities per inspection unit, constant opportunity.

        r = sw.c_chart([3, 2, 4, 1, 3])
    """
    c, index = _counts(data, defects, "defects", "c_chart")
    cv = c.to_numpy("float64")

    if limits is None:
        center = float(cv.mean())
        baseline = Baseline("c_chart", {"c_center": center}, len(cv),
                            utcnow(), __version__)
        source = "fitted (Phase I)"
    else:
        baseline = _resolve(limits, "c_chart", ("c_center",))
        center = float(baseline.stats["c_center"])
        source = "frozen baseline (Phase II)"

    sigma = math.sqrt(center)
    lcl = np.full(len(cv), max(0.0, center - 3.0 * sigma))
    ucl = np.full(len(cv), center + 3.0 * sigma)

    return _assemble(
        method="c_chart", plotted=cv, lcl=lcl, ucl=ucl, center=center,
        use_rules=_attr_ruleset(rules, "c_chart"),
        table_cols={"defects": cv},
        index=index,
        stats={"c_center": center, "c_lcl": float(lcl[0]), "c_ucl": float(ucl[0])},
        params={"defects": defects, "rules": rules,
                "limits": "frozen" if limits is not None else "fitted"},
        baseline=baseline, source=source, n_points=len(cv), hashed=cv,
    )


@register("u_chart")
def u_chart(data: Any, *, defects: str | None = None, size: Any = None,
            rules: str | None = "nelson", limits: Any = None) -> Result:
    """u chart: nonconformities per unit, varying number of units supported.

        r = sw.u_chart(df, defects="flaws", size="units")
    """
    d, index = _counts(data, defects, "defects", "u_chart")
    n = _sizes(data, size, index, len(d), "u_chart", integral=False)
    dv = d.to_numpy("float64")
    per_unit = dv / n

    if limits is None:
        center = float(dv.sum() / n.sum())
        baseline = Baseline("u_chart", {"u_center": center}, int(len(dv)),
                            utcnow(), __version__)
        source = "fitted (Phase I)"
    else:
        baseline = _resolve(limits, "u_chart", ("u_center",))
        center = float(baseline.stats["u_center"])
        source = "frozen baseline (Phase II)"

    sigma = np.sqrt(center / n)
    lcl = np.maximum(0.0, center - 3.0 * sigma)
    ucl = center + 3.0 * sigma

    stats = {"u_center": center}
    if len(set(n)) == 1:
        stats["u_lcl"], stats["u_ucl"] = float(lcl[0]), float(ucl[0])

    return _assemble(
        method="u_chart", plotted=per_unit, lcl=lcl, ucl=ucl, center=center,
        use_rules=_attr_ruleset(rules, "u_chart"),
        table_cols={"defects": dv, "size": n, "per_unit": per_unit},
        index=index, stats=stats,
        params={"defects": defects, "size": size if np.isscalar(size) else str(size),
                "rules": rules, "limits": "frozen" if limits is not None else "fitted"},
        baseline=baseline, source=source, n_points=len(dv), hashed=np.vstack([dv, n]),
    )
