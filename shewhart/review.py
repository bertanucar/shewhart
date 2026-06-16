"""One-call review: select the chart, check the assumptions, return a verdict.

review() is pure composition. It never computes a statistic of its own:
every number in the verdict comes from the validated chart and capability
functions, and the selection logic is a small set of documented conventions
(Montgomery subgroup-size cutoffs, Laney's sigma_z, the AIAG subgroup-count
guidance). The agent interprets; this module only decides which validated
call to make and assembles the result into one structured, JSON-safe object.

Verdict contract (frozen from 0.1.1 on, append-only forever):

    ok          True iff failures is empty - the gate
    failures    machine-readable causes: "out_of_control",
                "capability_marginal", "capability_inadequate",
                "capability_error", "check:<name>"
    headline    a short deterministic plain-language verdict
    selection   which chart and why
    control     status, stats and signals of the underlying chart
    capability  always present; status "not_assessed" carries a reason code
    checks      assumption checks; numeric fields are finite or null
    params      echo of the call, with limits as "fitted" | "frozen"

The check set and every enum are open: later versions may add checks (which
can tighten the gate) and enum values. Consumers should treat unknown values
conservatively and pin the library version where bit-stable gates matter.
"""

from __future__ import annotations

import dataclasses
import math
import pathlib
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ._data import as_series, time_subgroups
from ._result import Baseline, Result, _jsonable
from ._version import __version__
from .capability import capability
from .charts import (
    c_chart,
    imr,
    laney_p,
    laney_u,
    np_chart,
    p_chart,
    u_chart,
    xbar_r,
    xbar_s,
)

_SCHEMA = 1

# Documented conventions, not fitted tests; see docs/guides/review.md.
_SUBGROUPS_FAIL = 10  # fewer Phase I subgroups than this: no credible limits
_SUBGROUPS_WARN = 25  # AIAG guidance for establishing control limits
_XBAR_S_FROM = 9  # subgroup size at which S replaces R (Montgomery)
_SIGMA_Z_HIGH = 1.5  # Laney: sigma_z near 1 means the classic chart is fine
_SIGMA_Z_LOW = 1.0 / 1.5
_AUTOCORR_WARN = 0.5  # |lag-1 r| above this: limits assume too much
_CAPABLE = 4.0 / 3.0  # cpk thresholds: industry convention
_MARGINAL = 1.0

_VARIABLES = ("imr", "xbar_r", "xbar_s")
_DEFECTIVES = ("p_chart", "np_chart", "laney_p")
_DEFECTS = ("c_chart", "u_chart", "laney_u")

_CHARTS = {
    "imr": imr, "xbar_r": xbar_r, "xbar_s": xbar_s,
    "p_chart": p_chart, "np_chart": np_chart, "laney_p": laney_p,
    "c_chart": c_chart, "u_chart": u_chart, "laney_u": laney_u,
}


@dataclasses.dataclass(frozen=True)
class Check:
    """One assumption check: pass, warn, or fail (fail gates the verdict)."""

    name: str
    status: str
    value: float | None
    threshold: float | None
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "value": _finite(self.value),
            "threshold": _finite(self.threshold),
            "note": self.note,
        }

    def __str__(self) -> str:
        v = "n/a" if self.value is None or not math.isfinite(self.value) else f"{self.value:.4g}"
        return f"{self.name}: {self.status} (value {v})" + (f" - {self.note}" if self.note else "")


