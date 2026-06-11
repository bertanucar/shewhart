# shewhart

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

## Status

Under active development, pre 0.1. Implemented and tested so far:

* I-MR, Xbar-R and Xbar-S charts
* Nelson rules 1 to 8 and Western Electric rules 1 to 4
* chart constants (d2, d3, c4, A2, A3, D3, D4, B3, B4), computed from their
  defining integrals rather than copied from tables
* baseline freezing and reuse (JSON)
* a reference-case validation suite (tests/validation_cases.json)

The version on PyPI (0.0.1) predates most of this. Until 0.1 is released,
install from source:

```
pip install git+https://github.com/bertanucar/shewhart
```

## Usage

```python
import shewhart as sw

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

Every analysis returns the same `Result` object: named statistics, a tidy
per-point table, a tuple of structured rule violations, and provenance
metadata (library version, input hash, timestamp).

## Roadmap

| Version | Scope |
|---------|-------|
| 0.1     | attribute charts (p, np, c, u), run chart, capability analysis with confidence intervals, HTML report |
| 0.1.x   | EWMA, CUSUM, Laney p'/u', non-normal capability, tolerance intervals |
| 0.2     | measurement systems analysis: ANOVA gauge R&R (crossed and nested), Type 1 studies, attribute agreement |
| 0.3     | process screening across many characteristics, drift monitoring with control chart semantics |

Out of scope: DOE (see pyDOE3), reliability engineering (see reliability),
general statistics (see statsmodels), GUIs.

## License

MIT. Written and maintained by [Bertan Ucar](https://github.com/bertanucar),
PhD researcher at Tsinghua University.
