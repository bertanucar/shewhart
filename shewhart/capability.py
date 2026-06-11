"""Process capability analysis with confidence intervals.

Indices and intervals follow Montgomery (8th ed., ch. 8):

* Cp/Cpk use the within-process sigma (moving range / d2 for individuals,
  pooled standard deviation for subgrouped data); Pp/Ppk use the overall
  sample standard deviation.
* The Cp/Pp interval is exact, based on the chi-square distribution of the
  variance estimate. The Cpk/Ppk interval is the standard approximation
  (Bissell 1990; Montgomery eq. 8.19).
* For the moving-range estimate the effective degrees of freedom are
  0.62*(n-1), the usual approximation for the MR(2) estimator. Pooled
  estimates use their exact degrees of freedom, sum(n_i - 1).

``Result.ok`` means the data passed the stability gate (no observations
beyond 3 sigma of the mean). Capability numbers from an unstable process
are not meaningful; the gate makes that visible instead of silent.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from ._constants import d2
from ._data import as_series
from ._registry import register
from ._result import Result, Signal, data_hash, utcnow
from ._version import __version__


def _pooled(data: pd.DataFrame, value: str, subgroup: str):
    frame = data[[value, subgroup]].dropna()
    groups = [
        g.to_numpy("float64")
        for _, g in frame.groupby(subgroup, sort=False)[value]
        if len(g) >= 2
    ]
    if len(groups) < 2:
        raise ValueError(
            "capability() with subgroup= needs at least 2 subgroups of size >= 2. "
            "For individual values, omit subgroup=."
        )
    df = sum(len(g) - 1 for g in groups)
    pooled_var = sum((len(g) - 1) * np.var(g, ddof=1) for g in groups) / df
    return math.sqrt(pooled_var), float(df)


def _cp_interval(cp: float, df: float, confidence: float) -> tuple[float, float]:
    a = (1.0 - confidence) / 2.0
    return (
        cp * math.sqrt(sps.chi2.ppf(a, df) / df),
        cp * math.sqrt(sps.chi2.ppf(1.0 - a, df) / df),
    )


def _cpk_interval(cpk: float, n: int, df: float, confidence: float):
    if cpk <= 0:
        return None
    z = sps.norm.ppf(1.0 - (1.0 - confidence) / 2.0)
    half = z * math.sqrt(1.0 / (9.0 * n * cpk**2) + 1.0 / (2.0 * df))
    return cpk * (1.0 - half), cpk * (1.0 + half)


def _tail_ppm(mean: float, sigma: float, lsl, usl) -> float:
    ppm = 0.0
    if lsl is not None:
        ppm += sps.norm.cdf((lsl - mean) / sigma)
    if usl is not None:
        ppm += 1.0 - sps.norm.cdf((usl - mean) / sigma)
    return ppm * 1e6


@register("capability")
def capability(
    data: Any,
    *,
    value: str | None = None,
    lsl: float | None = None,
    usl: float | None = None,
    target: float | None = None,
    subgroup: str | None = None,
    confidence: float = 0.95,
) -> Result:
    """Process capability study (Cp/Cpk, Pp/Ppk) with confidence intervals.

        r = sw.capability(df, value="dia", lsl=9.95, usl=10.05)
        r.stats["cpk"], r.stats["cpk_lci"], r.stats["cpk_uci"]
    """
    if lsl is None and usl is None:
        raise ValueError(
            "capability() needs at least one specification limit. "
            'Example: sw.capability(df, value="dia", lsl=9.95, usl=10.05)'
        )
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError(f"lsl must be below usl, got lsl={lsl}, usl={usl}.")
    if not 0.5 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0.5, 1), got {confidence}.")

    if subgroup is not None:
        if not isinstance(data, pd.DataFrame):
            raise ValueError(
                "capability() with subgroup= needs a DataFrame. "
                'Example: sw.capability(df, value="dia", subgroup="batch", lsl=..., usl=...)'
            )
        s = as_series(data, value, "capability")
        sigma_within, df_within = _pooled(data, value, subgroup)
        within_how = "pooled std dev over subgroups"
    else:
        s = as_series(data, value, "capability")
        if len(s) < 3:
            raise ValueError(f"capability() needs at least 3 observations, got {len(s)}.")
        mr = s.diff().abs().dropna()
        sigma_within = float(mr.mean()) / d2(2)
        df_within = 0.62 * (len(s) - 1)
        within_how = "average moving range / d2(2)"

    x = s.to_numpy()
    n = len(x)
    mean = float(x.mean())
    sigma_overall = float(x.std(ddof=1))
    df_overall = float(n - 1)
    if sigma_within <= 0 or sigma_overall <= 0:
        raise ValueError(
            "capability(): the data has no variation; capability indices are "
            "undefined. Check that the measurement resolution is adequate."
        )

    stats: dict[str, float] = {
        "mean": mean,
        "sigma_within": sigma_within,
        "sigma_overall": sigma_overall,
    }

    cpu = (usl - mean) / (3.0 * sigma_within) if usl is not None else None
    cpl = (mean - lsl) / (3.0 * sigma_within) if lsl is not None else None
    if cpu is not None:
        stats["cpu"] = cpu
    if cpl is not None:
        stats["cpl"] = cpl

    def both(fn_within: float | None, fn_overall: float | None, name_w: str, name_o: str):
        if fn_within is not None:
            stats[name_w] = fn_within
        if fn_overall is not None:
            stats[name_o] = fn_overall

    if lsl is not None and usl is not None:
        span = usl - lsl
        cp = span / (6.0 * sigma_within)
        pp = span / (6.0 * sigma_overall)
        stats["cp"], stats["pp"] = cp, pp
        stats["cp_lci"], stats["cp_uci"] = _cp_interval(cp, df_within, confidence)
        stats["pp_lci"], stats["pp_uci"] = _cp_interval(pp, df_overall, confidence)
        if target is not None:
            msd = float(np.sum((x - target) ** 2) / (n - 1))
            stats["cpm"] = span / (6.0 * math.sqrt(msd))

    cpk = min(v for v in (cpu, cpl) if v is not None)
    ppk_parts = [
        (usl - mean) / (3.0 * sigma_overall) if usl is not None else None,
        (mean - lsl) / (3.0 * sigma_overall) if lsl is not None else None,
    ]
    ppk = min(v for v in ppk_parts if v is not None)
    stats["cpk"], stats["ppk"] = cpk, ppk

    ci = _cpk_interval(cpk, n, df_within, confidence)
    if ci:
        stats["cpk_lci"], stats["cpk_uci"] = ci
    ci = _cpk_interval(ppk, n, df_overall, confidence)
    if ci:
        stats["ppk_lci"], stats["ppk_uci"] = ci

    out_of_spec = np.zeros(n, dtype=bool)
    if lsl is not None:
        out_of_spec |= x < lsl
    if usl is not None:
        out_of_spec |= x > usl
    stats["ppm_observed"] = float(out_of_spec.mean() * 1e6)
    stats["ppm_within"] = _tail_ppm(mean, sigma_within, lsl, usl)
    stats["ppm_overall"] = _tail_ppm(mean, sigma_overall, lsl, usl)

    # Stability gate: capability assumes a stable process.
    unstable = np.flatnonzero(np.abs(x - mean) > 3.0 * sigma_within)
    signals = (
        (
            Signal(
                rule="unstable",
                chart="stability",
                points=tuple(int(i) for i in unstable),
                note="observations beyond 3 sigma; capability of an unstable "
                "process is not meaningful",
            ),
        )
        if len(unstable)
        else ()
    )

    ad = sps.anderson(x, dist="norm")
    crit_5 = float(ad.critical_values[list(ad.significance_level).index(5.0)])
    normality = (
        f"Anderson-Darling = {ad.statistic:.3f}, "
        + ("rejected" if ad.statistic > crit_5 else "not rejected")
        + " at 5%"
    )

    table = pd.DataFrame({"value": x, "in_spec": ~out_of_spec}, index=s.index)
    return Result(
        method="capability",
        params={
            "value": value,
            "lsl": lsl,
            "usl": usl,
            "target": target,
            "subgroup": subgroup,
            "confidence": confidence,
            "rules": None,
        },
        stats=stats,
        signals=signals,
        meta={
            "n": n,
            "version": __version__,
            "input": data_hash(x),
            "computed_at": utcnow(),
            "source": f"within sigma: {within_how}",
            "df_within": df_within,
            "df_overall": df_overall,
            "normality": normality,
        },
        baseline=None,
        _table=table,
    )
