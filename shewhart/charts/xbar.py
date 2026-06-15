"""Xbar-R and Xbar-S charts for subgrouped data.

Built on the I-MR template: one flat function per chart, Phase I fit or
Phase II frozen-baseline evaluation, structured signals, full provenance.
Formulas per Montgomery (8th ed.), ch. 6; all factors computed in
``shewhart.constants``.

Xbar-R requires equal subgroup sizes. Xbar-S also accepts variable sizes,
charting per-subgroup stair-step limits from the pooled sigma.
"""

from __future__ import annotations

import math
import pathlib
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .._constants import A2, A3, B3, B4, B5, B6, D3, D4, c4, d2
from .._data import time_subgroups
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
    time_labels = time_subgroups(data, subgroup)
    if time_labels is not None:
        data = data.assign(__window__=time_labels)
        subgroup = "__window__"
    for arg, name in ((value, "value"), (subgroup, "subgroup")):
        if arg is None or arg not in data.columns:
            raise ValueError(
                f"{fname}() requires {name}= naming a column (or, with a "
                f"DatetimeIndex, a fixed time window like subgroup=\"1H\"). "
                f"Columns: {list(data.columns)}. "
                f'Example: sw.{fname}(df, value="torque", subgroup="batch")'
            )

    frame = data[[value, subgroup]].dropna()
    labels = list(pd.unique(frame[subgroup]))
    groups = [frame.loc[frame[subgroup] == lab, value].to_numpy("float64") for lab in labels]
    sizes = np.array([len(g) for g in groups])
    if sizes.min() < 2:
        raise ValueError(
            f"{fname}() needs subgroups of at least 2 observations, got "
            f"n={int(sizes.min())}. For individual values use sw.imr()."
        )
    return labels, groups, sizes


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


_METHODS = {"range": ("rbar",), "stdev": ("sbar", "pooled")}


def _variable_xbar_s(fname, labels, groups, sizes, value, subgroup, rules, method, base, limits):
    """Xbar-S with variable subgroup sizes: pooled sigma, stair-step limits.

    Sigma is estimated once from the pooled within-subgroup variance and
    unbiased through c4. This is the preferred estimator when sizes differ;
    the range and average-S estimators are defined for a constant n. The
    Xbar and S limits are then set per subgroup: xbar_center +/-
    3*sigma/sqrt(n_i) and the B5/B6 sigma factors at each n_i. A baseline is
    marked variable with n_sub=0, and Phase II derives per-subgroup limits
    from its sigma.
    """
    means = np.array([g.mean() for g in groups])
    s = np.array([g.std(ddof=1) for g in groups])
    n_sub = sizes.astype(int)

    if base is None:
        df = int((n_sub - 1).sum())
        pooled_sd = math.sqrt(float(np.sum((n_sub - 1) * s**2) / df))
        sigma = pooled_sd / c4(df + 1)
        center = float(np.sum(n_sub * means) / n_sub.sum())
        baseline = Baseline(
            chart=fname,
            stats={"xbar_center": center, "sigma_within": sigma,
                   "s_center": 0.0, "n_sub": 0},
            n=int(n_sub.sum()),
            created_at=utcnow(),
            version=__version__,
        )
        source = "fitted (Phase I), pooled sigma over variable subgroup sizes"
    else:
        center = float(base.stats["xbar_center"])
        sigma = float(base.stats["sigma_within"])
        baseline = base
        source = "frozen baseline (Phase II)"

    sigma_xbar = sigma / np.sqrt(n_sub)
    xbar_lcl = center - 3.0 * sigma_xbar
    xbar_ucl = center + 3.0 * sigma_xbar
    b5 = np.array([B5(int(ni)) for ni in n_sub])
    b6 = np.array([B6(int(ni)) for ni in n_sub])
    s_lcl = b5 * sigma
    s_ucl = b6 * sigma

    if sigma > 0:
        z = (means - center) / sigma_xbar
    else:
        with np.errstate(invalid="ignore"):
            z = np.where(means == center, 0.0, np.sign(means - center) * np.inf)

    signals = [
        Signal(rule=key, chart="xbar", points=points, note=note)
        for key, note, points in apply_rules(z, resolve_ruleset(rules))
    ]
    s_beyond = (s > s_ucl) | (s < s_lcl)
    signals += [
        Signal(rule="beyond_limits", chart="s", points=(int(i),),
               note="subgroup stdev beyond control limits")
        for i in np.flatnonzero(s_beyond)
    ]

    x_flagged = {pt for sig in signals if sig.chart == "xbar" for pt in sig.points}
    s_flagged = {pt for sig in signals if sig.chart == "s" for pt in sig.points}
    table = pd.DataFrame(
        {
            "mean": means,
            "stdev": s,
            "n": n_sub,
            "mean_lcl": xbar_lcl,
            "mean_ucl": xbar_ucl,
            "stdev_lcl": s_lcl,
            "stdev_ucl": s_ucl,
            "mean_signal": [i in x_flagged for i in range(len(means))],
            "stdev_signal": [i in s_flagged for i in range(len(means))],
        },
        index=pd.Index(labels, name=subgroup),
    )

    return Result(
        method=fname,
        params={
            "value": value,
            "subgroup": subgroup,
            "rules": rules,
            "method": method,
            "limits": "frozen" if limits is not None else "fitted",
        },
        stats={"xbar_center": center, "sigma_within": sigma},
        signals=tuple(signals),
        meta={
            "n": int(len(means)),
            "n_total": int(n_sub.sum()),
            "version": __version__,
            "input": data_hash(np.concatenate([np.concatenate(groups),
                                               n_sub.astype("float64")])),
            "computed_at": utcnow(),
            "source": source,
            "variable_sizes": True,
        },
        baseline=baseline,
        _table=table,
    )


