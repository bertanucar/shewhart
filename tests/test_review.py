import json

import numpy as np
import pandas as pd
import pytest

import shewhart as sw

# seed 5 gives 50 N(10, 0.05) points that are quiet under the full Nelson set
QUIET = np.random.default_rng(5).normal(10, 0.05, 50)


def quiet_df():
    return pd.DataFrame({"d": QUIET})


# -- selection ---------------------------------------------------------------


def test_individuals_select_imr():
    rv = sw.review(quiet_df(), value="d")
    assert rv.selection["chart"] == "imr"
    assert rv.chart.method == "imr"


def test_bare_series_is_the_value_branch():
    rv = sw.review(pd.Series(QUIET))
    assert rv.selection["chart"] == "imr"


def test_subgroup_size_routes_r_vs_s():
    rng = np.random.default_rng(2)
    df4 = pd.DataFrame({"x": rng.normal(0, 1, 100), "b": np.repeat(range(25), 4)})
    df12 = pd.DataFrame({"x": rng.normal(0, 1, 120), "b": np.repeat(range(10), 12)})
    assert sw.review(df4, value="x", subgroup="b").selection["chart"] == "xbar_r"
    assert sw.review(df12, value="x", subgroup="b").selection["chart"] == "xbar_s"


def test_size_one_subgroups_fall_back_to_imr():
    df = pd.DataFrame({"x": QUIET[:20], "b": range(20)})
    rv = sw.review(df, value="x", subgroup="b")
    assert rv.selection["chart"] == "imr"


def test_attribute_routing_p_np_c_u():
    rng = np.random.default_rng(3)
    k = 30
    const = pd.DataFrame({"r": rng.binomial(100, 0.05, k), "n": [100] * k})
    vary_n = rng.integers(80, 140, k)
    vary = pd.DataFrame({"r": rng.binomial(vary_n, 0.05), "n": vary_n})
    counts = pd.DataFrame({"c": rng.poisson(4, k)})
    areas = rng.uniform(1, 2, k)
    rates = pd.DataFrame({"c": rng.poisson(5 * areas), "a": areas})

    assert sw.review(const, defectives="r", size="n").selection["chart"] == "np_chart"
    assert sw.review(vary, defectives="r", size="n").selection["chart"] == "p_chart"
    assert sw.review(counts, defects="c").selection["chart"] == "c_chart"
    assert sw.review(rates, defects="c", size="a").selection["chart"] == "u_chart"


def test_overdispersed_proportions_switch_to_laney():
    rng = np.random.default_rng(4)
    n = np.full(30, 2000)
    p = rng.normal(0.05, 0.015, 30).clip(0.01)
    df = pd.DataFrame({"r": rng.binomial(n, p), "n": n})
    rv = sw.review(df, defectives="r", size="n")
    assert rv.selection["chart"] == "laney_p"
    assert "sigma_z" in rv.selection["reason"]
    over = [c for c in rv.checks if c.name == "overdispersion"]
    assert over and over[0].status == "pass"  # handled by the switch


def test_c_chart_overdispersion_recommends_instead_of_switching():
    rng = np.random.default_rng(8)
    lam = rng.normal(20, 8, 30).clip(2)
    df = pd.DataFrame({"c": rng.poisson(lam)})
    rv = sw.review(df, defects="c")
    assert rv.selection["chart"] == "c_chart"
    assert any(r["code"] == "consider_laney" for r in rv.recommendations)


# -- composition: review numbers == direct-call numbers ----------------------


def test_control_block_equals_direct_chart_call():
    rv = sw.review(quiet_df(), value="d")
    direct = sw.imr(quiet_df(), value="d")
    assert rv.to_dict()["control"]["stats"] == direct.to_dict()["stats"]


def test_capability_stats_equal_direct_call():
    rv = sw.review(quiet_df(), value="d", lsl=9.7, usl=10.3)
    direct = sw.capability(quiet_df(), value="d", lsl=9.7, usl=10.3)
    assert rv.to_dict()["capability"]["stats"] == direct.to_dict()["stats"]


# -- checks -------------------------------------------------------------------


def test_sample_size_boundaries():
    fail = sw.review(pd.Series(QUIET[:8]))
    warn = sw.review(pd.Series(QUIET[:15]))
    ok = sw.review(pd.Series(QUIET))
    by_name = lambda rv: {c.name: c.status for c in rv.checks}
    assert by_name(fail)["sample_size"] == "fail" and not fail.ok
    assert "check:sample_size" in fail.failures
    assert by_name(warn)["sample_size"] == "warn"
    assert by_name(ok)["sample_size"] == "pass"