@dataclasses.dataclass(frozen=True)
class Review:
    """The composite verdict; every part is also available for drill-down."""

    headline: str
    failures: tuple[str, ...]
    selection: Mapping[str, str]
    params: Mapping[str, Any]
    chart: Result
    capability: Result | None
    capability_block: Mapping[str, Any]
    checks: tuple[Check, ...]
    recommendations: tuple[Mapping[str, Any], ...]
    meta: Mapping[str, Any]

    @property
    def ok(self) -> bool:
        """True iff nothing gates: in control, capable (or no specs), no check failed."""
        return len(self.failures) == 0

    @property
    def control_status(self) -> str:
        return "in_control" if self.chart.ok else "out_of_control"

    @property
    def capability_status(self) -> str:
        return str(self.capability_block["status"])

    @property
    def baseline(self) -> Baseline | None:
        """The chart's baseline: review(df_hist, ...).baseline.save(path)."""
        return self.chart.baseline

    def to_dict(self) -> dict:
        table = self.chart.table
        signals = []
        for s in self.chart.signals:
            d = s.to_dict()
            d["labels"] = [str(table.index[p]) for p in s.points if p < len(table)]
            signals.append(d)
        return {
            "schema": _SCHEMA,
            "method": "review",
            "ok": self.ok,
            "failures": list(self.failures),
            "headline": self.headline,
            "params": _jsonable(self.params),
            "selection": dict(self.selection),
            "control": {
                "status": self.control_status,
                "chart": self.chart.method,
                "stats": _jsonable(self.chart.stats),
                "signals": signals,
            },
            "capability": _jsonable(self.capability_block),
            "checks": [c.to_dict() for c in self.checks],
            "recommendations": [dict(r) for r in self.recommendations],
            "baseline": {
                "chart": self.chart.baseline.chart,
                "n": self.chart.baseline.n,
                "created_at": self.chart.baseline.created_at,
                "version": self.chart.baseline.version,
            } if self.chart.baseline is not None else None,
            "meta": _jsonable(self.meta),
        }

    def summary(self) -> str:
        lines = [
            f"shewhart review - v{self.meta.get('version', '?')}",
            f"  verdict: {'OK' if self.ok else 'NOT OK'} - {self.headline}",
            f"  chart: {self.selection['chart']} - {self.selection['reason']}",
        ]
        for c in self.checks:
            lines.append(f"  check {c}")
        for r in self.recommendations:
            lines.append(f"  recommend [{r['code']}]: {r['message']}")
        return "\n".join(lines) + "\n" + self.chart.summary()

    def plot(self, ax=None):
        return self.chart.plot(ax=ax)

    def to_html(self, path=None, *, title: str | None = None):
        from ._report import report

        results = [self.chart] + ([self.capability] if self.capability else [])
        return report(results, path, title=title or self.headline)

    def _repr_html_(self) -> str:
        return f"<pre>{self.summary()}</pre>"


def _finite(v) -> float | None:
    if v is None:
        return None
    v = float(v)
    return v if math.isfinite(v) else None


def _spec_bounds(lsl, usl):
    return (-math.inf if lsl is None else lsl, math.inf if usl is None else usl)


def _dropped(data: Any, column: str | None, extra: Any = None) -> int:
    if isinstance(data, pd.DataFrame) and column is not None and column in data.columns:
        mask = np.asarray(data[column].isna())
        if isinstance(extra, str) and extra in data.columns:
            mask = mask | np.asarray(data[extra].isna())
        return int(mask.sum())
    if isinstance(data, pd.Series):
        return int(data.isna().sum())
    return int(pd.isna(np.asarray(data, dtype="float64")).sum()) if not isinstance(data, pd.DataFrame) else 0


def _load_baseline(limits: Any) -> Baseline:
    if isinstance(limits, (str, pathlib.Path)):
        return Baseline.load(limits)
    if isinstance(limits, Baseline):
        return limits
    raise TypeError(
        "review(limits=...) needs a Baseline or a path to a baseline JSON, "
        f"got {type(limits).__name__}. Plain mappings lack the chart name "
        "review dispatches on; pass them to the chart function directly, "
        'e.g. sw.imr(df, value="x", limits={...}).'
    )


