import math

import numpy as np
import pytest
from scipy import stats as sps

import shewhart as sw
from shewhart.tolerance import howe_k2, wilks_confidence

X = [10.2, 10.4, 10.1, 10.5, 10.3, 10.2, 10.6, 10.3, 10.4, 10.2]


def test_howe_k2_follows_documented_formula():
    n, p, g = 10, 0.95, 0.95
    z = sps.norm.ppf((1 + p) / 2)
    chi2 = sps.chi2.ppf(1 - g, n - 1)
    assert howe_k2(n, p, g) == pytest.approx(z * math.sqrt((n - 1) * (1 + 1 / n) / chi2))


def test_k2_reproduces_nist_handbook_value():
    # NIST/SEMATECH e-Handbook 7.2.6.3: n=43, p=0.90, gamma=0.99 -> k2 = 2.217
    assert howe_k2(43, 0.90, 0.99) == pytest.approx(2.217, abs=5e-4)


def test_k2_shrinks_with_n_and_grows_with_coverage():
    assert howe_k2(50, 0.95, 0.95) < howe_k2(10, 0.95, 0.95)
    assert howe_k2(10, 0.99, 0.95) > howe_k2(10, 0.95, 0.95)


def test_normal_interval():
    r = sw.tolerance_interval(X, coverage=0.95, confidence=0.95)
    mean, sd = np.mean(X), np.std(X, ddof=1)
    k2 = howe_k2(len(X), 0.95, 0.95)
    assert r.stats["lower"] == pytest.approx(mean - k2 * sd)
    assert r.stats["upper"] == pytest.approx(mean + k2 * sd)
    assert r.ok
    assert "Howe" in r.meta["source"]


def test_wilks_confidence_formula_and_monotonicity():
    # closed form for n=10, p=0.9: 1 - 0.9^10 - 10*0.1*0.9^9
    assert wilks_confidence(10, 0.9) == pytest.approx(
        1 - 0.9**10 - 10 * 0.1 * 0.9**9
    )
    assert wilks_confidence(100, 0.9) > wilks_confidence(10, 0.9)


def test_nonparametric_needs_enough_data():
    with pytest.raises(ValueError, match="requires n >="):
        sw.tolerance_interval(X, coverage=0.95, confidence=0.95,
                              method="nonparametric")


def test_nonparametric_interval_with_enough_data():
    rng = np.random.default_rng(2)
    x = rng.normal(50, 2, 100)
    r = sw.tolerance_interval(x, coverage=0.90, confidence=0.95,
                              method="nonparametric")
    assert r.stats["lower"] == pytest.approx(x.min())
    assert r.stats["upper"] == pytest.approx(x.max())
    assert r.stats["achieved_confidence"] >= 0.95


def test_parameter_validation_teaches():
    with pytest.raises(ValueError, match="coverage must be in"):
        sw.tolerance_interval(X, coverage=1.5)
    with pytest.raises(ValueError, match="'normal' or 'nonparametric'"):
        sw.tolerance_interval(X, method="exact")


def test_monte_carlo_coverage_sanity():
    # the (0.9, 0.9) normal interval should cover >= 90% of the population
    # in at least ~90% of repeated samples; generous margins keep this stable
    rng = np.random.default_rng(42)
    hits = 0
    for _ in range(300):
        sample = rng.normal(0, 1, 30)
        r = sw.tolerance_interval(sample, coverage=0.9, confidence=0.9)
        covered = sps.norm.cdf(r.stats["upper"]) - sps.norm.cdf(r.stats["lower"])
        hits += covered >= 0.9
    assert hits / 300 > 0.85
