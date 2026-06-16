"""Time-window subgrouping: subgroup="1H"-style on a DatetimeIndex."""

import numpy as np
import pandas as pd
import pytest

import shewhart as sw


def hourly_df(hours=5, per_hour=3, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-06-12 06:00", periods=hours * per_hour,
                        freq=f"{60 // per_hour}min")
    return pd.DataFrame({"torque": rng.normal(50, 1, len(idx))}, index=idx)


def test_xbar_r_with_time_window():
    df = hourly_df()
    r = sw.xbar_r(df, value="torque", subgroup="1h")
    assert r.meta["n"] == 5  # five hourly subgroups
    assert r.stats["n_sub"] == 3


def test_capability_with_time_window_pooled():
    df = hourly_df()
    r = sw.capability(df, value="torque", subgroup="1h", lsl=45, usl=55)
    assert r.meta["df_within"] == 5 * (3 - 1)


def test_column_name_still_wins_over_window_syntax():
    df = hourly_df().assign(batch=lambda d: ["a", "b", "c"] * 5)
    r = sw.xbar_r(df, value="torque", subgroup="batch")
    assert r.stats["n_sub"] == 5  # grouped by the column, not by time


def test_non_datetime_index_teaches():
    df = pd.DataFrame({"torque": [1.0, 2.0, 3.0, 4.0]})
    with pytest.raises(ValueError, match="naming a column"):
        sw.xbar_r(df, value="torque", subgroup="1h")


def daily_df(days=90, seed=1):
    idx = pd.date_range("2026-01-01", periods=days, freq="D")
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"x": rng.normal(50, 2, days)}, index=idx)


def test_weekly_calendar_window_groups_by_week():
    df = daily_df()
    r = sw.xbar_s(df, value="x", subgroup="W")
    # weeks have differing sizes (a partial first week), so it is variable
    assert r.meta["variable_sizes"] is True
    assert r.table["n"].max() == 7
    # labels are week-start timestamps
    assert (r.table.index == pd.DatetimeIndex(r.table.index).normalize()).all()


def test_monthly_calendar_window_groups_by_month():
    df = daily_df(days=90)
    r = sw.xbar_s(df, value="x", subgroup="ME")
    assert r.meta["n"] == 3
    assert r.table["n"].tolist() == [31, 28, 31]


def test_review_routes_weekly_to_xbar_s():
    r = sw.review(daily_df(), value="x", subgroup="W")
    assert r.selection["chart"] == "xbar_s"


def test_unusable_window_teaches():
    df = daily_df()
    with pytest.raises(ValueError, match="time window"):
        sw.xbar_s(df, value="x", subgroup="1.5W")