def _subgrouped(
    fname: str,
    data: Any,
    value: str | None,
    subgroup: str | None,
    rules: str | None,
    method: str,
    limits: Any,
    spread_name: str,
) -> Result:
    if method not in _METHODS[spread_name]:
        options = " or ".join(repr(m) for m in _METHODS[spread_name])
        raise ValueError(
            f"{fname}() supports method={options}, got {method!r}."
            + (' Pooled estimation lives on sw.xbar_s(method="pooled").'
               if spread_name == "range" else "")
        )

    keys = ("xbar_center", "sigma_within", f"{spread_name[0]}_center", "n_sub")
    labels, groups, sizes = _prepare(data, value, subgroup, fname)
    base = _resolve(limits, fname, keys) if limits is not None else None
    base_variable = base is not None and int(round(float(base.stats.get("n_sub", 0)))) == 0
    variable = int(sizes.min()) != int(sizes.max())

    if (variable or base_variable) and spread_name == "range":
        why = (
            "this baseline was fitted on variable subgroup sizes"
            if base_variable and not variable
            else f"got sizes {sorted(set(sizes.tolist()))}"
        )
        raise ValueError(
            f"xbar_r() needs equal subgroup sizes ({why}). For variable "
            "subgroup sizes use sw.xbar_s(), which sets per-subgroup limits "
            "from the pooled sigma."
        )
    if variable or base_variable:
        return _variable_xbar_s(
            fname, labels, groups, sizes, value, subgroup, rules, method, base, limits
        )

    n = int(sizes[0])
    mat = np.vstack(groups)
    means = mat.mean(axis=1)

    if spread_name == "range":
        spread = mat.max(axis=1) - mat.min(axis=1)
        to_sigma, lo, hi = d2(n), D3(n), D4(n)
    else:
        spread = mat.std(axis=1, ddof=1)
        to_sigma, lo, hi = c4(n), B3(n), B4(n)

    if limits is None:
        center = float(means.mean())
        if method == "pooled":
            df = mat.shape[0] * (n - 1)
            pooled_sd = float(np.sqrt(np.sum((n - 1) * spread**2) / df))
            sigma = pooled_sd / c4(df + 1)
            # display center such that lo/hi factors yield B5/B6 * sigma
            spread_center = c4(n) * sigma
        else:
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
        baseline = base
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
            "method": method,
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
    method: str = "rbar",
    limits: Any = None,
) -> Result:
    """Xbar-R chart: subgroup means with limits from the average range.

        r = sw.xbar_r(df, value="torque", subgroup="batch", rules="nelson")
    """
    return _subgrouped("xbar_r", data, value, subgroup, rules, method, limits, "range")


@register("xbar_s")
def xbar_s(
    data: Any,
    *,
    value: str | None = None,
    subgroup: str | None = None,
    rules: str | None = "nelson",
    method: str = "sbar",
    limits: Any = None,
) -> Result:
    """Xbar-S chart: subgroup means with limits from the average std deviation.

        r = sw.xbar_s(df, value="torque", subgroup="batch", rules="nelson")

    method="pooled" estimates sigma from the pooled standard deviation
    (exact degrees of freedom, unbiased via c4); the S-chart limits then
    correspond to the B5/B6 factors.

    Variable subgroup sizes are supported: sigma comes from the pooled
    within-subgroup variance regardless of ``method`` (the range and
    average-S estimators need a constant n), and each subgroup gets its own
    limits (a stair-step chart). The per-point limits live in the result
    table (``mean_lcl``/``mean_ucl``, ``stdev_lcl``/``stdev_ucl``), so the
    scalar limit keys are absent from ``stats`` when sizes vary.
    """
    return _subgrouped("xbar_s", data, value, subgroup, rules, method, limits, "stdev")
