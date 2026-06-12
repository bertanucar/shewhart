import math

import numpy as np
import pandas as pd
import pytest

import shewhart as sw
from shewhart import constants as c


def test_laney_p_hand_computed():
    df = pd.DataFrame({"d": [2, 3, 1, 4, 2], "n": [50] * 5})
    r = sw.laney_p(df, defectives="d", size="n", rules="none")
    # z = (p - 0.048)/sigma_i; sigma_z = mean|dz| / d2(2)
    p = np.array([2, 3, 1, 4, 2]) / 50
    sig = math.sqrt(0.048 * 0.952 / 50)
    z = (p - 0.048) / sig
    sigma_z = np.abs(np.diff(z)).mean() / c.d2(2)
    assert r.stats["p_center"] == pytest.approx(0.048)
    assert r.stats["sigma_z"] == pytest.approx(sigma_z)
    assert r.stats["p_ucl"] == pytest.approx(0.048 + 3 * sig * sigma_z)
    assert r.stats["p_lcl"] == 0.0
    assert r.ok


def test_laney_widens_limits_when_overdispersed():
    # huge subgroups with between-period variation: classic p chart panics,
    # Laney does not
    rng = np.random.default_rng(11)
    true_p = rng.normal(0.05, 0.01, 20).clip(0.02, 0.08)
    n = 10_000
    d = rng.binomial(n, true_p)
    df = pd.DataFrame({"d": d, "n": [n] * 20})

    classic = sw.p_chart(df, defectives="d", size="n", rules="none")
    laney = sw.laney_p(df, defectives="d", size="n", rules="none")

    assert not classic.ok            # overdispersion: false alarms everywhere
    assert laney.stats["sigma_z"] > 2
    assert laney.table["ucl"].iloc[0] > classic.table["ucl"].iloc[0]
    assert laney.ok                  # Laney absorbs the between-period variation


def test_sigma_z_near_one_for_binomial_data():
    rng = np.random.default_rng(5)
    d = rng.binomial(500, 0.05, 30)
    df = pd.DataFrame({"d": d, "n": [500] * 30})
    r = sw.laney_p(df, defectives="d", size="n", rules="none")
    assert 0.5 < r.stats["sigma_z"] < 1.6  # no overdispersion: sigma_z ~ 1


def test_laney_u_runs_and_freezes(tmp_path):
    df = pd.DataFrame({"flaws": [6, 4, 9, 5, 7], "units": [3, 2, 4, 2, 3]})
    r = sw.laney_u(df, defects="flaws", size="units", rules="none")
    assert r.stats["u_center"] == pytest.approx(31 / 14)
    path = tmp_path / "laney_u.json"
    r.baseline.save(path)
    r2 = sw.laney_u(df, defects="flaws", size="units", limits=str(path))
    assert "Phase II" in r2.meta["source"]
    assert r2.stats["sigma_z"] == pytest.approx(r.stats["sigma_z"])


def test_no_variation_teaches():
    df = pd.DataFrame({"d": [2, 2, 2, 2], "n": [50] * 4})
    with pytest.raises(ValueError, match="sigma_z"):
        sw.laney_p(df, defectives="d", size="n")


def test_plot_smoke():
    import matplotlib

    matplotlib.use("Agg")
    df = pd.DataFrame({"d": [2, 3, 1, 4, 2], "n": [50] * 5})
    ax = sw.laney_p(df, defectives="d", size="n").plot()
    assert "Laney" in ax.get_title()
