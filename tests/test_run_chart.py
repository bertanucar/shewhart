import pytest

import shewhart as sw


def test_clustering_detected():
    r = sw.run_chart([1, 1, 1, 5, 5, 5])
    assert r.stats["runs_about_median"] == 2.0
    assert r.stats["runs_expected"] == 4.0
    assert r.stats["p_clustering"] == pytest.approx(0.0339445774, abs=1e-9)
    assert any(s.rule == "clustering" for s in r.signals)


def test_mixtures_and_oscillation_detected():
    r = sw.run_chart([1, 5, 1, 5, 1, 5, 1, 5])
    rules = {s.rule for s in r.signals}
    assert "mixtures" in rules
    assert "oscillation" in rules


def test_trend_detected():
    r = sw.run_chart([1, 2, 3, 4, 5, 6, 7])
    assert any(s.rule == "trends" for s in r.signals)


def test_quiet_sequence_is_ok():
    r = sw.run_chart([2.0, 4.0, 1.0, 5.0, 3.0])
    assert r.ok


def test_signal_without_points_renders():
    r = sw.run_chart([1, 1, 1, 5, 5, 5])
    text = str(r.signals[0])
    assert "clustering" in text and "p =" in text


def test_too_few_observations_teaches():
    with pytest.raises(ValueError, match="at least 4"):
        sw.run_chart([1, 2, 3])


def test_plot_smoke():
    import matplotlib

    matplotlib.use("Agg")
    ax = sw.run_chart([3, 1, 4, 1, 5, 9, 2, 6]).plot()
    assert hasattr(ax, "axhline")