def _subgroup_size(data: Any, value: str, subgroup: Any) -> int:
    """The unique subgroup size, or 0 when sizes vary (routed to xbar_s).

    Teaching errors stay review-attributed.
    """
    time_labels = time_subgroups(data, subgroup)
    if time_labels is not None:
        labels = time_labels
    elif isinstance(data, pd.DataFrame) and subgroup in data.columns:
        labels = data[subgroup]
    else:
        cols = list(data.columns) if isinstance(data, pd.DataFrame) else []
        raise ValueError(
            f"review(): subgroup={subgroup!r} is not a column (or, with a "
            f'DatetimeIndex, a fixed time window like "1H"). Columns: {cols}. '
            'Example: sw.review(df, value="torque", subgroup="batch")'
        )
    frame = pd.DataFrame({"v": data[value], "g": labels}).dropna()
    sizes = sorted(set(frame.groupby("g", sort=False).size()))
    if not sizes:
        raise ValueError(
            f"review(): no usable rows; every value in {value!r} (or its "
            f"subgroup label) is missing."
        )
    if len(sizes) > 1:
        return 0  # variable sizes -> xbar_s (stair-step limits)
    return int(sizes[0])


def _run_chart(name: str, *args, **kwargs) -> Result:
    try:
        return _CHARTS[name](*args, **kwargs)
    except (TypeError, ValueError) as e:
        raise type(e)(f"review() dispatched to {name}(), which reports: {e}") from None


def _sigma_z_probe(fn, data, **kwargs) -> tuple[Result | None, float | None]:
    """Fit the Laney variant for sigma_z; None when not estimable."""
    try:
        r = fn(data, **kwargs)
    except ValueError:
        return None, None
    sz = float(r.stats["sigma_z"])
    return r, (sz if math.isfinite(sz) and sz > 0 else None)


