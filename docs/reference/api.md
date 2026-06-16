# API and grammar

This page is the complete public surface of shewhart. It is deliberately
small, and it is **frozen**: from 0.1 on, no public name, signature, default
value, or string alias is removed or changes meaning within a major version.
Renames, if ever, keep permanent aliases. Defaults never change silently,
because changed defaults change numbers, and this is an audit tool.

One import, everywhere:

```python
import shewhart as sw
```

## Control charts

| Call | Chart | Notes |
|------|-------|-------|
| `sw.imr(data, value=, rules=, limits=)` | Individuals & moving range | the default chart for n=1 data |
| `sw.xbar_r(df, value=, subgroup=, rules=, limits=)` | Xbar-R | subgrouped, limits from R-bar |
| `sw.xbar_s(df, value=, subgroup=, rules=, limits=)` | Xbar-S | subgrouped, limits from S-bar |
| `sw.p_chart(df, defectives=, size=, rules=, limits=)` | p | varying sizes, stair-step limits |
| `sw.np_chart(df, defectives=, size=, rules=, limits=)` | np | constant size |
| `sw.c_chart(data, defects=, rules=, limits=)` | c | counts per unit |
| `sw.u_chart(df, defects=, size=, rules=, limits=)` | u | rates, varying sizes |
| `sw.ewma(data, value=, lam=, k=, center=, sigma=, asymptotic=, limits=)` | EWMA | exact limits by default |
| `sw.run_chart(data, value=, alpha=)` | run chart | four runs tests |
| `sw.pareto(data, by=, weights=)` | Pareto analysis | counts or weighted (e.g. cost) |
| `sw.cusum(data, value=, k=, h=, center=, sigma=, limits=)` | tabular CUSUM | decision interval, no run rules |
| `sw.laney_p(df, defectives=, size=, rules=, limits=)` | Laney p' | overdispersion-robust, reports sigma_z |
| `sw.laney_u(df, defects=, size=, rules=, limits=)` | Laney u' | overdispersion-robust rates |

## Analyses

| Call | Analysis | Notes |
|------|----------|-------|
| `sw.review(data, value=\|defectives=\|defects=, subgroup=, size=, lsl=, usl=, target=, rules=, limits=)` | one-call review | selects the chart, checks assumptions, returns a [Review](#the-review-verdict) |
| `sw.capability(data, value=, lsl=, usl=, target=, subgroup=, confidence=, dist=, transform=)` | Cp/Cpk/Pp/Ppk/Cpm with confidence intervals | non-normal via `dist=` (percentile method) or `transform="boxcox"` |
| `sw.gauge_rr(...)` | ANOVA gauge R&R (AIAG) | *planned (0.2)* |
| `sw.type1(...)` | Type 1 gauge study (Cg/Cgk) | *planned (0.2)* |
| `sw.attribute_agreement(...)` | attribute agreement (kappa) | *planned (0.2)* |
| `sw.tolerance_interval(data, value=, coverage=, confidence=, method=)` | tolerance intervals | normal (Howe k2) and nonparametric (Wilks) |
| `sw.screen(...)` | fleet screening over many characteristics | *planned (0.3)* |
| `sw.monitor(...)` | drift monitoring with chart semantics | *planned (0.3)* |

Planned names are part of the frozen grammar: they will appear exactly as
written here.

## Everything returns a Result

```python
r.ok          # bool: no signals; use as exit code
r.stats       # named scalars: centers, limits, indices
r.table       # tidy per-point DataFrame incl. signal flags
r.signals     # tuple of structured violations (rule, chart, points, note)
r.meta        # provenance: n, version, input hash, timestamp, source
r.baseline    # frozen parameters; .save(path) / Baseline.load(path)
r.summary()   # plain-text verdict
r.plot(ax=None)
r.to_html(path=None, title=None)
r.to_dict()   # JSON-safe, integer-versioned schema
```

Reports over several analyses:

```python
sw.report([r1, r2, r3], "weekly.html", title="Line 3 weekly")
```

## The review verdict

`sw.review()` returns a `Review`, not a `Result`: it composes a chart, the
assumption checks, and (with specification limits) a capability study into
one gate. The underlying `Result` objects stay reachable for drill-down:

```python
rv = sw.review(df, value="torque", lsl=9.95, usl=10.05)
rv.ok            # True iff failures is empty - the gate
rv.failures      # machine-readable causes, e.g. ("out_of_control",)
rv.headline      # a short deterministic verdict line
rv.chart         # the underlying chart Result
rv.capability    # the capability Result, or None
rv.checks        # tuple of Check(name, status, value, threshold, note)
rv.baseline      # passthrough: rv.baseline.save("line3.json")
rv.summary(); rv.plot(); rv.to_html(); rv.to_dict()
```

`rv.to_dict()` is the JSON verdict (schema 1): `ok`, `failures`, `headline`,
`params` (the call echoed, with `limits` as `"fitted"` or `"frozen"`),
`selection` (chart and reason), `control` (status, stats, signals with index
labels), `capability` (always present; `status` `"not_assessed"` carries a
reason code such as `no_spec_limits`, `not_in_control`, `unstable`),
`checks`, `recommendations` (`code`, `message`, `call`), `baseline`, `meta`.
Numeric fields are finite or null - the JSON never contains NaN.

Two covenant rules for consumers:

* The check set and every enum are **open**: minor versions may add checks
  (which can tighten the gate) and enum values. Treat unknown values
  conservatively, and pin the library version where bit-stable gates matter.
* Fields are never removed or renamed, and `failures` is empty exactly when
  `ok` is true.

## String aliases (stable forever)

* Rule sets: `"nelson"`, `"western_electric"`, `"none"`
* Sigma estimators (capability/charts vocabulary follows the AIAG manuals
  and the major commercial packages): `average_mr`, pooled, `rbar`, `sbar`
* Registry: `sw.chart("imr", ...)` dispatches by alias and is the entry
  point reserved for third-party plugins (`shewhart-<name>` packages).

## Conventions

* Data is always the first positional argument; every column or option is a
  keyword with a full word (`value=`, `subgroup=`, `lsl=`, `rules=`).
* On a DatetimeIndex, `subgroup=` also accepts a time window: a fixed one
  such as `"15min"` or `"1h"`, or a calendar one such as `"W"`, `"ME"`, or
  `"QE"`. Calendar windows produce subgroups of differing sizes, which
  `xbar_s` and `review()` handle with stair-step limits.
* Sigma estimators are selected by name: `sw.imr(..., method="average_mr" |
  "median_mr")`, `sw.xbar_r(..., method="rbar")`, `sw.xbar_s(...,
  method="sbar" | "pooled")`. Estimator aliases, like all string aliases,
  never change meaning.
* No `**kwargs` anywhere public.
* Errors teach: every exception ends with a corrected, runnable example.
