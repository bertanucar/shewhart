import math

import numpy as np
import pandas as pd
import pytest

import shewhart as sw

DEFECTIVES = [2, 3, 1, 4, 2]


def test_p_chart_hand_computed():
    df = pd.DataFrame({"rejects": DEFECTIVES, "inspected": [50] * 5})
    r = sw.p_chart(df, defectives="rejects", size="inspected", rules="none")
    pbar = 12 / 250
    sigma = math.sqrt(pbar * (1 - pbar) / 50)
    assert r.stats["p_center"] == pytest.approx(pbar)
    assert r.stats["p_ucl"] == pytest.approx(pbar + 3 * sigma)
    assert r.stats["p_lcl"] == 0.0  # clamped
    assert r.ok


def test_p_chart_varying_sizes_stair_step():
    df = pd.DataFrame({"d": [2, 30, 1], "n": [50, 400, 60]})
    r = sw.p_chart(df, defectives="d", size="n", rules="none")
    assert "p_ucl" not in r.stats  # no scalar limits when sizes vary
    t = r.table
    assert t["ucl"].nunique() == 3  # per-point limits
    pbar = 33 / 510
    assert t["ucl"].iloc[1] == pytest.approx(pbar + 3 * math.sqrt(pbar * (1 - pbar) / 400))


def test_p_chart_spike_flags_test_1():
    df = pd.DataFrame({"d": [2, 3, 1, 4, 2, 20], "n": [50] * 6})
    r = sw.p_chart(df, defectives="d", size="n")
    assert not r.ok
    assert any(s.rule == "nelson_1" for s in r.signals)


def test_p_chart_defectives_exceed_size_teaches():
    df = pd.DataFrame({"d": [60], "n": [50]})
    with pytest.raises(ValueError):
        sw.p_chart(pd.concat([df, df]), defectives="d", size="n")


def test_np_chart_hand_computed_and_constant_n_required():
    df = pd.DataFrame({"d": DEFECTIVES})
    r = sw.np_chart(df, defectives="d", size=50, rules="none")
    p = 12 / 250
    assert r.stats["np_center"] == pytest.approx(2.4)
    assert r.stats["np_ucl"] == pytest.approx(2.4 + 3 * math.sqrt(2.4 * (1 - p)))
    assert r.stats["np_lcl"] == 0.0
    with pytest.raises(ValueError, match="constant subgroup size"):
        sw.np_chart(df, defectives="d", size=[50, 50, 50, 50, 60])


def test_c_chart_hand_computed_with_plain_list():
    r = sw.c_chart([3, 2, 4, 1, 3], rules="none")
    assert r.stats["c_center"] == pytest.approx(2.6)
    assert r.stats["c_ucl"] == pytest.approx(2.6 + 3 * math.sqrt(2.6))
    assert r.stats["c_lcl"] == 0.0
    assert r.ok


def test_u_chart_varying_sizes():
    df = pd.DataFrame({"flaws": [6, 4, 9, 5], "units": [3, 2, 4, 2]})
    r = sw.u_chart(df, defects="flaws", size="units", rules="none")
    ubar = 24 / 11
    assert r.stats["u_center"] == pytest.approx(ubar)
    assert r.table["ucl"].iloc[0] == pytest.approx(ubar + 3 * math.sqrt(ubar / 3))
    assert "u_ucl" not in r.stats


def test_run_rules_apply_to_attribute_charts():
    # 9 consecutive points above center triggers nelson_2
    counts = [1, 1, 1, 1, 1, 5, 5, 5, 5, 5, 5, 5, 5, 5]
    r = sw.c_chart(counts)
    assert any(s.rule == "nelson_2" for s in r.signals)


def test_zone_rules_rejected_with_teaching_error():
    with pytest.raises(ValueError, match="attribute-chart tests"):
        sw.c_chart([1, 2, 3, 4], rules="western_electric")


def test_non_integer_counts_teach():
    with pytest.raises(ValueError, match="integer counts"):
        sw.c_chart([1.5, 2.0, 3.0])


def test_frozen_baseline_workflow(tmp_path):
    df = pd.DataFrame({"d": DEFECTIVES, "n": [50] * 5})
    path = tmp_path / "p_baseline.json"
    sw.p_chart(df, defectives="d", size="n", rules="none").baseline.save(path)

    worse = pd.DataFrame({"d": [9, 11, 10, 12], "n": [50] * 4})
    r = sw.p_chart(worse, defectives="d", size="n", limits=str(path))
    assert not r.ok
    assert "Phase II" in r.meta["source"]


def test_np_baseline_size_mismatch_teaches(tmp_path):
    df = pd.DataFrame({"d": DEFECTIVES})
    path = tmp_path / "np.json"
    sw.np_chart(df, defectives="d", size=50, rules="none").baseline.save(path)
    with pytest.raises(ValueError, match="does not\nmatch|does not match"):
        sw.np_chart(df, defectives="d", size=40, limits=str(path))


def test_plot_smoke_single_panel():
    import matplotlib

    matplotlib.use("Agg")
    ax = sw.c_chart([3, 2, 4, 1, 3]).plot()
    assert hasattr(ax, "axhline")
