"""EWMA control chart.

z_t = lam * x_t + (1 - lam) * z_{t-1}, started at the center line, with
limits center +/- k * sigma * sqrt(lam/(2-lam) * (1 - (1-lam)^(2t))).
``asymptotic=True`` uses the steady-state factor sqrt(lam/(2-lam)) instead,
as in the NIST/SEMATECH e-Handbook example (section 6.3.2.4).

Run rules are deliberately not offered: EWMA values are autocorrelated by
construction, so zone and run tests are invalid on them. The chart signals
on limit violations only.
"""

from __future__ import annotations

import math
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
        if limits.chart != "ewma":
            raise ValueError(
                f"This baseline was fitted for {limits.chart!r}, not 'ewma'."
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


@register("ewma")
def ewma(
    data: Any,
    *,
    value: str | None = None,
    lam: float = 0.2,
    k: float = 3.0,
    center: float | None = None,
    sigma: float | None = None,
    asymptotic: bool = False,
    limits: Any = None,
) -> Result:
    """EWMA chart for detecting small sustained shifts.

        r = sw.ewma(df, value="torque", lam=0.2)

    Phase II against known parameters (or a saved baseline):

        r = sw.ewma(df_new, value="torque", center=50.0, sigma=2.05, lam=0.3)
    """
    if not 0.0 < lam <= 1.0:
        raise ValueError(
            f"lam must be in (0, 1], got {lam}. Common choices: 0.1 to 0.3 "
            "(smaller lam reacts to smaller shifts)."
        )
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}.")

    s = as_series(data, value, "ewma")
    x = s.to_numpy()
    n = len(x)

    if limits is not None:
        center, sigma = _resolve(limits)
    fitted = center is None or sigma is None
    if center is None or sigma is None:
        if n < 2:
            raise ValueError(
                f"ewma() needs at least 2 observations to estimate parameters, "
                f"got {n}. Alternatively pass center= and sigma= explicitly."
            )
        if center is None:
            center = float(x.mean())
        if sigma is None:
            sigma = float(np.abs(np.diff(x)).mean()) / d2(2)
    if sigma <= 0:
        raise ValueError("ewma(): sigma must be positive; the data has no variation.")

    z = np.empty(n)
    prev = center
    for i, v in enumerate(x):
        prev = lam * v + (1.0 - lam) * prev
        z[i] = prev

    base = lam / (2.0 - lam)
    if asymptotic:
        factor = np.full(n, math.sqrt(base))
    else:
        t = np.arange(1, n + 1)
        factor = np.sqrt(base * (1.0 - (1.0 - lam) ** (2 * t)))
    ucl = center + k * sigma * factor
    lcl = center - k * sigma * factor

    beyond = (z > ucl) | (z < lcl)
    signals = tuple(
        Signal(rule="beyond_limits", chart="ewma", points=(int(i),),
               note="EWMA beyond control limits")
        for i in np.flatnonzero(beyond)
    )

    stats = {"center": float(center), "sigma": float(sigma), "lam": lam, "k": k}
    if asymptotic:
        stats["ewma_lcl"], stats["ewma_ucl"] = float(lcl[0]), float(ucl[0])

    table = pd.DataFrame(
        {"value": x, "ewma": z, "lcl": lcl, "ucl": ucl,
         "signal": beyond},
        index=s.index,
    )
    return Result(
        method="ewma",
        params={"value": value, "lam": lam, "k": k, "asymptotic": asymptotic,
                "rules": "limits only (EWMA values are autocorrelated)",
                "limits": "fitted" if fitted else "specified"},
        stats=stats,
        signals=signals,
        meta={
            "n": n,
            "version": __version__,
            "input": data_hash(x),
            "computed_at": utcnow(),
            "source": "fitted (Phase I)" if fitted else "specified parameters (Phase II)",
        },
        baseline=Baseline("ewma", {"center": float(center), "sigma": float(sigma)},
                          n, utcnow(), __version__),
        _table=table,
    )
