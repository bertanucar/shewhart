"""shewhart — statistical process control for Python.

Validated, pandas-native, automation-first SPC.

    import shewhart as sw

    r = sw.imr(df, value="torque", rules="nelson")
    r.ok          # True iff in control — the cron exit-code primitive
    r.summary()   # plain-language verdict
    r.plot()

    # fit once, freeze, monitor forever:
    sw.imr(df_hist, value="torque").baseline.save("line3_baseline.json")
    r = sw.imr(df_new, value="torque", limits="line3_baseline.json")
"""

from . import _constants as constants
from ._registry import available, chart
from ._result import Baseline, Result, Signal
from ._version import __version__
from .charts import imr, xbar_r, xbar_s

__all__ = [
    "imr",
    "xbar_r",
    "xbar_s",
    "chart",
    "available",
    "Result",
    "Signal",
    "Baseline",
    "constants",
    "imr_limits",
    "beyond_limits",
    "__version__",
]


# -- v0.0.1 compatibility — kept forever (string aliases never die) ----------


def imr_limits(x) -> dict:
    """I-MR control limits as a plain dict (v0.0.1 API, kept forever).

    Prefer ``sw.imr(x)`` which returns the full Result. Constants are now
    computed exactly (d2 = 2/sqrt(pi), D4 = 1 + 3*d3/d2) rather than the
    3-decimal table values used in v0.0.1.
    """
    r = imr(x, rules="none")
    out = {k: float(v) for k, v in r.stats.items()}
    out["n"] = int(r.meta["n"])
    return out


def beyond_limits(x, limits: dict) -> list[bool]:
    """Nelson rule 1 against given individuals limits (v0.0.1 API, kept forever)."""
    import numpy as np

    arr = np.asarray(x, dtype="float64")
    return [bool(v < limits["i_lcl"] or v > limits["i_ucl"]) for v in arr]
