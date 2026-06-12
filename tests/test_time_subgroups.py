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
