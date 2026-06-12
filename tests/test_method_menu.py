"""Sigma-estimator menu: named methods with computed unbiasing constants."""

import math

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

import shewhart as sw
from shewhart import constants as c


def test_d4_closed_form_and_guard():
    assert c.d4(2) == pytest.approx(math.sqrt(2) * norm.ppf(0.75), rel=1e-12)
    assert c.d4(2) == pytest.approx(0.954, abs=1e-3)  # published table value
    with pytest.raises(ValueError, match="n=2 only"):
        c.d4(3)


def test_b5_b6_match_published_tables():
    assert c.B5(5) == 0.0
    assert c.B6(5) == pytest.approx(1.964, abs=1e-3)
    assert c.B5(10) == pytest.approx(0.276, abs=1e-3)
    assert c.B6(10) == pytest.approx(1.669, abs=1e-3)


def test_imr_median_mr_differs_when_mr_is_skewed():
    x = [10.0, 12.0, 11.0, 12.0, 11.0]  # MRs [2,1,1,1]: mean 1.25, median 1
    avg = sw.imr(x, rules="none")
    med = sw.imr(x, rules="none", method="median_mr")
    assert avg.stats["sigma_within"] == pytest.approx(1.25 / c.d2(2))
    assert med.stats["sigma_within"] == pytest.approx(1.0 / c.d4(2))
    assert med.params["method"] == "median_mr"


def test_imr_unknown_method_teaches():
    with pytest.raises(ValueError, match="average_mr"):
        sw.imr([1.0, 2.0, 3.0], method="rbar")


def make_df(groups):
    rows = []
    for i, g in enumerate(groups):
        rows += [{"x": v, "g": f"b{i}"} for v in g]
    return pd.DataFrame(rows)


CLEAN = [[10, 12], [11, 13], [9, 11], [12, 14], [10, 12]]


def test_xbar_s_pooled_sigma_and_limits():
    r = sw.xbar_s(make_df(CLEAN), value="x", subgroup="g",
                  rules="none", method="pooled")
    df = 5 * (2 - 1)
    pooled_sd = math.sqrt(2.0)  # every pair has variance 2
    sigma = pooled_sd / c.c4(df + 1)
    assert r.stats["sigma_within"] == pytest.approx(sigma)
    # with the pooled estimator the S-chart limits equal B5/B6 * sigma
    assert r.stats["s_ucl"] == pytest.approx(c.B6(2) * sigma)
    assert r.stats["s_lcl"] == pytest.approx(c.B5(2) * sigma)
    assert r.params["method"] == "pooled"


def test_xbar_s_default_is_unchanged_sbar():
    r = sw.xbar_s(make_df(CLEAN), value="x", subgroup="g", rules="none")
    sbar = math.sqrt(2.0)
    assert r.stats["sigma_within"] == pytest.approx(sbar / c.c4(2))
    assert r.params["method"] == "sbar"


def test_xbar_r_rejects_pooled_with_pointer():
    with pytest.raises(ValueError, match='xbar_s\\(method="pooled"\\)'):
        sw.xbar_r(make_df(CLEAN), value="x", subgroup="g", method="pooled")