def review(
    data: Any,
    *,
    value: str | None = None,
    subgroup: Any = None,
    defectives: str | None = None,
    defects: str | None = None,
    size: Any = None,
    lsl: float | None = None,
    usl: float | None = None,
    target: float | None = None,
    rules: str | None = "nelson",
    limits: Any = None,
) -> Review:
    """Select the right chart, check the assumptions, return one verdict.

    Phase I (fit limits from this data)::

        rv = sw.review(df, value="torque", lsl=9.95, usl=10.05)
        rv.ok                      # the gate: stable and capable
        rv.to_dict()               # the structured verdict, JSON-safe
        rv.baseline.save("line3_baseline.json")

    Phase II (judge new data against the frozen baseline)::

        import sys
        rv = sw.review(df_new, value="torque", limits="line3_baseline.json")
        sys.exit(0 if rv.ok else 1)

    Exactly one of value= (measurements), defectives= (rejected units, with
    size=), or defects= (defect counts, size= optional) selects the branch;
    the decision tree is documented in the review guide. review() composes
    the validated chart and capability functions and never computes its own
    statistics.
    """
    given = {"value": value, "defectives": defectives, "defects": defects}
    named = [k for k, v in given.items() if v is not None]
    if len(named) > 1 or (not named and isinstance(data, pd.DataFrame)):
        raise ValueError(
            "review() needs exactly one of value= (measurements), "
            "defectives= (rejected units per period, with size=), or "
            "defects= (defect counts per period). "
            f"Got: {named or 'a DataFrame and none of them'}."
        )
    branch = named[0] if named else "value"  # bare Series/array: measurements
    specs = lsl is not None or usl is not None
    if branch != "value" and (specs or target is not None):
        raise ValueError(
            "Specification limits apply to measurements (value=); "
            "attribute charts judge counts. Drop lsl=/usl=/target=, or "
            "pass the underlying measurement as value=."
        )
    if branch == "value" and size is not None:
        raise ValueError(
            "size= belongs to the attribute charts; for subgrouped "
            'measurements use subgroup=. Example: sw.review(df, value="x", '
            'subgroup="batch")'
        )
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError(f"lsl must be below usl, got lsl={lsl}, usl={usl}.")
    if branch != "value" and rules not in ("nelson", "none", None):
        raise ValueError(
            f'Attribute charts support rules="nelson" or rules="none", got '
            f'{rules!r}; the zone tests need variables data. '
            'Example: sw.review(df, defectives="rejects", size="inspected")'
        )

    baseline_in = _load_baseline(limits) if limits is not None else None
    if baseline_in is not None:
        family = (
            "value" if baseline_in.chart in _VARIABLES
            else "defectives" if baseline_in.chart in _DEFECTIVES
            else "defects" if baseline_in.chart in _DEFECTS
            else None
        )
        if family is None:
            raise ValueError(
                f"review() dispatches the Shewhart-family charts; this "
                f"baseline was fitted for {baseline_in.chart!r}. Evaluate it "
                f"directly: sw.{baseline_in.chart}(df, ..., limits=...)."
            )
        if family != branch:
            raise ValueError(
                f"This baseline was fitted for {baseline_in.chart!r}, which "
                f"takes {family}=, but the call passes {branch}=. Use the "
                "matching data, or refit: sw.review(df_hist, ...).baseline"
            )

    checks: list[Check] = []
    recs: list[dict] = []
    selection: dict[str, str]

    # -- dispatch -------------------------------------------------------------
    if branch == "value":
        s = as_series(data, value, "review")
        x = s.to_numpy()
        n_dropped = _dropped(data, value, subgroup)

        if baseline_in is not None:
            chart_name = baseline_in.chart
            if chart_name == "imr" and subgroup is not None:
                raise ValueError(
                    "This baseline charts individuals (imr); drop subgroup=, "
                    "or refit on subgrouped data: sw.review(df_hist, "
                    'value="x", subgroup="batch").baseline'
                )
            selection = {"chart": chart_name, "reason": "from frozen baseline (Phase II)"}
            kwargs = {"value": value, "rules": rules, "limits": baseline_in}
            if chart_name in ("xbar_r", "xbar_s"):
                kwargs["subgroup"] = subgroup
            chart = _run_chart(chart_name, data, **kwargs)
        elif subgroup is None:
            selection = {"chart": "imr", "reason": "individual measurements (no subgroup=)"}
            chart = _run_chart("imr", data, value=value, rules=rules)
        else:
            n_sub = _subgroup_size(data, value, subgroup)
            if n_sub == 0:
                selection = {"chart": "xbar_s", "reason": "variable subgroup sizes -> Xbar-S"}
                chart = _run_chart("xbar_s", data, value=value, subgroup=subgroup, rules=rules)
            elif n_sub == 1:
                selection = {"chart": "imr", "reason": "subgroups of size 1 are individuals"}
                chart = _run_chart("imr", data, value=value, rules=rules)
            elif n_sub < _XBAR_S_FROM:
                selection = {"chart": "xbar_r", "reason": f"subgroup size {n_sub} (2-8 -> Xbar-R)"}
                chart = _run_chart("xbar_r", data, value=value, subgroup=subgroup, rules=rules)
            else:
                selection = {"chart": "xbar_s", "reason": f"subgroup size {n_sub} (>=9 -> Xbar-S)"}
                chart = _run_chart("xbar_s", data, value=value, subgroup=subgroup, rules=rules)

        checks += _variables_checks(x, chart, lsl, usl, target, recs)
    else:
        chart, selection, sz = _attribute_dispatch(
            data, branch, defectives, defects, size, rules, baseline_in, recs
        )
        n_dropped = _dropped(data, defectives or defects)
        if sz is not None or selection.get("_sz_attempted"):
            triggered = sz is not None and not (_SIGMA_Z_LOW < sz < _SIGMA_Z_HIGH)
            in_classic = chart.method in ("p_chart", "np_chart", "c_chart", "u_chart")
            status = "warn" if (triggered and in_classic) else "pass"
            note = (
                "sigma_z not estimable (no variation in the standardized points)"
                if sz is None
                else f"sigma_z = {sz:.3g}; " + (
                    "Laney limits in use" if not in_classic
                    else "over/underdispersion relative to the classic model"
                    if triggered else "consistent with the classic chart (Laney 2002)"
                )
            )
            threshold = None if sz is None else (
                _SIGMA_Z_LOW if sz <= _SIGMA_Z_LOW else _SIGMA_Z_HIGH
            )
            checks.append(Check("overdispersion", status, sz, threshold, note))
        selection.pop("_sz_attempted", None)

    # -- checks that depend on the fitted chart -------------------------------
    if baseline_in is None:
        k = int(chart.meta["n"])
        if k < _SUBGROUPS_FAIL:
            checks.insert(0, Check(
                "sample_size", "fail", float(k), float(_SUBGROUPS_FAIL),
                f"{k} subgroups cannot support Phase I limits; collect at least {_SUBGROUPS_FAIL}.",
            ))
        elif k < _SUBGROUPS_WARN:
            checks.insert(0, Check(
                "sample_size", "warn", float(k), float(_SUBGROUPS_WARN),
                f"{k} subgroups; AIAG advises {_SUBGROUPS_WARN} for established limits.",
            ))
        else:
            checks.insert(0, Check("sample_size", "pass", float(k), float(_SUBGROUPS_WARN), ""))
        if any(c.name == "sample_size" and c.status != "pass" for c in checks):
            recs.append({
                "code": "collect_more_subgroups",
                "message": f"Phase I limits rest on {k} subgroups; they firm up at {_SUBGROUPS_WARN}.",
                "call": None,
            })

    # -- capability -----------------------------------------------------------
    cap_result, cap_block = _capability_verdict(
        data, value, subgroup, lsl, usl, target, specs, chart, checks, recs
    )

    if n_dropped > 0:
        recs.append({
            "code": "missing_values_excluded",
            "message": f"{n_dropped} row(s) with missing values were excluded before analysis.",
            "call": None,
        })
    if not chart.ok:
        recs.insert(0, {
            "code": "investigate_signals",
            "message": f"{len(chart.signals)} rule violation(s); find the causes before acting on capability or limits.",
            "call": None,
        })

    failures = _failures(chart, cap_block, checks)
    headline = _headline(chart, cap_block, failures)

    table = chart.table
    meta = dict(chart.meta)
    meta["n_dropped"] = n_dropped
    meta["index_start"] = str(table.index[0]) if len(table) else None
    meta["index_end"] = str(table.index[-1]) if len(table) else None

    params = {
        "value": value, "subgroup": subgroup, "defectives": defectives,
        "defects": defects, "size": size, "lsl": lsl, "usl": usl,
        "target": target, "rules": rules,
        "limits": "frozen" if baseline_in is not None else "fitted",
    }
    return Review(
        headline=headline,
        failures=tuple(failures),
        selection=selection,
        params=params,
        chart=chart,
        capability=cap_result,
        capability_block=cap_block,
        checks=tuple(checks),
        recommendations=tuple(recs),
        meta=meta,
    )


