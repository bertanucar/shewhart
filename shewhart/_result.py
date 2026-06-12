"""The Result protocol: the one object every shewhart analysis returns.

Design contract (frozen from v0.1 on, append-only forever):

    Result.method    stable analysis alias ("imr", "xbar_r", ...)
    Result.params    echo of the user's inputs
    Result.stats     named scalars (centers, limits, indices)
    Result.signals   tuple of structured rule-violation events; empty == in control
    Result.meta      provenance: n, version, input hash, timestamp, source
    Result.baseline  the frozen/fitted Baseline behind the verdict

    r.ok             True iff no signals  ->  sys.exit(0 if r.ok else 1)
    r.summary()      fixed-width audit text with a plain-language verdict
    r.table          tidy per-point DataFrame (defensive copy)
    r.to_dict()      JSON-safe, integer-versioned schema
    r.plot(ax=None)  matplotlib rendering (statistics and presentation stay separate)
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import pathlib
from typing import Any, Mapping

import numpy as np
import pandas as pd

_SCHEMA = 1


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def data_hash(values: np.ndarray) -> str:
    return "sha256:" + hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()[:16]


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, Mapping):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    return str(obj)


@dataclasses.dataclass(frozen=True)
class Signal:
    """One rule violation: which rule, on which chart, at which points."""

    rule: str
    chart: str
    points: tuple[int, ...]
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "chart": self.chart,
            "points": list(self.points),
            "note": self.note,
        }

    def __str__(self) -> str:
        if not self.points:
            pts = ""
        elif len(self.points) == 1:
            pts = f": point {self.points[0]}"
        else:
            pts = f": points {self.points[0]}-{self.points[-1]}"
        return f"{self.rule} ({self.chart}){pts}" + (f" - {self.note}" if self.note else "")


@dataclasses.dataclass(frozen=True)
class Baseline:
    """Frozen Phase-I parameters: fit once, commit to git, evaluate forever."""

    chart: str
    stats: Mapping[str, float]
    n: int
    created_at: str
    version: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema": _SCHEMA,
                "chart": self.chart,
                "stats": _jsonable(self.stats),
                "n": self.n,
                "created_at": self.created_at,
                "shewhart_version": self.version,
            },
            indent=2,
        )

    def save(self, path: str | pathlib.Path) -> pathlib.Path:
        path = pathlib.Path(path)
        path.write_text(self.to_json() + "\n", encoding="utf-8")
        return path

    @classmethod
    def from_json(cls, text: str) -> "Baseline":
        raw = json.loads(text)
        if int(raw.get("schema", 1)) > _SCHEMA:
            raise ValueError(
                f"This baseline uses schema {raw['schema']}, written by "
                f"shewhart {raw.get('shewhart_version', '?')}; this version "
                f"reads up to schema {_SCHEMA}. Upgrade shewhart to load it."
            )
        return cls(
            chart=raw["chart"],
            stats=dict(raw["stats"]),
            n=int(raw["n"]),
            created_at=raw["created_at"],
            version=raw["shewhart_version"],
        )

    @classmethod
    def load(cls, path: str | pathlib.Path) -> "Baseline":
        return cls.from_json(pathlib.Path(path).read_text(encoding="utf-8"))


@dataclasses.dataclass(frozen=True)
class Result:
    method: str
    params: Mapping[str, Any]
    stats: Mapping[str, float]
    signals: tuple[Signal, ...]
    meta: Mapping[str, Any]
    baseline: "Baseline | None" = None
    _table: pd.DataFrame = dataclasses.field(default=None, repr=False, compare=False)

    # -- verdict ------------------------------------------------------------
    @property
    def ok(self) -> bool:
        """True iff no rule violations - the cron exit-code primitive."""
        return len(self.signals) == 0

    # -- views --------------------------------------------------------------
    @property
    def table(self) -> pd.DataFrame:
        """Tidy per-point table (defensive copy: results are immutable)."""
        return self._table.copy()

    def to_frame(self) -> pd.DataFrame:
        return self.table

    def to_dict(self) -> dict:
        return {
            "schema": _SCHEMA,
            "method": self.method,
            "params": _jsonable(self.params),
            "stats": _jsonable(self.stats),
            "signals": [s.to_dict() for s in self.signals],
            "meta": _jsonable(self.meta),
        }

    def summary(self) -> str:
        stats = "  ".join(f"{k}={_fmt(v)}" for k, v in self.stats.items())
        head = (
            f"shewhart {self.method} - n={self.meta.get('n', '?')}"
            f" - rules={self.params.get('rules')}"
            f" - {self.meta.get('source', '')} - v{self.meta.get('version', '?')}"
        )
        if self.ok:
            verdict = "verdict: IN CONTROL - no rule violations."
        else:
            lines = "\n".join(f"  - {s}" for s in self.signals)
            verdict = (
                f"verdict: OUT OF CONTROL - {len(self.signals)} signal(s):\n{lines}"
            )
        return f"{head}\n  {stats}\n{verdict}"

    def plot(self, ax=None):
        from . import _plot

        return _plot.render(self, ax=ax)

    def to_html(self, path=None, *, title: str | None = None):
        """Self-contained HTML report; returns the HTML string, or writes
        to ``path`` and returns the Path. Works headless (cron, CI)."""
        from . import _report

        return _report.result_to_html(self, path, title=title)

    def _repr_html_(self) -> str:
        body = self.summary().replace("\n", "<br>")
        return f"<pre>{body}</pre>"


def _fmt(v: float) -> str:
    return f"{v:.4g}" if isinstance(v, (int, float, np.floating)) else str(v)
