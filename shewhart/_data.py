"""Shared input coercion."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def time_subgroups(data: Any, subgroup: str | None) -> pd.Series | None:
    """Resolve subgroup= given as a time window like "15min" or "1H".

    Returns a label Series aligned to the DataFrame, or None if subgroup=
    does not look like a time-window specification.
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
        pd.tseries.frequencies.to_offset(subgroup)
    except ValueError:
        return None
    try:
        return pd.Series(data.index.floor(subgroup), index=data.index)
    except ValueError:
        raise ValueError(
            f"subgroup={subgroup!r} is not a fixed time window. Use fixed "
            'windows like "15min", "1H", or "1D"; calendar frequencies like '
            '"W" or "M" are not supported yet.'
        ) from None


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