def _attribute_dispatch(data, branch, defectives, defects, size, rules, baseline_in, recs):
    """Choose among p/np/laney_p and c/u/laney_u; return (chart, selection, sigma_z)."""
    if branch == "defectives" and size is None:
        raise ValueError(
            "review(defectives=...) needs size= (units inspected per "
            "period). If these are defect counts without an inspection "
            "size, pass them as defects= instead (c chart). "
            'Example: sw.review(df, defectives="rejects", size="inspected")'
        )

    if baseline_in is not None:
        name = baseline_in.chart
        if name == "c_chart" and size is not None:
            raise ValueError(
                "This baseline is a c chart (constant opportunity); drop "
                "size=, or refit for rates: sw.review(df_hist, "
                'defects="x", size="area").baseline'
            )
        kwargs = {"rules": rules, "limits": baseline_in}
        if branch == "defectives":
            kwargs.update(defectives=defectives, size=size)
        else:
            kwargs.update(defects=defects)
            if name in ("u_chart", "laney_u"):
                kwargs["size"] = size
        chart = _run_chart(name, data, **kwargs)
        selection = {"chart": name, "reason": "from frozen baseline (Phase II)",
                     "_sz_attempted": True}
        sz = None
        if name in ("p_chart", "np_chart"):
            _, sz = _sigma_z_probe(laney_p, data, defectives=defectives, size=size, rules="none")
        elif name == "u_chart":
            _, sz = _sigma_z_probe(laney_u, data, defects=defects, size=size, rules="none")
        elif name == "c_chart":
            _, sz = _sigma_z_probe(laney_u, data, defects=defects, size=1, rules="none")
        else:  # laney baselines carry their frozen sigma_z
            sz = float(chart.stats["sigma_z"])
        return chart, selection, sz

    if branch == "defectives":
        if (
            isinstance(data, pd.DataFrame)
            and defectives in data.columns
            and (
                (isinstance(size, str) and size in data.columns
                 and (data[defectives] > data[size]).any())
                or (np.ndim(size) == 0 and not isinstance(size, str)
                    and (data[defectives] > size).any())
            )
        ):
            raise ValueError(
                "review(): defectives exceed size in at least one period; "
                "defectives counts units, not defects. If a unit can carry "
                "several findings, pass them as defects= instead."
            )
        probe, sz = _sigma_z_probe(laney_p, data, defectives=defectives, size=size, rules=rules)
        if sz is not None and not (_SIGMA_Z_LOW < sz < _SIGMA_Z_HIGH):
            return probe, {
                "chart": "laney_p",
                "reason": f"sigma_z = {sz:.3g} outside [{_SIGMA_Z_LOW:.3g}, {_SIGMA_Z_HIGH}]: "
                          "Laney p' adjusts for over/underdispersion",
                "_sz_attempted": True,
            }, sz
        try:
            arr = np.asarray(
                data[size] if isinstance(data, pd.DataFrame)
                and isinstance(size, str) and size in data.columns else size,
                dtype="float64",
            )
            constant = arr.ndim == 0 or (arr.size > 0 and np.all(arr == arr.flat[0]))
        except (TypeError, ValueError):
            constant = False
        name = "np_chart" if constant else "p_chart"
        reason = (
            "defective counts, constant subgroup size -> np chart"
            if constant else "defective counts, varying subgroup sizes -> p chart"
        )
        chart = _run_chart(name, data, defectives=defectives, size=size, rules=rules)
        return chart, {"chart": name, "reason": reason, "_sz_attempted": True}, sz

    if size is not None:
        probe, sz = _sigma_z_probe(laney_u, data, defects=defects, size=size, rules=rules)
        if sz is not None and not (_SIGMA_Z_LOW < sz < _SIGMA_Z_HIGH):
            return probe, {
                "chart": "laney_u",
                "reason": f"sigma_z = {sz:.3g} outside [{_SIGMA_Z_LOW:.3g}, {_SIGMA_Z_HIGH}]: "
                          "Laney u' adjusts for over/underdispersion",
                "_sz_attempted": True,
            }, sz
        chart = _run_chart("u_chart", data, defects=defects, size=size, rules=rules)
        return chart, {"chart": "u_chart", "reason": "defect rates per inspection size",
                       "_sz_attempted": True}, sz

    chart = _run_chart("c_chart", data, defects=defects, rules=rules)
    _, sz = _sigma_z_probe(laney_u, data, defects=defects, size=1, rules="none")
    if sz is not None and not (_SIGMA_Z_LOW < sz < _SIGMA_Z_HIGH):
        recs.append({
            "code": "consider_laney",
            "message": f"sigma_z = {sz:.3g}: defect counts are over/underdispersed "
                       "relative to the Poisson model behind the c chart.",
            "call": f'sw.laney_u(df, defects="{defects}", size=1)',
        })
    return chart, {"chart": "c_chart", "reason": "defect counts, constant area of opportunity",
                   "_sz_attempted": True}, sz


