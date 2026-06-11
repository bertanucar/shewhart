"""Run chart with the four standard runs tests.

Tests follow the classic normal approximations (as used in Minitab's run
chart): runs about the median detect clustering (too few runs) and mixtures
(too many); runs up/down detect trends (too few) and oscillation (too many).
Points equal to the median and zero differences are excluded, as usual.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from .._data import as_series
from .._registry import register
from .._result import Result, Signal, data_hash, utcnow
from .._version import __version__


def _count_runs(signs: np.ndarray) -> int:
    return int(1 + np.sum(signs[1:] != signs[:-1])) if len(signs) else 0


@register("run_chart")
def run_chart(data: Any, *, value: str | None = None, alpha: float = 0.05) -> Result:
    """Run chart: values against the median, with the four runs tests.

        r = sw.run_chart(df, value="torque")
    """
    s = as_series(data, value, "run_chart")
    if len(s) < 4:
        raise ValueError(f"run_chart() needs at least 4 observations, got {len(s)}.")
    if not 0.0 < alpha < 0.5:
        raise ValueError(f"alpha must be in (0, 0.5), got {alpha}.")

    x = s.to_numpy()
    median = float(np.median(x))
    stats: dict[str, float] = {"median": median}
    signals: list[Signal] = []

    # Runs about the median (ties excluded).
    sides = np.sign(x - median)
    sides = sides[sides != 0]
    m = int(np.sum(sides > 0))
    k = int(np.sum(sides < 0))
    if m > 0 and k > 0:
        runs = _count_runs(sides)
        expected = 2.0 * m * k / (m + k) + 1.0
        var = 2.0 * m * k * (2.0 * m * k - m - k) / ((m + k) ** 2 * (m + k - 1))
        stats["runs_about_median"] = float(runs)
        stats["runs_expected"] = expected
        if var > 0:
            z = (runs - expected) / math.sqrt(var)
            stats["p_clustering"] = float(sps.norm.cdf(z))
            stats["p_mixtures"] = float(sps.norm.sf(z))
            if stats["p_clustering"] < alpha:
                signals.append(Signal("clustering", "run", (),
                                      f"too few runs about the median (p = {stats['p_clustering']:.4f})"))
            if stats["p_mixtures"] < alpha:
                signals.append(Signal("mixtures", "run", (),
                                      f"too many runs about the median (p = {stats['p_mixtures']:.4f})"))

    # Runs up and down (zero differences excluded).
    diffs = np.sign(np.diff(x))
    diffs = diffs[diffs != 0]
    if len(diffs) >= 2:
        nn = len(diffs) + 1
        runs_ud = _count_runs(diffs)
        expected_ud = (2.0 * nn - 1.0) / 3.0
        var_ud = (16.0 * nn - 29.0) / 90.0
        stats["runs_up_down"] = float(runs_ud)
        stats["runs_ud_expected"] = expected_ud
        z = (runs_ud - expected_ud) / math.sqrt(var_ud)
        stats["p_trends"] = float(sps.norm.cdf(z))
        stats["p_oscillation"] = float(sps.norm.sf(z))
        if stats["p_trends"] < alpha:
            signals.append(Signal("trends", "run", (),
                                  f"too few runs up/down (p = {stats['p_trends']:.4f})"))
        if stats["p_oscillation"] < alpha:
            signals.append(Signal("oscillation", "run", (),
                                  f"too many runs up/down (p = {stats['p_oscillation']:.4f})"))

    # Runs tests judge the sequence as a whole; no single point is "the" signal.
    table = pd.DataFrame(
        {"value": x, "above_median": x > median, "signal": False}, index=s.index
    )
    return Result(
        method="run_chart",
        params={"value": value, "alpha": alpha, "rules": "runs tests"},
        stats=stats,
        signals=tuple(signals),
        meta={
            "n": len(x),
            "version": __version__,
            "input": data_hash(x),
            "computed_at": utcnow(),
            "source": "runs tests vs median",
        },
        baseline=None,
        _table=table,
    )
