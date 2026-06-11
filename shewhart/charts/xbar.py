"""Xbar-R and Xbar-S charts for subgrouped data.

Built on the I-MR template: one flat function per chart, Phase I fit or
Phase II frozen-baseline evaluation, structured signals, full provenance.
Formulas per Montgomery (8th ed.), ch. 6; all factors computed in
``shewhart.constants``.

v0.1 supports equal subgroup sizes; stair-step limits for variable sizes
arrive in a later release (the error message shows the interim options).
"""

from __future__ import annotations

import math
import pathlib
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .._constants import A2, A3, B3, B4, D3, D4, c4, d2
from .._registry import register
from .._result import Baseline, Result, Signal, data_hash, utcnow
from .._rules import apply_rules, resolve_ruleset
from .._version import __version__


def _prepare(data: Any, value: str | None, subgroup: str | None, fname: str):
    if not isinstance(data, pd.DataFrame):
        raise ValueError(
            f"{fname}() needs a tidy DataFrame with one row per measurement. "
            f'Example: sw.{fname}(df, value="torque", subgroup="batch"). '
            "For individual values (no subgroups), use sw.imr()."
        )
    for arg, name in ((value, "value"), (subgroup, "subgroup")):
        if arg is None or arg not in data.columns:
            raise ValueError(
                f"{fname}() requires {name}= naming a column. "
                f"Columns: {list(data.columns)}. "
                f'Example: sw.{fname}(df, value="torque", subgroup="batch")'
            )

    frame = data[[value, subgroup]].dropna()
    labels = list(pd.unique(frame[subgroup]))
    groups = [frame.loc[frame[subgroup] == lab, value].to_numpy("float64") for lab in labels]
    sizes = {len(g) for g in groups}
    if len(sizes) > 1:
        raise ValueError(
            f"{fname}() currently requires equal subgroup sizes, got {sorted(sizes)}. "
            "Stair-step limits for variable sizes land in a later release. "
            "Until then: drop incomplete subgroups, or chart subgroup means with sw.imr()."
        )
    n = sizes.pop()
    if n < 2:
        raise ValueError(
            f"{fname}() needs subgroups of at least 2 observations, got n={n}. "
            "For individual values use sw.imr()."
        )
    return labels, np.vstack(groups), n


def _resolve(limits: Any, chart: str, keys: tuple[str, ...]) -> Baseline:
    if isinstance(limits, (str, pathlib.Path)):
        limits = Baseline.load(limits)
    if isinstance(limits, Baseline):
        if limits.chart != chart:
            raise ValueError(
                f"This baseline was fitted for {limits.chart!r}, not {chart!r}. "
                f"Fit a matching one: sw.{chart}(df_hist, ...).baseline"
            )
        return limits
    if isinstance(limits, Mapping):
        missing = [k for k in keys if k not in limits]
        if missing:
            raise ValueError(
                f"limits mapping is missing {missing}. Required keys: {list(keys)}. "
                f"Easiest fix: sw.{chart}(df_hist, ...).baseline"
            )
        return Baseline(
            chart=chart,
            stats={k: float(limits[k]) for k in keys},
            n=int(limits.get("n", 0)),
            created_at=str(limits.get("created_at", "")),
            version=str(limits.get("version", "")),
        )
    raise TypeError(
        f"limits must be a Baseline, mapping, or path to a baseline JSON, "
        f"got {type(limits).__name__}."
    )


