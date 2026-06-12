"""Control-chart constants, derived from first principles.

Every factor is computed from the underlying order-statistics integrals for
samples drawn from a standard normal distribution. Nothing is copied from a
table; the published tables (Montgomery, "Introduction to Statistical Quality
Control", Appendix VI) serve as *test oracles* in the test suite instead.

    c4(n)   bias-correction constant  E[s] / sigma
    d2(n)   mean of the range of n standard normal observations
    d3(n)   standard deviation of that range
    A2, A3, D3, D4, B3, B4 — the classic chart factors, derived from the above
"""

from __future__ import annotations

import math
from functools import lru_cache

from scipy import integrate
from scipy.stats import norm

# The standard normal carries ~6e-16 of mass beyond +/-8; integrating over
# [-8, 8] is exact to double precision and much faster than (-inf, inf).
_LIM = 8.0


def _check_n(n: int) -> None:
    if not isinstance(n, int) or n < 2:
        raise ValueError(
            f"Subgroup size n must be an integer >= 2, got {n!r}. "
            'Example: from shewhart import constants; constants.d2(5)'
        )


@lru_cache(maxsize=None)
def c4(n: int) -> float:
    """E[s]/sigma for a sample of size n: sqrt(2/(n-1)) * G(n/2) / G((n-1)/2)."""
    _check_n(n)
    return math.sqrt(2.0 / (n - 1)) * math.exp(
        math.lgamma(n / 2.0) - math.lgamma((n - 1) / 2.0)
    )


@lru_cache(maxsize=None)
def d2(n: int) -> float:
    """E[R]/sigma: integral of 1 - F(x)^n - (1-F(x))^n over the real line."""
    _check_n(n)
    value, _ = integrate.quad(
        lambda x: 1.0 - norm.cdf(x) ** n - (1.0 - norm.cdf(x)) ** n, -_LIM, _LIM
    )
    return value


@lru_cache(maxsize=None)
def d3(n: int) -> float:
    """SD(R)/sigma via E[R^2] = 2 * double integral over y < x."""
    _check_n(n)

    def integrand(y: float, x: float) -> float:
        fx, fy = norm.cdf(x), norm.cdf(y)
        return 1.0 - fx**n - (1.0 - fy) ** n + (fx - fy) ** n

    ew2, _ = integrate.dblquad(integrand, -_LIM, _LIM, lambda x: -_LIM, lambda x: x)
    return math.sqrt(2.0 * ew2 - d2(n) ** 2)


@lru_cache(maxsize=None)
def A2(n: int) -> float:
    """Xbar-chart factor for limits from R-bar: 3 / (d2 * sqrt(n))."""
    return 3.0 / (d2(n) * math.sqrt(n))


@lru_cache(maxsize=None)
def A3(n: int) -> float:
    """Xbar-chart factor for limits from S-bar: 3 / (c4 * sqrt(n))."""
    return 3.0 / (c4(n) * math.sqrt(n))


@lru_cache(maxsize=None)
def D3(n: int) -> float:
    """R-chart lower-limit factor: max(0, 1 - 3*d3/d2)."""
    return max(0.0, 1.0 - 3.0 * d3(n) / d2(n))


@lru_cache(maxsize=None)
def D4(n: int) -> float:
    """R-chart upper-limit factor: 1 + 3*d3/d2."""
    return 1.0 + 3.0 * d3(n) / d2(n)


@lru_cache(maxsize=None)
def d4(n: int) -> float:
    """Median of the range of n standard normal observations.

    Used to unbias the *median* moving range: sigma = median(MR) / d4(2).
    Not to be confused with the R-chart limit factor D4 (capital D).
    For n = 2 the closed form is sqrt(2) * z_0.75.
    """
    _check_n(n)
    if n != 2:
        raise ValueError(
            "d4(n) is implemented for n=2 only (median moving-range "
            "estimation uses spans of 2)."
        )
    return math.sqrt(2.0) * norm.ppf(0.75)


@lru_cache(maxsize=None)
def B5(n: int) -> float:
    """S-chart lower-limit factor from a known sigma: max(0, c4 - 3*sqrt(1-c4^2))."""
    return max(0.0, c4(n) - 3.0 * math.sqrt(1.0 - c4(n) ** 2))


@lru_cache(maxsize=None)
def B6(n: int) -> float:
    """S-chart upper-limit factor from a known sigma: c4 + 3*sqrt(1-c4^2)."""
    return c4(n) + 3.0 * math.sqrt(1.0 - c4(n) ** 2)


@lru_cache(maxsize=None)
def B3(n: int) -> float:
    """S-chart lower-limit factor: max(0, 1 - 3*sqrt(1-c4^2)/c4)."""
    return max(0.0, 1.0 - 3.0 * math.sqrt(1.0 - c4(n) ** 2) / c4(n))


@lru_cache(maxsize=None)
def B4(n: int) -> float:
    """S-chart upper-limit factor: 1 + 3*sqrt(1-c4^2)/c4."""
    return 1.0 + 3.0 * math.sqrt(1.0 - c4(n) ** 2) / c4(n)
