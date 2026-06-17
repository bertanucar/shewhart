"""Fit control limits once, freeze them, monitor new data forever.

This is the workflow shewhart is built around. Phase I estimates limits
from a stable reference period and writes them to a JSON baseline that you
commit to git. Phase II judges each new batch against those frozen limits,
and never recomputes them, so a drift cannot quietly widen the limits and
hide itself.

Run it:

    python examples/fit_freeze_monitor.py

It prints the verdict and exits non-zero when the process is out of control,
which is all a cron job or CI step needs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

import shewhart as sw


def _reference_data(seed: int = 0) -> np.ndarray:
    # a stable process: torque centered at 10.0 with small variation
    return np.random.default_rng(seed).normal(10.0, 0.05, 200)


def _todays_data(seed: int = 1) -> np.ndarray:
    # the tool warmed up fine, then drifted up in the second half of the shift
    rng = np.random.default_rng(seed)
    steady = rng.normal(10.0, 0.05, 30)
    drift = 10.0 + np.linspace(0.0, 0.25, 30) + rng.normal(0.0, 0.05, 30)
    return np.concatenate([steady, drift])


def main(outdir: str | Path = ".") -> int:
    baseline_path = Path(outdir) / "torque_baseline.json"

    # Phase I: fit limits from the reference period and freeze them.
    sw.imr(_reference_data(), rules="nelson").baseline.save(baseline_path)

    # Phase II: judge today's data against the frozen limits.
    r = sw.imr(_todays_data(), rules="nelson", limits=baseline_path)

    print(r.summary())
    if not r.ok:
        first = r.signals[0]
        print(f"\nfirst signal: {first}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
