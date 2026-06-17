# shewhart

[![CI](https://github.com/bertanucar/shewhart/actions/workflows/ci.yml/badge.svg)](https://github.com/bertanucar/shewhart/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/shewhart)](https://pypi.org/project/shewhart/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Statistical process control for Python.

Control charts with the standard run rules, process capability analysis, and
measurement systems analysis. Results are computed from the published formulas
and checked against reference values in the test suite.

Named after Walter A. Shewhart.

## Motivation

R has had a maintained SPC package (qcc) since 2004. Python does not: the
existing packages are unmaintained, cover only fragments of the toolkit, and
none of them validate their output against reference data. This library is an
attempt to fix that, with a few specific goals:

* correct constants and estimators, validated against published values
* a clean separation between estimating control limits (Phase I) and
  monitoring new data against frozen limits (Phase II)
* rule violations as structured data, usable in pipelines, not only in plots
* an API that works headless, so a weekly control chart review can run as a
  cron job

```
pip install shewhart
```

Documentation: https://bertanucar.github.io/shewhart/

Runnable examples: [examples/](examples/)

## Status

Version 0.1.1 is on PyPI. Implemented and tested:

* `review()`: one call that selects the right chart, checks the
  assumptions, and returns a structured verdict (see below)
* control charts: I-MR, Xbar-R, Xbar-S, p, np, c, u (stair-step limits for
  varying subgroup sizes), Laney p'/u' for overdispersed data, EWMA (exact
  and asymptotic limits), tabular CUSUM, run chart with the four runs
  tests, Pareto analysis
* time-window subgrouping on DatetimeIndex data (`subgroup="1H"`)
* process capability: Cp, Cpk, Pp, Ppk, Cpm with confidence intervals
  (chi-square for Cp/Pp, Bissell approximation for Cpk/Ppk), within vs
  overall sigma, expected and observed PPM, stability gate, normality
  check; non-normal data via fitted models (percentile method) or Box-Cox
* tolerance intervals: normal (Howe k2, anchored to the NIST handbook
  factor) and nonparametric (Wilks)
* named sigma estimators: average or median moving range, Sbar, pooled
* Nelson rules 1 to 8 and Western Electric rules 1 to 4, returned as
  structured signal events
* chart constants (d2, d3, c4, A2, A3, D3, D4, B3, B4), computed from their
  defining integrals rather than copied from tables
* baseline freezing and reuse (JSON), self-contained HTML reports
* a reference-case validation suite (tests/validation_cases.json), anchored
  externally: NIST StRD certified values (Michelso, NumAcc1) and the
  NIST/SEMATECH e-Handbook EWMA worked example are reproduced in CI

## Usage

One call, if you just want a verdict:

```python
import shewhart as sw

rv = sw.review(df, value="torque", lsl=9.95, usl=10.05)
rv.ok          # in control, capable, no failed checks
rv.headline    # "In control: no rule violations on the imr chart. Cpk 1.41 (capable)."
rv.to_dict()   # the full verdict as JSON-safe data
```

review() selects the chart from the data shape, checks the assumptions,
and refuses to report capability on an unstable process. The individual
analyses behind it:

```python
r = sw.imr(df, value="torque", rules="nelson")
r.ok           # False if any rule fired
r.summary()    # plain text verdict
r.table        # per-point DataFrame with signal flags
r.plot()
```

Subgrouped data:

```python
r = sw.xbar_r(df, value="torque", subgroup="batch")
```

Fit limits once, then monitor new data against them:

```python
sw.imr(df_baseline, value="torque").baseline.save("line3_baseline.json")

# later, e.g. in a scheduled job:
r = sw.imr(df_new, value="torque", limits="line3_baseline.json")
sys.exit(0 if r.ok else 1)
```

Capability analysis, with the confidence intervals that the usual
hand-rolled Cpk calculation cannot give you:

```python
r = sw.capability(df, value="dia", lsl=9.95, usl=10.05)
r.stats["cpk"], r.stats["cpk_lci"], r.stats["cpk_uci"]
```

Several analyses in one self-contained HTML file, e.g. as a weekly job:

```python
sw.report([
    sw.imr(df, value="torque", limits="line3_baseline.json"),
    sw.p_chart(df2, defectives="rejects", size="inspected"),
    sw.capability(df, value="torque", lsl=9.5, usl=11.0),
], "weekly_report.html", title="Line 3 weekly")
```

Every analysis returns the same `Result` object: named statistics, a tidy
per-point table, a tuple of structured rule violations, and provenance
metadata (library version, input hash, timestamp).

If you are wiring this into an AI agent, read
[Statistics is not a language task](https://bertanucar.github.io/shewhart/agents/)
first.

## Roadmap

| Version | Scope |
|---------|-------|
| 0.2     | measurement systems analysis: ANOVA gauge R&R (crossed and nested), Type 1 studies, attribute agreement |
| 0.3     | process screening across many characteristics, drift monitoring with control chart semantics |

Out of scope: DOE (see pyDOE3), reliability engineering (see reliability),
general statistics (see statsmodels), GUIs.

## License

MIT. Written and maintained by [Bertan Ucar](https://github.com/bertanucar),
PhD researcher at Tsinghua University.
