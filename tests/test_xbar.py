import numpy as np
import pandas as pd
import pytest

import shewhart as sw
from shewhart import constants as c


def make_df(groups):
    rows = []
    for i, g in enumerate(groups):
        rows += [{"x": v, "g": f"b{i}"} for v in g]
    return pd.DataFrame(rows)


CLEAN = [[10, 12], [11, 13], [9, 11], [12, 14], [10, 12]]


def test_xbar_r_hand_computed():
    r = sw.xbar_r(make_df(CLEAN), value="x", subgroup="g", rules="none")
    sigma = 2.0 / c.d2(2)
    assert r.stats["xbar_center"] == pytest.approx(11.4)
    assert r.stats["r_center"] == pytest.approx(2.0)
    assert r.stats["sigma_within"] == pytest.approx(sigma)
    assert r.stats["xbar_ucl"] == pytest.approx(11.4 + 3 * sigma / np.sqrt(2))
    assert r.stats["r_ucl"] == pytest.approx(c.D4(2) * 2.0)
    assert r.stats["r_lcl"] == 0.0
    assert r.ok
    assert r.meta["n"] == 5 and r.meta["n_total"] == 10


def test_xbar_s_hand_computed():
    r = sw.xbar_s(make_df(CLEAN), value="x", subgroup="g", rules="none")
    sbar = float(np.std([10, 12], ddof=1))
    assert r.stats["s_center"] == pytest.approx(sbar)
    assert r.stats["sigma_within"] == pytest.approx(sbar / c.c4(2))
    assert r.stats["s_ucl"] == pytest.approx(c.B4(2) * sbar)
    assert r.ok


def test_shifted_subgroup_triggers_nelson_1():
    r = sw.xbar_r(make_df(CLEAN + [[17, 19]]), value="x", subgroup="g")
    assert not r.ok
    assert any(s.rule == "nelson_1" and s.chart == "xbar" for s in r.signals)


def test_xbar_r_rejects_unequal_sizes_and_points_to_xbar_s():
    df = make_df(CLEAN)
    df = pd.concat([df, pd.DataFrame([{"x": 11.0, "g": "b0"}])], ignore_index=True)
    with pytest.raises(ValueError, match="equal subgroup sizes"):
        sw.xbar_r(df, value="x", subgroup="g")


# Independent hand reference for variable-size Xbar-S (see derivation in the
# variable-sizes guide): pooled sigma over n=3,4,5 subgroups.
VAR_DF = pd.DataFrame(
    [{"g": lab, "x": float(v)}
     for lab, vals in [("A", [10, 12, 11]),
                       ("B", [9, 11, 10, 12]),
                       ("C", [11, 10, 12, 13, 9])]
     for v in vals]
)


def test_xbar_s_variable_sizes_hand_computed():
    r = sw.xbar_s(VAR_DF, value="x", subgroup="g", rules="none")
    # pooled sd = sqrt(17/9), sigma = pooled_sd / c4(10), grand mean weighted
    pooled_sd = (17 / 9) ** 0.5
    sigma = pooled_sd / c.c4(10)
    assert r.stats["sigma_within"] == pytest.approx(sigma)
    assert r.stats["xbar_center"] == pytest.approx(130 / 12)
    assert "xbar_ucl" not in r.stats  # limits vary, so no scalar keys
    assert r.meta["variable_sizes"] is True

    t = r.table
    for lab, n in zip(["A", "B", "C"], [3, 4, 5]):
        row = t.loc[lab]
        assert row["mean_ucl"] == pytest.approx(130 / 12 + 3 * sigma / n**0.5)
        assert row["mean_lcl"] == pytest.approx(130 / 12 - 3 * sigma / n**0.5)
        assert row["stdev_ucl"] == pytest.approx(c.B6(n) * sigma)
        assert row["stdev_lcl"] == pytest.approx(c.B5(n) * sigma)