def _variables_checks(x, chart, lsl, usl, target, recs) -> list[Check]:
    from scipy import stats as sps

    checks: list[Check] = []
    spread = float(np.ptp(x)) if len(x) else 0.0
    if spread == 0.0:
        checks.append(Check(
            "variation", "fail", 0.0, 0.0,
            f"all {len(x)} values are identical; check measurement resolution and sensor health.",
        ))
        return checks  # AD, autocorrelation, and specs are meaningless on a flat line

    if len(x) >= 8:
        ad = sps.anderson(x, dist="norm")
        crit5 = float(ad.critical_values[2])
        stat = float(ad.statistic)
        if math.isfinite(stat):
            if chart.method == "imr":
                note = (
                    "normality rejected at 5%; the I chart's false-alarm rate "
                    "inflates under non-normality (Borror, Montgomery & Runger 1999)."
                    if stat > crit5 else "Anderson-Darling, 5% level"
                )
            else:
                note = (
                    "normality rejected at 5% on the raw values; subgroup "
                    "means are CLT-robust, capability is where it matters."
                    if stat > crit5 else "Anderson-Darling, 5% level"
                )
            checks.append(Check(
                "normality", "warn" if stat > crit5 else "pass", stat, crit5, note,
            ))

    if chart.method == "imr" and len(x) >= 20:
        r1 = float(np.corrcoef(x[:-1], x[1:])[0, 1])
        if math.isfinite(r1):
            if abs(r1) > _AUTOCORR_WARN:
                checks.append(Check(
                    "autocorrelation", "warn", r1, _AUTOCORR_WARN,
                    "control limits assume independent observations.",
                ))
                recs.append({
                    "code": "model_autocorrelation",
                    "message": f"lag-1 autocorrelation r1 = {r1:.2f}: widen the sampling "
                               "interval, or model the dynamics and chart the residuals; "
                               "a plain EWMA does not fix this.",
                    "call": None,
                })
            else:
                checks.append(Check("autocorrelation", "pass", r1, _AUTOCORR_WARN, ""))

    uniques = np.unique(x)
    if len(uniques) == 2 and set(uniques) <= {0.0, 1.0}:
        checks.append(Check(
            "binary_data", "warn", None, None,
            "values are 0/1; pass/fail data belongs on an attribute chart.",
        ))
        recs.append({
            "code": "use_attribute_chart",
            "message": "0/1 measurements are pass/fail outcomes; chart the rate, not the bits.",
            "call": 'sw.review(df_counts, defectives="rejects", size="inspected")',
        })

    if lsl is not None or usl is not None:
        lo, hi = _spec_bounds(lsl, usl)
        share = float(np.mean((x >= lo) & (x <= hi)))
        checks.append(Check(
            "spec_plausibility", "warn" if share == 0.0 else "pass", share, 0.0,
            "no observation inside the specification limits; check units and entries."
            if share == 0.0 else "share of observations inside the specification limits",
        ))
        if share == 0.0:
            recs.append({
                "code": "check_spec_units",
                "message": "Data and specification limits do not overlap at all; a unit "
                           "or typing error is far more likely than 100% scrap.",
                "call": None,
            })
        if target is not None and not (lo <= target <= hi):
            checks.append(Check(
                "target_within_specs", "warn", float(target),
                float(lo if target < lo else hi),
                "target lies outside the specification limits.",
            ))
    return checks