def test_sample_size_does_not_run_in_phase_two(tmp_path):
    base = sw.review(pd.Series(QUIET)).baseline
    path = tmp_path / "b.json"
    base.save(path)
    rv = sw.review(pd.Series(QUIET[:6]), limits=path)
    assert all(c.name != "sample_size" for c in rv.checks)
    assert rv.ok  # a small healthy window must gate green in Phase II


def test_flat_line_fails_variation_not_crashes():
    rv = sw.review([10.0] * 15, lsl=9, usl=11)
    assert "check:variation" in rv.failures
    assert rv.capability_block["status"] == "not_assessed"
    json.dumps(rv.to_dict(), allow_nan=False)  # finite-or-null, strictly


def test_normality_warns_on_skewed_data():
    x = np.random.default_rng(6).exponential(1.0, 80)
    rv = sw.review(pd.Series(x))
    norm = [c for c in rv.checks if c.name == "normality"]
    assert norm and norm[0].status == "warn"
    assert norm[0].value > norm[0].threshold


def test_autocorrelation_warns_on_ar1_data():
    rng = np.random.default_rng(7)
    x = np.zeros(80)
    for t in range(1, 80):
        x[t] = 0.85 * x[t - 1] + rng.normal()
    rv = sw.review(pd.Series(x))
    auto = [c for c in rv.checks if c.name == "autocorrelation"]
    assert auto and auto[0].status == "warn"
    assert any(r["code"] == "model_autocorrelation" for r in rv.recommendations)


def test_binary_data_warns_toward_attribute_charts():
    rv = sw.review(pd.Series([0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0] * 3, dtype=float))
    assert any(c.name == "binary_data" and c.status == "warn" for c in rv.checks)
    assert any(r["code"] == "use_attribute_chart" for r in rv.recommendations)


def test_disjoint_specs_warn_about_units():
    rv = sw.review(pd.Series(QUIET), lsl=990, usl=1010)  # data near 10
    spec = [c for c in rv.checks if c.name == "spec_plausibility"]
    assert spec and spec[0].status == "warn" and spec[0].value == 0.0
    assert any(r["code"] == "check_spec_units" for r in rv.recommendations)


def test_target_outside_specs_warns():
    rv = sw.review(pd.Series(QUIET), lsl=9.7, usl=10.3, target=11.0)
    assert any(c.name == "target_within_specs" and c.status == "warn" for c in rv.checks)


# -- capability doctrine -------------------------------------------------------


def test_capable_marginal_inadequate_thresholds():
    wide = sw.review(quiet_df(), value="d", lsl=9.7, usl=10.3)
    tight = sw.review(quiet_df(), value="d", lsl=9.95, usl=10.05)
    assert wide.capability_block["status"] == "capable" and wide.ok
    assert tight.capability_block["status"] == "inadequate"
    assert "capability_inadequate" in tight.failures


def test_no_specs_means_not_assessed_with_reason():
    rv = sw.review(quiet_df(), value="d")
    assert rv.capability is None
    assert rv.capability_block["status"] == "not_assessed"
    assert rv.capability_block["reason"] == "no_spec_limits"
    assert rv.ok  # not_assessed never gates


def test_out_of_control_withholds_capability():
    x = np.concatenate([QUIET[:30], [10.9, 11.0]])
    rv = sw.review(pd.Series(x), lsl=9.8, usl=10.2)
    assert not rv.ok and "out_of_control" in rv.failures
    assert rv.capability is None
    assert rv.capability_block["reason"] == "not_in_control"
    assert rv.capability_block["index_value"] is None


def test_marginal_gates_and_recommends_the_interval():
    # sigma 0.05, specs at +-0.18 -> cpk just above 1.0
    rv = sw.review(quiet_df(), value="d", lsl=9.825, usl=10.185)
    assert rv.capability_block["status"] == "marginal"
    assert "capability_marginal" in rv.failures and not rv.ok
    assert any(r["code"] == "review_capability_ci" for r in rv.recommendations)


# -- Phase II ------------------------------------------------------------------


def test_phase_two_dispatches_on_the_baseline_not_the_data():
    rng = np.random.default_rng(9)
    df = pd.DataFrame({"x": rng.normal(0, 1, 100), "b": np.repeat(range(20), 5)})
    base = sw.xbar_s(df, value="x", subgroup="b").baseline  # deliberate S at n=5
    df_new = pd.DataFrame({"x": rng.normal(0, 1, 25), "b": np.repeat(range(5), 5)})
    rv = sw.review(df_new, value="x", subgroup="b", limits=base)
    assert rv.selection["chart"] == "xbar_s"  # not re-derived as xbar_r
    assert rv.params["limits"] == "frozen"


