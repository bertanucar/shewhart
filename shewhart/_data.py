"""Shared input coercion."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def time_subgroups(data: Any, subgroup: str | None) -> pd.Series | None:
    """Resolve subgroup= given as a time window.

    Fixed windows ("15min", "1h", "1D") label each row by the floored
    timestamp; calendar windows ("W", "ME", "QE") label it by the start of
    its period. Returns a label Series aligned to the DataFrame, or None if
    subgroup= does not look like a time-window specification.
    """
    if (
        not isinstance(data, pd.DataFrame)
        or subgroup is None
        or subgroup in getattr(data, "columns", ())
    ):
        return None
    if not isinstance(data.index, pd.DatetimeIndex):
        return None
    try:
        offset = pd.tseries.frequencies.to_offset(subgroup)
    except ValueError:
        return None

    index = data.index
    try:
        labels = index.floor(offset)  # fixed windows
    except ValueError:
        try:
            labels = index.to_period(offset).start_time  # calendar windows
        except (ValueError, AttributeError):
            raise ValueError(
                f"subgroup={subgroup!r} has no usable time window. Use a "
                'fixed window like "15min", "1h", "1D", or a calendar window '
                'like "W", "ME", or "QE".'
            ) from None
    return pd.Series(labels, index=index)


def as_series(data: Any, value: str | None, fname: str) -> pd.Series:
    """Coerce input to a float Series; DataFrames require value=."""
    if isinstance(data, pd.DataFrame):
        if value is None or value not in data.columns:
            raise ValueError(
                f"{fname}() got a DataFrame, so value= must name the measurement "
                f"column. Columns: {list(data.columns)}. "
                f'Example: sw.{fname}(df, value="torque")'
            )
        s = data[value]
    elif isinstance(data, pd.Series):
        s = data
    else:
        s = pd.Series(np.asarray(data, dtype="float64"))
    return s.astype("float64").dropna()
