"""Shared input coercion."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


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