def _capability_verdict(data, value, subgroup, lsl, usl, target, specs, chart, checks, recs):
    """Return (Result | None, the capability block of the verdict)."""
    def block(status, *, index=None, index_value=None, reason=None, detail=None, stats=None):
        return {
            "status": status, "index": index, "index_value": _finite(index_value),
            "reason": reason, "detail": detail, "stats": stats or {},
        }

    if not specs:
        return None, block("not_assessed", reason="no_spec_limits")
    if not chart.ok:
        return None, block(
            "not_assessed", reason="not_in_control",
            detail="capability indices on an unstable process are not meaningful; "
                   "remove the special causes first.",
        )
    if any(c.name == "variation" and c.status == "fail" for c in checks):
        return None, block(
            "not_assessed", reason="no_variation",
            detail="the data has no variation; no capability index is defined.",
        )

    x = as_series(data, value, "review").to_numpy()
    ad_warn = any(c.name == "normality" and c.status == "warn" for c in checks)
    use_auto = ad_warn and subgroup is None and len(x) >= 10 and bool(np.all(x > 0))
    try:
        cap = capability(
            data, value=value, lsl=lsl, usl=usl, target=target,
            subgroup=subgroup, dist="auto" if use_auto else "normal",
        )
    except ValueError as e:
        return None, block("not_assessed", reason="error", detail=str(e))
    if ad_warn and not use_auto:
        recs.append({
            "code": "nonnormal_capability",
            "message": "normality is rejected but the percentile method is unavailable "
                       "here (subgrouped data, n < 10, or non-positive values); "
                       "normal-theory indices reported, interpret tail estimates with care.",
            "call": None,
        })

    if cap.signals:
        checks.append(Check(
            "stability", "fail", float(len(cap.signals[0].points)), 0.0,
            cap.signals[0].note or "observations beyond 3 sigma of the mean.",
        ))
        return cap, block(
            "not_assessed", reason="unstable",
            detail="the capability stability gate flagged observations beyond "
                   "3 sigma; indices are withheld.",
        )

    index = "cpk" if "cpk" in cap.stats else "ppk" if "ppk" in cap.stats else None
    if index is None:
        return cap, block("not_assessed", reason="error",
                          detail="no capability index in the result; one-sided "
                                 "specification without a matching tail.")
    val = float(cap.stats[index])
    status = "capable" if val >= _CAPABLE else "marginal" if val >= _MARGINAL else "inadequate"
    if status == "marginal":
        recs.append({
            "code": "review_capability_ci",
            "message": f"{index} = {val:.2f} sits between 1.00 and 1.33; judge the "
                       f"confidence interval in capability.stats, not the point estimate.",
            "call": None,
        })
    if int(cap.meta["n"]) < 30:
        recs.append({
            "code": "capability_estimate_noisy",
            "message": f"{index} from n = {cap.meta['n']} is a noisy point estimate; "
                       f"for a conservative gate read {index}_lci.",
            "call": None,
        })
    return cap, block(status, index=index, index_value=val,
                      stats=_jsonable(cap.stats))


def _failures(chart, cap_block, checks) -> list[str]:
    failures = []
    if not chart.ok:
        failures.append("out_of_control")
    if cap_block["status"] == "marginal":
        failures.append("capability_marginal")
    elif cap_block["status"] == "inadequate":
        failures.append("capability_inadequate")
    elif cap_block["reason"] == "error":
        failures.append("capability_error")
    failures += [f"check:{c.name}" for c in checks if c.status == "fail"]
    return failures


def _headline(chart, cap_block, failures) -> str:
    if chart.ok:
        head = f"In control: no rule violations on the {chart.method} chart."
    else:
        head = (
            f"Out of control: {len(chart.signals)} signal(s) on the "
            f"{chart.method} chart."
        )
    status = cap_block["status"]
    if status in ("capable", "marginal", "inadequate"):
        head += f" {cap_block['index'].capitalize()} {cap_block['index_value']:.2f} ({status})."
    elif cap_block["reason"] not in (None, "no_spec_limits"):
        head += f" Capability not assessed ({cap_block['reason'].replace('_', ' ')})."
    hard = [f for f in failures if f.startswith("check:")]
    if hard:
        head += " Failed checks: " + ", ".join(f.split(":", 1)[1] for f in hard) + "."
    return head
