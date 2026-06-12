import math

import numpy as np
import pytest
from scipy import stats as sps

import shewhart as sw

MU, SIG = 1.0, 0.5  # lognormal log-scale parameters


def lognormal_sample(n=4000, seed=8):
    return np.random.default_rng(seed).lognormal(MU, SIG, n)


def test_lognormal_percentile_indices_approach_analytic_truth():
    x = lognormal_sample()
    lsl, usl = 0.5, 15.0
    r = sw.capability(x, lsl=lsl, usl=usl, dist="lognormal")

    z = sps.norm.ppf(0.99865)
    q_lo, q_med, q_hi = math.exp(MU - z * SIG), math.exp(MU), math.exp(MU + z * SIG)
    ppk_true = min((usl - q_med) / (q_hi - q_med), (q_med - lsl) / (q_med - q_lo))

    assert r.stats["q_median"] == pytest.approx(q_med, rel=0.05)
    assert r.stats["ppk"] == pytest.approx(ppk_true, rel=0.08)
    assert "pp" in r.stats
    assert "cpk" not in r.stats  # within-sigma indices do not apply here
    assert "ppk_lci" not in r.stats  # no normal-theory intervals either


def test_auto_selects_lognormal_for_lognormal_data():
    r = sw.capability(lognormal_sample(), lsl=0.5, usl=20.0, dist="auto")
    assert r.meta["dist_selected"] == "lognormal"
    assert set(r.meta["dist_fit_ad"]) >= {"lognormal", "weibull", "gamma", "normal"}


def test_boxcox_transforms_data_and_specs_together():
    x = lognormal_sample(seed=9)
    r = sw.capability(x, lsl=0.5, usl=15.0, transform="boxcox")
    # for lognormal data the MLE lambda is near 0 (log transform)
    assert abs(r.stats["boxcox_lambda"]) < 0.15
    assert "cpk" in r.stats and "cpk_lci" in r.stats  # normal machinery applies
    assert r.params["transform"] == "boxcox"


def test_dist_and_transform_are_mutually_exclusive():
    with pytest.raises(ValueError, match="not both"):
        sw.capability(lognormal_sample(), lsl=0.5, usl=15.0,
                      dist="weibull", transform="boxcox")


def test_positive_data_required():
    with pytest.raises(ValueError, match="strictly positive"):
        sw.capability([-1.0, 2.0, 3.0] * 5, lsl=0.1, usl=9.0, dist="weibull")
    with pytest.raises(ValueError, match="strictly positive"):
        sw.capability([1.0, 2.0, 3.0] * 5, lsl=-1.0, usl=9.0, transform="boxcox")


def test_subgroup_with_percentile_method_teaches():
    import pandas as pd

    df = pd.DataFrame({"x": lognormal_sample(60), "g": list("abc") * 20})
    with pytest.raises(ValueError, match="overall performance"):
        sw.capability(df, value="x", subgroup="g", lsl=0.5, usl=15.0,
                      dist="lognormal")


def test_one_sided_percentile_method():
    r = sw.capability(lognormal_sample(), usl=15.0, dist="lognormal")
    assert "ppk" in r.stats and "pp" not in r.stats


def test_small_sample_teaches():
    with pytest.raises(ValueError, match="at least 10"):
        sw.capability([1.0, 2.0, 3.0], lsl=0.1, usl=9.0, dist="lognormal")


def test_default_normal_path_unchanged():
    x = [10.0, 12.0, 11.0, 13.0, 12.0]
    r = sw.capability(x, lsl=6, usl=16)
    assert r.params["dist"] == "normal" and r.params["transform"] is None
    assert r.stats["cpk"] == pytest.approx(4.4 / (3 * r.stats["sigma_within"]))