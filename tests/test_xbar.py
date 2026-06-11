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


def test_unequal_subgroup_sizes_teach():
    df = make_df(CLEAN)
    df = pd.concat([df, pd.DataFrame([{"x": 11.0, "g": "b0"}])], ignore_index=True)
    with pytest.raises(ValueError, match="equal subgroup sizes"):
        sw.xbar_r(df, value="x", subgroup="g")


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
