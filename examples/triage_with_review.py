"""Triage a batch with one call, for a human or an agent.

``sw.review`` picks the chart, checks the assumptions, runs capability
against the spec, and returns one structured verdict. ``rv.ok`` is the gate;
``rv.to_dict()`` is the JSON an agent acts on without touching a formula.

Run it:

    python examples/triage_with_review.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import shewhart as sw


def _batch(seed: int = 9) -> np.ndarray:
    # in control, but the spec window is tight enough to bite on capability
    return np.random.default_rng(seed).normal(10.0, 0.05, 80)


def main(outdir: str | Path = ".") -> int:
    rv = sw.review(_batch(), lsl=9.85, usl=10.15)

    print(rv.headline)
    print(f"gate (rv.ok): {rv.ok}")
    if rv.failures:
        print(f"failures: {', '.join(rv.failures)}")
    for rec in rv.recommendations:
        print(f"  - [{rec['code']}] {rec['message']}")

    # the same verdict an agent would consume over MCP
    verdict = json.dumps(rv.to_dict(), indent=2)
    (Path(outdir) / "verdict.json").write_text(verdict, encoding="utf-8")
    return 0 if rv.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
