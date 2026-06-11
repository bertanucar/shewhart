import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps

import shewhart as sw
from shewhart import constants as c

X = [10.0, 12.0, 11.0, 13.0, 12.0]  # mean 11.6, MRbar 1.5


def test_indices_hand_computed():
    r = sw.capability(X, lsl=6, usl=16)
    s_w = 1.5 / c.d2(2)
    s_o = math.sqrt(5.2 / 4)
    assert r.stats["sigma_within"] == pytest.approx(s_w)
    assert r.stats["sigma_overall"] == pytest.approx(s_o)
    assert r.stats["cp"] == pytest.approx(10 / (6 * s_w))
    assert r.stats["cpk"] == pytest.approx(4.4 / (3 * s_w))
    assert r.stats["pp"] == pytest.approx(10 / (6 * s_o))
    assert r.stats["ppk"] == pytest.approx(4.4 / (3 * s_o))
    assert r.ok  # stable


def test_confidence_intervals_follow_documented_formulas():
    r = sw.capability(X, lsl=6, usl=16, confidence=0.95)
    n, cp, cpk = 5, r.stats["cp"], r.stats["cpk"]
    df_w = 0.62 * (n - 1)
    assert r.meta["df_within"] == pytest.approx(df_w)

    assert r.stats["cp_lci"] == pytest.approx(cp * math.sqrt(sps.chi2.ppf(0.025, df_w) / df_w))
    assert r.stats["cp_uci"] == pytest.approx(cp * math.sqrt(sps.chi2.ppf(0.975, df_w) / df_w))

    z = sps.norm.ppf(0.975)
    half = z * math.sqrt(1 / (9 * n * cpk**2) + 1 / (2 * df_w))
    assert r.stats["cpk_lci"] == pytest.approx(cpk * (1 - half))
    assert r.stats["cpk_uci"] == pytest.approx(cpk * (1 + half))
    # the honest message: with n=5 the interval is enormous
    assert r.stats["cpk_uci"] - r.stats["cpk_lci"] > 1.5


def test_one_sided_spec():
    r = sw.capability(X, usl=16)
    assert "cp" not in r.stats and "pp" not in r.stats
    assert r.stats["cpk"] == pytest.approx(r.stats["cpu"])


def test_cpm_with_target():
    r = sw.capability(X, lsl=6, usl=16, target=11.0)
    msd = sum((v - 11.0) ** 2 for v in X) / 4
    assert r.stats["cpm"] == pytest.approx(10 / (6 * math.sqrt(msd)))


def test_ppm_keys():
    r = sw.capability(X, lsl=6, usl=16)
    assert r.stats["ppm_observed"] == 0.0
    assert r.stats["ppm_within"] > r.stats["ppm_overall"]  # s_w > s_o here


def test_subgrouped_pooled_sigma():
    rows = []
    for i, g in enumerate([[10, 12], [11, 13], [9, 11], [12, 14], [10, 12]]):
        rows += [{"x": v, "g": f"b{i}"} for v in g]
    r = sw.capability(pd.DataFrame(rows), value="x", subgroup="g", lsl=5, usl=18)
    assert r.stats["sigma_within"] == pytest.approx(math.sqrt(2.0))
    assert r.meta["df_within"] == 5.0


def test_stability_gate_flags_outlier():
    r = sw.capability(X + [25.0], lsl=6, usl=30)
    assert not r.ok
    assert r.signals[0].rule == "unstable"


def test_spec_validation_teaches():
    with pytest.raises(ValueError, match="at least one specification limit"):
        sw.capability(X)
    with pytest.raises(ValueError, match="below usl"):
        sw.capability(X, lsl=16, usl=6)


def test_no_variation_teaches():
    with pytest.raises(ValueError, match="no variation"):
        sw.capability([5.0] * 6, lsl=0, usl=10)


def test_normality_note_present():
    r = sw.capability(X, lsl=6, usl=16)
    assert "Anderson-Darling" in r.meta["normality"]


def test_plot_smoke():
    import matplotlib

    matplotlib.use("Agg")
    ax = sw.capability(X, lsl=6, usl=16, target=11.5).plot()
    assert ax.get_title().startswith("Process capability")