def _subgrouped(
    fname: str,
    data: Any,
    value: str | None,
    subgroup: str | None,
    rules: str | None,
    limits: Any,
    spread_name: str,
) -> Result:
    labels, mat, n = _prepare(data, value, subgroup, fname)
    means = mat.mean(axis=1)

    if spread_name == "range":
        spread = mat.max(axis=1) - mat.min(axis=1)
        to_sigma, lo, hi = d2(n), D3(n), D4(n)
    else:
        spread = mat.std(axis=1, ddof=1)
        to_sigma, lo, hi = c4(n), B3(n), B4(n)

    keys = ("xbar_center", "sigma_within", f"{spread_name[0]}_center", "n_sub")
    if limits is None:
        center = float(means.mean())
        spread_center = float(spread.mean())
        sigma = spread_center / to_sigma
        baseline = Baseline(
            chart=fname,
            stats={
                "xbar_center": center,
                "sigma_within": sigma,
                f"{spread_name[0]}_center": spread_center,
                "n_sub": n,
            },
            n=int(mat.size),
            created_at=utcnow(),
            version=__version__,
        )
        source = "fitted (Phase I)"
    else:
        baseline = _resolve(limits, fname, keys)
        if int(baseline.stats["n_sub"]) != n:
            raise ValueError(
                f"Baseline was fitted with subgroup size n={int(baseline.stats['n_sub'])}, "
                f"but the new data has n={n}. Control limits depend on n - refit, or "
                "subgroup the new data the same way."
            )
        center = float(baseline.stats["xbar_center"])
        sigma = float(baseline.stats["sigma_within"])
        spread_center = float(baseline.stats[f"{spread_name[0]}_center"])
        source = "frozen baseline (Phase II)"

    sigma_xbar = sigma / math.sqrt(n)
    p = spread_name[0]
    stats = {
        "xbar_center": center,
        "xbar_lcl": center - 3.0 * sigma_xbar,
        "xbar_ucl": center + 3.0 * sigma_xbar,
        f"{p}_center": spread_center,
        f"{p}_lcl": lo * spread_center,
        f"{p}_ucl": hi * spread_center,
        "sigma_within": sigma,
        "n_sub": n,
    }

    if sigma_xbar > 0:
        z = (means - center) / sigma_xbar
    else:
        with np.errstate(invalid="ignore"):
            z = np.where(means == center, 0.0, np.sign(means - center) * np.inf)

    signals = [
        Signal(rule=key, chart="xbar", points=points, note=note)
        for key, note, points in apply_rules(z, resolve_ruleset(rules))
    ]
    beyond = (spread > stats[f"{p}_ucl"]) | (
        (stats[f"{p}_lcl"] > 0) & (spread < stats[f"{p}_lcl"])
    )
    signals += [
        Signal(
            rule="beyond_limits",
            chart=p,
            points=(int(i),),
            note=f"subgroup {spread_name} beyond control limits",
        )
        for i in np.flatnonzero(beyond)
    ]

    x_flagged = {pt for s in signals if s.chart == "xbar" for pt in s.points}
    s_flagged = {pt for s in signals if s.chart == p for pt in s.points}
    table = pd.DataFrame(
        {
            "mean": means,
            spread_name: spread,
            "mean_signal": [i in x_flagged for i in range(len(means))],
            f"{spread_name}_signal": [i in s_flagged for i in range(len(means))],
        },
        index=pd.Index(labels, name=subgroup),
    )

    return Result(
        method=fname,
        params={
            "value": value,
            "subgroup": subgroup,
            "rules": rules,
            "limits": "frozen" if limits is not None else "fitted",
        },
        stats=stats,
        signals=tuple(signals),
        meta={
            "n": int(len(means)),
            "n_total": int(mat.size),
            "version": __version__,
            "input": data_hash(mat),
            "computed_at": utcnow(),
            "source": source,
        },
        baseline=baseline,
        _table=table,
    )


@register("xbar_r")
def xbar_r(
    data: Any,
    *,
    value: str | None = None,
    subgroup: str | None = None,
    rules: str | None = "nelson",
    limits: Any = None,
) -> Result:
    """Xbar-R chart: subgroup means with limits from the average range.

        r = sw.xbar_r(df, value="torque", subgroup="batch", rules="nelson")
    """
    return _subgrouped("xbar_r", data, value, subgroup, rules, limits, "range")


@register("xbar_s")
def xbar_s(
    data: Any,
    *,
    value: str | None = None,
    subgroup: str | None = None,
    rules: str | None = "nelson",
    limits: Any = None,
) -> Result:
    """Xbar-S chart: subgroup means with limits from the average std deviation.

        r = sw.xbar_s(df, value="torque", subgroup="batch", rules="nelson")
    """
    return _subgrouped("xbar_s", data, value, subgroup, rules, limits, "stdev")
