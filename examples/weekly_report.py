"""A weekly SPC report as a single self-contained HTML file.

Generates one month of daily measurements and a weekly reject count, charts
each with the right tool, and writes one HTML page whose banner is green only
if every chart is in control. Point a Monday cron job at this and email the
file.

The measurement chart uses calendar subgrouping (``subgroup="W"``): each week
becomes one subgroup, the weeks hold different numbers of days, and xbar_s
draws stair-step limits for the varying sizes.

Run it:

    python examples/weekly_report.py    # writes weekly_report.html
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import shewhart as sw


def _measurements(seed: int = 2) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=28, freq="D")
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"diameter": rng.normal(10.0, 0.4, len(idx))}, index=idx)


def _rejects(seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    inspected = rng.integers(180, 220, 12)
    return pd.DataFrame({
        "rejects": rng.binomial(inspected, 0.04),
        "inspected": inspected,
    })


def main(outdir: str | Path = ".") -> int:
    out = Path(outdir) / "weekly_report.html"

    results = [
        sw.xbar_s(_measurements(), value="diameter", subgroup="W"),
        sw.p_chart(_rejects(), defectives="rejects", size="inspected"),
    ]
    sw.report(results, out, title="Line 3 weekly")

    print(f"wrote {out}")
    print("in control" if all(r.ok for r in results) else "signals present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