def test_phase_two_family_mismatch_teaches():
    base = sw.review(pd.Series(QUIET)).baseline
    df = pd.DataFrame({"r": [1, 2], "n": [50, 50]})
    with pytest.raises(ValueError, match="takes value="):
        sw.review(df, defectives="r", size="n", limits=base)


def test_phase_two_rejects_non_shewhart_baselines():
    base = sw.cusum(QUIET).baseline
    with pytest.raises(ValueError, match="cusum"):
        sw.review(pd.Series(QUIET), limits=base)


def test_phase_two_keeps_the_frozen_attribute_chart():
    rng = np.random.default_rng(10)
    k, n = 30, np.full(30, 500)
    df = pd.DataFrame({"r": rng.binomial(n, 0.04), "n": n})
    base = sw.p_chart(df, defectives="r", size="n").baseline
    df_new = pd.DataFrame({"r": rng.binomial(n[:5], 0.04), "n": n[:5]})
    rv = sw.review(df_new, defectives="r", size="n", limits=base)
    assert rv.selection["chart"] == "p_chart"  # sigma_z is a finding, not a re-selection


def test_phase_two_sigma_z_for_laney_and_c_baselines():
    rng = np.random.default_rng(11)
    n = np.full(30, 2000)
    p = rng.normal(0.05, 0.015, 30).clip(0.01)
    df = pd.DataFrame({"r": rng.binomial(n, p), "n": n})
    base = sw.laney_p(df, defectives="r", size="n").baseline
    rv = sw.review(df.tail(6), defectives="r", size="n", limits=base)
    over = [c for c in rv.checks if c.name == "overdispersion"]
    assert over and over[0].value == pytest.approx(base.stats["sigma_z"])
    assert "Laney limits in use" in over[0].note
    json.dumps(rv.to_dict(), allow_nan=False)

    lam = rng.normal(20, 8, 30).clip(2)
    dfc = pd.DataFrame({"c": rng.poisson(lam)})
    cbase = sw.c_chart(dfc, defects="c").baseline
    rvc = sw.review(dfc.tail(8), defects="c", limits=cbase)
    over = [c for c in rvc.checks if c.name == "overdispersion"]
    assert over and over[0].value is not None  # probed, not "not estimable"


def test_phase_two_rejects_arguments_the_baseline_cannot_use():
    base = sw.review(pd.Series(QUIET)).baseline
    df = pd.DataFrame({"x": QUIET, "b": np.repeat(range(10), 5)})
    with pytest.raises(ValueError, match="charts individuals"):
        sw.review(df, value="x", subgroup="b", limits=base)
    dfc = pd.DataFrame({"c": np.random.default_rng(0).poisson(4, 25), "a": 1.0})
    cbase = sw.c_chart(dfc, defects="c").baseline
    with pytest.raises(ValueError, match="constant opportunity"):
        sw.review(dfc, defects="c", size="a", limits=cbase)


# -- teaching errors -----------------------------------------------------------


def test_branch_validation_teaches():
    with pytest.raises(ValueError, match="exactly one of"):
        sw.review(pd.DataFrame({"a": [1.0]}))
    with pytest.raises(ValueError, match="exactly one of"):
        sw.review(pd.DataFrame({"a": [1.0], "b": [2]}), value="a", defects="b")
    with pytest.raises(ValueError, match="attribute charts judge counts"):
        sw.review(pd.DataFrame({"r": [1], "n": [5]}), defectives="r", size="n", lsl=1)
    with pytest.raises(ValueError, match="defects= instead"):
        sw.review(pd.DataFrame({"r": [1, 2]}), defectives="r")
    with pytest.raises(ValueError, match="defectives exceed size"):
        sw.review(pd.DataFrame({"r": [9, 2], "n": [5, 5]}), defectives="r", size="n")
    with pytest.raises(ValueError, match="zone tests"):
        sw.review(pd.DataFrame({"r": [1, 2], "n": [5, 5]}), defectives="r",
                  size="n", rules="western_electric")
    with pytest.raises(ValueError, match="subgroup sizes vary"):
        sw.review(pd.DataFrame({"x": [1.0] * 7 + [2.0] * 8, "b": [1] * 7 + [2] * 8}),
                  value="x", subgroup="b")
    with pytest.raises(ValueError, match="lsl must be below usl"):
        sw.review(pd.Series(QUIET), lsl=10, usl=9)
    with pytest.raises(TypeError, match="chart name"):
        sw.review(pd.Series(QUIET), limits={"i_center": 10.0})


def test_dispatch_errors_name_review_and_the_chart():
    df = pd.DataFrame({"x": QUIET, "b": "label"})
    with pytest.raises(ValueError, match="review"):
        sw.review(df, value="x", subgroup="missing")


# -- the frozen verdict schema ---------------------------------------------------


