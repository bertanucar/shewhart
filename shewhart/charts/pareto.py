"""Pareto analysis of defect categories.

Counts occurrences (or sums a weight column, e.g. cost) per category, sorts
descending, and reports cumulative shares. The summary names the vital few:
the smallest set of categories covering 80% of the total.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from .._registry import register
from .._result import Result, data_hash, utcnow
from .._version import __version__


def _tally(data: Any, by: str | None, weights: str | None) -> pd.Series:
    if isinstance(data, pd.DataFrame):
        if by is None or by not in data.columns:
            raise ValueError(
                f"pareto() got a DataFrame, so by= must name the category "
                f"column. Columns: {list(data.columns)}. "
                'Example: sw.pareto(df, by="defect_type")'
            )
        if weights is not None:
            if weights not in data.columns:
                raise ValueError(
                    f'pareto(): weights="{weights}" is not a column. '
                    f"Columns: {list(data.columns)}."
                )
            tally = data.groupby(by, sort=False)[weights].sum()
        else:
            tally = data[by].value_counts(sort=False)
    elif isinstance(data, Mapping):
        tally = pd.Series(data, dtype="float64")
    else:
        tally = pd.Series(list(data)).value_counts(sort=False)

    tally = tally.astype("float64").dropna()
    if (tally < 0).any():
        raise ValueError("pareto(): category values must be non-negative.")
    tally = tally[tally > 0]
    if tally.empty:
        raise ValueError(
            "pareto() found no categories with positive counts. "
            'Example: sw.pareto({"scratch": 42, "dent": 17, "stain": 5})'
        )
    return tally.sort_values(ascending=False)


@register("pareto")
def pareto(data: Any, *, by: str | None = None, weights: str | None = None) -> Result:
    """Pareto analysis: which categories dominate the problem.

        r = sw.pareto(df, by="defect_type")
        r = sw.pareto(df, by="defect_type", weights="cost")
        r = sw.pareto({"scratch": 42, "dent": 17, "stain": 5})
    """
    tally = _tally(data, by, weights)
    total = float(tally.sum())
    share = tally / total
    cumulative = share.cumsum()

    n_for_80 = int(np.searchsorted(cumulative.to_numpy(), 0.8) + 1)
    table = pd.DataFrame(
        {"count": tally, "share": share, "cumulative_share": cumulative}
    )
    table.index.name = by or "category"

    vital = ", ".join(map(str, tally.index[:n_for_80]))
    return Result(
        method="pareto",
        params={"by": by, "weights": weights, "rules": None},
        stats={
            "total": total,
            "n_categories": float(len(tally)),
            "top_share": float(share.iloc[0]),
            "n_for_80pct": float(n_for_80),
        },
        signals=(),
        meta={
            "n": int(len(tally)),
            "version": __version__,
            "input": data_hash(tally.to_numpy()),
            "computed_at": utcnow(),
            "source": f"vital few (80%): {vital}",
        },
        baseline=None,
        _table=table,
    )
