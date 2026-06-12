"""Tolerance intervals: bounds that cover a proportion of the population.

A (p, gamma) tolerance interval covers at least proportion p of the
population with confidence gamma. This is a statement about individual
values, which is why tolerance intervals, not confidence intervals on the
mean, are what specification work in pharma and medical devices calls for.

Normal method: two-sided factor k2 via the Howe (1969) approximation,

    k2 = z_{(1+p)/2} * sqrt( nu * (1 + 1/n) / chi2_{alpha, nu} )

with nu = n - 1 and chi2_{alpha, nu} the lower alpha = 1 - gamma quantile.
This is the approximation used by the NIST/SEMATECH e-Handbook (7.2.6.3)
and by the major commercial packages.

Nonparametric method: the interval (min, max) per Wilks. Its achieved
confidence for covering proportion p is

    gamma_achieved = 1 - p^n - n * (1 - p) * p^(n-1)

which depends only on n, so small samples cannot reach high confidence;
the error message then states the minimum n required.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from ._data import as_series
from ._registry import register
from ._result import Result, data_hash, utcnow
from ._version import __version__


def howe_k2(n: int, coverage: float, confidence: float) -> float:
    """Two-sided normal tolerance factor (Howe approximation)."""
    nu = n - 1
    z = sps.norm.ppf((1.0 + coverage) / 2.0)
    chi2 = sps.chi2.ppf(1.0 - confidence, nu)
    return z * math.sqrt(nu * (1.0 + 1.0 / n) / chi2)


def wilks_confidence(n: int, coverage: float) -> float:
    """Achieved confidence of (min, max) covering proportion ``coverage``."""
    p = coverage
    return 1.0 - p**n - n * (1.0 - p) * p ** (n - 1)


def _wilks_minimum_n(coverage: float, confidence: float) -> int:
    n = 2
    while wilks_confidence(n, coverage) < confidence:
        n += 1
        if n > 100_000:  # pragma: no cover - unreachable for sane inputs
            break
    return n


@register("tolerance_interval")
def tolerance_interval(
    data: Any,
    *,
    value: str | None = None,
    coverage: float = 0.95,
    confidence: float = 0.95,
    method: str = "normal",
) -> Result:
    """Two-sided (coverage, confidence) tolerance interval.

        r = sw.tolerance_interval(df, value="potency", coverage=0.99)
        r.stats["lower"], r.stats["upper"]

    method="nonparametric" uses (min, max) and reports the achieved
    confidence, which is set by n alone.
    """
    for name, v in (("coverage", coverage), ("confidence", confidence)):
        if not 0.0 < v < 1.0:
            raise ValueError(f"{name} must be in (0, 1), got {v}.")
    if method not in ("normal", "nonparametric"):
        raise ValueError(
            f"method must be 'normal' or 'nonparametric', got {method!r}. "
            'Example: sw.tolerance_interval(x, coverage=0.99, method="normal")'
        )

    s = as_series(data, value, "tolerance_interval")
    x = s.to_numpy()
    n = len(x)
    if n < 2:
        raise ValueError(f"tolerance_interval() needs at least 2 observations, got {n}.")

    stats: dict[str, float] = {"coverage": coverage, "confidence": confidence}

    if method == "normal":
        mean = float(x.mean())
        sd = float(x.std(ddof=1))
        if sd == 0:
            raise ValueError(
                "tolerance_interval(): the data has no variation; the interval "
                "is degenerate. Check the measurement resolution."
            )
        k2 = howe_k2(n, coverage, confidence)
        stats.update(
            mean=mean,
            sd=sd,
            k2=k2,
            lower=mean - k2 * sd,
            upper=mean + k2 * sd,
        )
        source = "normal method (Howe k2)"
    else:
        achieved = wilks_confidence(n, coverage)
        if achieved < confidence:
            need = _wilks_minimum_n(coverage, confidence)
            raise ValueError(
                f"With n={n} the nonparametric (min, max) interval reaches only "
                f"{achieved:.1%} confidence for {coverage:.0%} coverage; "
                f"{confidence:.0%} requires n >= {need}. Collect more data or "
                'use method="normal" if normality is defensible.'
            )
        stats.update(
            lower=float(x.min()),
            upper=float(x.max()),
            achieved_confidence=achieved,
        )
        source = "nonparametric method (Wilks, min/max)"

    inside = (x >= stats["lower"]) & (x <= stats["upper"])
    table = pd.DataFrame({"value": x, "inside": inside}, index=s.index)

    return Result(
        method="tolerance_interval",
        params={
            "value": value,
            "coverage": coverage,
            "confidence": confidence,
            "method": method,
            "rules": None,
        },
        stats=stats,
        signals=(),
        meta={
            "n": n,
            "version": __version__,
            "input": data_hash(x),
            "computed_at": utcnow(),
            "source": source,
        },
        baseline=None,
        _table=table,
    )