def test_xbar_s_variable_baseline_roundtrips(tmp_path):
    fit = sw.xbar_s(VAR_DF, value="x", subgroup="g")
    path = tmp_path / "var.json"
    fit.baseline.save(path)
    new = pd.DataFrame(
        [{"g": "X", "x": v} for v in [10, 11, 12]]
        + [{"g": "Y", "x": v} for v in [9, 10, 11, 12, 13]]
    )
    r = sw.xbar_s(new, value="x", subgroup="g", limits=path)
    assert "Phase II" in r.meta["source"]
    assert r.stats["xbar_center"] == pytest.approx(fit.stats["xbar_center"])
    assert r.table["mean_ucl"].iloc[0] == pytest.approx(
        fit.stats["xbar_center"] + 3 * fit.stats["sigma_within"] / 3**0.5
    )


def test_xbar_s_variable_sizes_render(tmp_path):
    import matplotlib

    matplotlib.use("Agg")
    r = sw.xbar_s(VAR_DF, value="x", subgroup="g")
    r.plot()  # stair-step renderer must not need scalar limit keys
    out = r.to_html(tmp_path / "var.html")
    assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_xbar_s_variable_echoes_method(tmp_path):
    r = sw.xbar_s(VAR_DF, value="x", subgroup="g", method="sbar")
    assert r.params["method"] == "sbar"  # faithful echo
    assert "pooled" in r.meta["source"]  # actual estimator disclosed


def test_xbar_s_variable_sizes_flags_a_wide_subgroup(tmp_path):
    # judge a wide subgroup against frozen limits, so it cannot inflate its own sigma
    path = tmp_path / "var.json"
    sw.xbar_s(VAR_DF, value="x", subgroup="g").baseline.save(path)
    new = pd.DataFrame([{"g": "D", "x": v} for v in [2, 20, 5, 18]])
    r = sw.xbar_s(new, value="x", subgroup="g", limits=path)
    assert any(s.chart == "s" and s.rule == "beyond_limits" for s in r.signals)


def test_missing_subgroup_arg_teaches():
    with pytest.raises(ValueError, match='subgroup="batch"'):
        sw.xbar_r(pd.DataFrame({"torque": [1.0, 2.0], "batch": ["a", "a"]}), value="torque")


def test_frozen_baseline_workflow(tmp_path):
    path = tmp_path / "xbar_baseline.json"
    sw.xbar_r(make_df(CLEAN), value="x", subgroup="g", rules="none").baseline.save(path)

    shifted = [[v + 2.0 for v in g] for g in CLEAN]
    r = sw.xbar_r(make_df(shifted), value="x", subgroup="g", limits=str(path))
    assert not r.ok
    assert "Phase II" in r.meta["source"]


def test_baseline_subgroup_size_mismatch_teaches(tmp_path):
    path = tmp_path / "b.json"
    sw.xbar_r(make_df(CLEAN), value="x", subgroup="g", rules="none").baseline.save(path)
    triples = [[10, 11, 12], [11, 12, 13]]
    with pytest.raises(ValueError, match="subgroup size"):
        sw.xbar_r(make_df(triples), value="x", subgroup="g", limits=str(path))


def test_baseline_chart_mismatch_teaches():
    imr_baseline = sw.imr([10.0, 11.0, 10.5, 11.5], rules="none").baseline
    with pytest.raises(ValueError, match="fitted for 'imr'"):
        sw.xbar_r(make_df(CLEAN), value="x", subgroup="g", limits=imr_baseline)
    with pytest.raises(ValueError, match="fitted for"):
        sw.imr([10.0, 11.0], limits=sw.xbar_r(make_df(CLEAN), value="x", subgroup="g").baseline)


def test_plot_smoke():
    import matplotlib

    matplotlib.use("Agg")
    axes = sw.xbar_r(make_df(CLEAN), value="x", subgroup="g").plot()
    assert len(axes) == 2
