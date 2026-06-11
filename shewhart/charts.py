"""Control chart primitives.

Constants and formulas follow Montgomery, "Introduction to Statistical
Quality Control" (8th ed.), chapter 6.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Control chart constants for a moving range of span n=2
D2_MR2 = 1.128  # E[MR]/sigma for normal data, n=2
D4_MR2 = 3.267  # upper control limit factor for the MR chart, n=2


def imr_limits(x) -> dict:
    """Individuals & Moving Range (I-MR) control limits from a Phase I sample.

    Parameters
    ----------
    x : array-like of float
        Individual measurements in time order. NaNs are dropped.

    Returns
    -------
    dict with keys:
        i_center, i_lcl, i_ucl       — individuals chart center line and 3-sigma limits
        mr_center, mr_lcl, mr_ucl    — moving range chart center line and limits
        sigma_within                 — within-process standard deviation estimate (MRbar/d2)
        n                            — number of observations used
    """
    s = pd.Series(x, dtype="float64").dropna()
    if len(s) < 2:
        raise ValueError("imr_limits needs at least 2 observations, got " f"{len(s)}.")

    mr = s.diff().abs().dropna()
    mr_bar = float(mr.mean())
    sigma_within = mr_bar / D2_MR2
    center = float(s.mean())

    return {
        "i_center": center,
        "i_lcl": center - 3.0 * sigma_within,
        "i_ucl": center + 3.0 * sigma_within,
        "mr_center": mr_bar,
        "mr_lcl": 0.0,
        "mr_ucl": D4_MR2 * mr_bar,
        "sigma_within": sigma_within,
        "n": int(len(s)),
    }


def beyond_limits(x, limits: dict) -> list[bool]:
    """Nelson rule 1: flag points beyond the individuals control limits.

    Parameters
    ----------
    x : array-like of float
        Measurements to check (Phase II), in time order.
    limits : dict
        Output of :func:`imr_limits` (uses ``i_lcl`` and ``i_ucl``).

    Returns
    -------
    list of bool, True where the point is outside [i_lcl, i_ucl].
    """
    arr = np.asarray(x, dtype="float64")
    return [bool(v < limits["i_lcl"] or v > limits["i_ucl"]) for v in arr]
