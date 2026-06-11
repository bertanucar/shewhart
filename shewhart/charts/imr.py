"""Individuals & Moving Range (I-MR / XmR) chart.

The reference implementation every later chart copies: one flat function,
Phase I (fit) and Phase II (frozen baseline) through the same call, structured
rule signals, full provenance. Formulas per Montgomery (8th ed.), ch. 6.
"""

from __future__ import annotations

import pathlib
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .._constants import D4, d2
from .._registry import register
from .._result import Baseline, Result, Signal, data_hash, utcnow
from .._rules import apply_rules, resolve_ruleset
from .._version import __version__

_BASELINE_KEYS = ("i_center", "sigma_within", "mr_center")


def _as_series(data: Any, value: str | None) -> pd.Series:
    if isinstance(data, pd.DataFrame):
        if value is None or value not in data.columns:
            raise ValueError(
                f"imr() got a DataFrame, so value= must name the measurement "
                f"column. Columns: {list(data.columns)}. "
                'Example: sw.imr(df, value="torque")'
            )
        s = data[value]
    elif isinstance(data, pd.Series):
        s = data
    else:
        s = pd.Series(np.asarray(data, dtype="float64"))
    return s.astype("float64").dropna()


def _resolve_baseline(limits: Any) -> Baseline:
    if isinstance(limits, Baseline):
        return limits
    if isinstance(limits, (str, pathlib.Path)):
        return Baseline.load(limits)
    if isinstance(limits, Mapping):
        missing = [k for k in _BASELINE_KEYS if k not in limits]
        if missing:
            raise ValueError(
                f"limits mapping is missing {missing}. Required keys: "
                f"{list(_BASELINE_KEYS)}. Easiest fix: pass the Baseline from a "
                'fit instead: sw.imr(df_hist, value="x").baseline'
            )
        return Baseline(
            chart="imr",
            stats={k: float(limits[k]) for k in _BASELINE_KEYS},
            n=int(limits.get("n", 0)),
            created_at=str(limits.get("created_at", "")),
            version=str(limits.get("version", "")),
        )
    raise TypeError(
        f"limits must be a Baseline, mapping, or path to a baseline JSON, "
        f"got {type(limits).__name__}. "
        'Example: sw.imr(df_new, value="x", limits="line3_baseline.json")'
    )


@register("imr")
def imr(
    data: Any,
    *,
    value: str | None = None,
    rules: str | None = "nelson",
    limits: Any = None,
) -> Result:
    """Individuals & Moving Range chart.

    Phase I (estimate limits from the data itself):

        >>> r = imr([10.2, 10.4, 10.1, 10.5, 10.3, 10.2, 10.6], rules="none")
        >>> r.ok
        True

    Phase II (judge new data against a frozen baseline):

        r = imr(df_new, value="torque", limits="line3_baseline.json")
        sys.exit(0 if r.ok else 1)
    """
    s = _as_series(data, value)
    if len(s) < 2:
        raise ValueError(
            f"imr() needs at least 2 observations, got {len(s)}. "
            "Collect more data or check your NaN filtering."
        )

    x = s.to_numpy()
    mr = np.abs(np.diff(x))

    if limits is None:
        center = float(x.mean())
        mr_center = float(mr.mean())
        sigma = mr_center / d2(2)
        baseline = Baseline(
            chart="imr",
            stats={"i_center": center, "sigma_within": sigma, "mr_center": mr_center},
            n=int(len(s)),
            created_at=utcnow(),
            version=__version__,
        )
        source = "fitted (Phase I)"
    else:
        baseline = _resolve_baseline(limits)
        center = float(baseline.stats["i_center"])
        sigma = float(baseline.stats["sigma_within"])
        mr_center = float(baseline.stats["mr_center"])
        source = "frozen baseline (Phase II)"

    stats = {
        "i_center": center,
        "i_lcl": center - 3.0 * sigma,
        "i_ucl": center + 3.0 * sigma,
        "mr_center": mr_center,
        "mr_lcl": 0.0,
        "mr_ucl": D4(2) * mr_center,
        "sigma_within": sigma,
    }

    if sigma > 0:
        z = (x - center) / sigma
    else:
        with np.errstate(invalid="ignore"):
            z = np.where(x == center, 0.0, np.sign(x - center) * np.inf)

    signals = [
        Signal(rule=key, chart="i", points=points, note=note)
        for key, note, points in apply_rules(z, resolve_ruleset(rules))
    ]
    mr_beyond = np.flatnonzero(mr > stats["mr_ucl"]) + 1  # MR i ends at point i
    signals += [
        Signal(
            rule="beyond_limits",
            chart="mr",
            points=(int(i),),
            note="moving range beyond UCL",
        )
        for i in mr_beyond
    ]

    i_flagged = {p for sig in signals if sig.chart == "i" for p in sig.points}
    mr_flagged = {p for sig in signals if sig.chart == "mr" for p in sig.points}
    table = pd.DataFrame(
        {
            "value": x,
            "moving_range": np.concatenate(([np.nan], mr)),
            "i_signal": [i in i_flagged for i in range(len(x))],
            "mr_signal": [i in mr_flagged for i in range(len(x))],
        },
        index=s.index,
    )

    return Result(
        method="imr",
        params={
            "value": value,
            "rules": rules,
            "limits": "frozen" if limits is not None else "fitted",
        },
        stats=stats,
        signals=tuple(signals),
        meta={
            "n": int(len(s)),
            "version": __version__,
            "input": data_hash(x),
            "computed_at": utcnow(),
            "source": source,
        },
        baseline=baseline,
        _table=table,
    )
