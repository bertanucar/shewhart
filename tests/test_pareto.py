import pandas as pd
import pytest

import shewhart as sw


def test_pareto_from_mapping():
    r = sw.pareto({"scratch": 42, "dent": 17, "stain": 5, "burr": 1})
    t = r.table
    assert list(t.index) == ["scratch", "dent", "stain", "burr"]
    assert r.stats["total"] == 65.0
    assert r.stats["top_share"] == pytest.approx(42 / 65)
    assert t["cumulative_share"].iloc[-1] == pytest.approx(1.0)
    assert r.ok


def test_vital_few_covers_80_percent():
    r = sw.pareto({"a": 50, "b": 30, "c": 15, "d": 5})
    assert r.stats["n_for_80pct"] == 2.0  # a + b = 80%
    assert "a, b" in r.meta["source"]


def test_pareto_from_dataframe_counts_and_weights():
    df = pd.DataFrame(
        {"defect": ["scratch", "dent", "scratch", "stain", "scratch"],
         "cost": [10.0, 100.0, 10.0, 1.0, 10.0]}
    )
    by_count = sw.pareto(df, by="defect")
    assert by_count.table["count"].iloc[0] == 3  # scratch most frequent

    by_cost = sw.pareto(df, by="defect", weights="cost")
    assert by_cost.table.index[0] == "dent"  # dent most expensive


def test_pareto_from_raw_labels():
    r = sw.pareto(["a", "b", "a", "a", "c"])
    assert r.table["count"].iloc[0] == 3


def test_dataframe_requires_by_and_teaches():
    with pytest.raises(ValueError, match='by="defect_type"'):
        sw.pareto(pd.DataFrame({"defect_type": ["a"], "n": [1]}))


def test_empty_and_negative_teach():
    with pytest.raises(ValueError, match="no categories"):
        sw.pareto({"a": 0, "b": 0})
    with pytest.raises(ValueError, match="non-negative"):
        sw.pareto({"a": -1, "b": 2})


def test_plot_smoke():
    import matplotlib

    matplotlib.use("Agg")
    ax = sw.pareto({"a": 5, "b": 3, "c": 1}).plot()
    assert ax.get_title() == "Pareto chart"
