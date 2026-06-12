"""Tabular CUSUM chart.

Upper and lower cumulative sums per Montgomery (8th ed., ch. 9):

    C+_i = max(0, x_i - (center + K) + C+_{i-1})
    C-_i = max(0, (center - K) - x_i + C-_{i-1})

with reference value K = k * sigma (k = 0.5 detects ~1 sigma shifts) and
decision interval H = h * sigma (h = 4 to 5 is customary). A signal fires
when either sum exceeds H.

Like the EWMA, CUSUM statistics are cumulative and therefore autocorrelated;
run rules are deliberately not offered. Note that this is not
``pandas.cumsum``: a plain cumulative sum has no reference value, no reset
at zero, and no decision interval, which is why it cannot serve as a
control chart.
"""

from __future__ import annotations

import pathlib
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .._constants import d2
from .._data import as_series
from .._registry import register
from .._result import Baseline, Result, Signal, data_hash, utcnow
from .._version import __version__


def _resolve(limits: Any) -> tuple[float, float]:
    if isinstance(limits, (str, pathlib.Path)):
        limits = Baseline.load(limits)
    if isinstance(limits, Baseline):
        if limits.chart != "cusum":
            raise ValueError(
                f"This baseline was fitted for {limits.chart!r}, not 'cusum'."
            )
        return float(limits.stats["center"]), float(limits.stats["sigma"])
    if isinstance(limits, Mapping):
        missing = [k for k in ("center", "sigma") if k not in limits]
        if missing:
            raise ValueError(
                f"limits mapping is missing {missing}. Required: ['center', 'sigma']."
            )
        return float(limits["center"]), float(limits["sigma"])
    raise TypeError(
        f"limits must be a Baseline, mapping, or path, got {type(limits).__name__}."
    )


@register("cusum")
def cusum(
    data: Any,
    *,
    value: str | None = None,
    k: float = 0.5,
    h: float = 4.0,
    center: float | None = None,
    sigma: float | None = None,
    limits: Any = None,
) -> Result:
    """Tabular CUSUM chart for detecting small sustained shifts.

        r = sw.cusum(df, value="torque")

    Phase II against known parameters (or a saved baseline):

        r = sw.cusum(df_new, value="torque", center=10.0, sigma=1.0)
    """
    if k <= 0 or h <= 0:
        raise ValueError(
            f"k and h must be positive, got k={k}, h={h}. Customary values: "
            "k=0.5 (detects ~1 sigma shifts), h=4 to 5."
        )

    s = as_series(data, value, "cusum")
    x = s.to_numpy()
    n = len(x)

    if limits is not None:
        center, sigma = _resolve(limits)
    fitted = center is None or sigma is None
    if center is None or sigma is None:
        if n < 2:
            raise ValueError(
                f"cusum() needs at least 2 observations to estimate parameters, "
                f"got {n}. Alternatively pass center= and sigma= explicitly."
            )
        if center is None:
            center = float(x.mean())
        if sigma is None:
            sigma = float(np.abs(np.diff(x)).mean()) / d2(2)
    if sigma <= 0:
        raise ValueError("cusum(): sigma must be positive; the data has no variation.")

    K = k * sigma
    H = h * sigma
    pos = np.empty(n)
    neg = np.empty(n)
    cp = cn = 0.0
    for i, v in enumerate(x):
        cp = max(0.0, v - (center + K) + cp)
        cn = max(0.0, (center - K) - v + cn)
        pos[i] = cp
        neg[i] = cn

    beyond = (pos > H) | (neg > H)
    signals = tuple(
        Signal(
            rule="beyond_limits",
            chart="cusum",
            points=(int(i),),
            note="cumulative sum beyond the decision interval",
        )
        for i in np.flatnonzero(beyond)
    )

    table = pd.DataFrame(
        {
            "value": x,
            "cusum_pos": pos,
            "cusum_neg": -neg,  # plotted below zero, as is conventional
            "signal": beyond,
        },
        index=s.index,
    )
    return Result(
        method="cusum",
        params={
            "value": value,
            "k": k,
            "h": h,
            "rules": "decision interval only (CUSUM values are autocorrelated)",
            "limits": "fitted" if fitted else "specified",
        },
        stats={
            "center": float(center),
            "sigma": float(sigma),
            "k": k,
            "h": h,
            "cusum_limit": H,
        },
        signals=signals,
        meta={
            "n": n,
            "version": __version__,
            "input": data_hash(x),
            "computed_at": utcnow(),
            "source": "fitted (Phase I)" if fitted else "specified parameters (Phase II)",
        },
        baseline=Baseline(
            "cusum", {"center": float(center), "sigma": float(sigma)},
            n, utcnow(), __version__,
        ),
        _table=table,
    )