def test_verdict_schema_keys_are_frozen():
    rv = sw.review(quiet_df(), value="d", lsl=9.7, usl=10.3)
    d = rv.to_dict()
    assert sorted(d) == [
        "baseline", "capability", "checks", "control", "failures", "headline",
        "meta", "method", "ok", "params", "recommendations", "schema", "selection",
    ]
    assert d["schema"] == 1 and d["method"] == "review"
    assert sorted(d["capability"]) == ["detail", "index", "index_value", "reason", "stats", "status"]
    assert sorted(d["params"]) == ["defectives", "defects", "limits", "lsl", "rules",
                                   "size", "subgroup", "target", "usl", "value"]
    for c in d["checks"]:
        assert sorted(c) == ["name", "note", "status", "threshold", "value"]
        for field in ("value", "threshold"):
            assert c[field] is None or np.isfinite(c[field])
    for r in d["recommendations"]:
        assert sorted(r) == ["call", "code", "message"]
    assert sorted(d["baseline"]) == ["chart", "created_at", "n", "version"]
    json.dumps(d, allow_nan=False)


def test_signals_carry_index_labels():
    idx = pd.date_range("2026-01-01", periods=32, freq="h")
    x = np.concatenate([QUIET[:30], [10.9, 11.0]])
    rv = sw.review(pd.Series(x, index=idx))
    sig = rv.to_dict()["control"]["signals"][0]
    assert sig["labels"] and sig["labels"][0].startswith("2026-01-0")


def test_ok_iff_failures_empty():
    for rv in [
        sw.review(quiet_df(), value="d"),
        sw.review(quiet_df(), value="d", lsl=9.95, usl=10.05),
        sw.review(pd.Series(QUIET[:8])),
    ]:
        assert rv.ok == (len(rv.failures) == 0)


# -- the Review object -----------------------------------------------------------


def test_baseline_passthrough_roundtrip(tmp_path):
    path = tmp_path / "line.json"
    sw.review(quiet_df(), value="d").baseline.save(path)
    rv = sw.review(quiet_df(), value="d", limits=path)
    assert rv.params["limits"] == "frozen"
    assert "Phase II" in rv.chart.meta["source"]


def test_summary_plot_html_smoke(tmp_path):
    import matplotlib

    matplotlib.use("Agg")
    rv = sw.review(quiet_df(), value="d", lsl=9.7, usl=10.3)
    assert rv.headline in rv.summary()
    assert rv.selection["chart"] in rv.summary()
    rv.plot()
    out = rv.to_html(tmp_path / "rv.html")
    assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert "<pre>" in rv._repr_html_()


def test_meta_extends_the_chart_meta():
    rv = sw.review(quiet_df(), value="d")
    assert rv.meta["n"] == 50 and rv.meta["n_dropped"] == 0
    assert rv.meta["index_start"] == "0" and rv.meta["index_end"] == "49"


def test_missing_values_are_counted_and_reported():
    df = quiet_df()
    df.loc[3, "d"] = np.nan
    rv = sw.review(df, value="d")
    assert rv.meta["n_dropped"] == 1
    assert any(r["code"] == "missing_values_excluded" for r in rv.recommendations)


def test_missing_subgroup_labels_are_counted_too():
    rng = np.random.default_rng(12)
    df = pd.DataFrame({"x": rng.normal(0, 1, 100),
                       "b": np.repeat(np.arange(25.0), 4)})
    df.loc[df["b"] == 7.0, "b"] = np.nan  # one whole subgroup unlabeled
    rv = sw.review(df, value="x", subgroup="b")
    assert rv.meta["n_dropped"] == 4


def test_all_missing_values_teach_instead_of_crashing():
    df = pd.DataFrame({"x": [np.nan] * 20, "b": list(range(5)) * 4})
    with pytest.raises(ValueError, match="no usable rows"):
        sw.review(df, value="x", subgroup="b")


def test_attribute_verdict_is_strict_json():
    rng = np.random.default_rng(4)
    n = np.full(30, 2000)
    p = rng.normal(0.05, 0.015, 30).clip(0.01)
    df = pd.DataFrame({"r": rng.binomial(n, p), "n": n},
                      index=pd.date_range("2026-01-01", periods=30, freq="D"))
    rv = sw.review(df, defectives="r", size="n")
    json.dumps(rv.to_dict(), allow_nan=False)


def test_future_baseline_schema_teaches(tmp_path):
    path = tmp_path / "future.json"
    path.write_text(json.dumps({
        "schema": 99, "chart": "imr", "stats": {}, "n": 1,
        "created_at": "", "shewhart_version": "9.9",
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="schema 99"):
        sw.Baseline.load(path)
