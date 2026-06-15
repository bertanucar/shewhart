# Control charts in Python

The task: monitor a measured characteristic over time and get a defensible
answer to "is this process stable?". This page shows the three-line version,
then explains why the usual hand-rolled approach computes the wrong limits.

## The three-line version

```python
import shewhart as sw

r = sw.imr(df, value="torque", rules="nelson")
print(r.summary())
```

For subgrouped data (several measurements per batch or time slot):

```python
r = sw.xbar_r(df, value="torque", subgroup="batch")
```

For counts (defective units, complaints, defects):

```python
r = sw.p_chart(df, defectives="rejects", size="inspected")
r = sw.c_chart(df, defects="scratches")
```

## Why `mean ± 3*std` is not a control chart

The most common hand-rolled pattern looks like this:

```python
# wrong, but everywhere:
ucl = x.mean() + 3 * x.std()
```

Two problems, both of which change the limits:

1. **Wrong sigma.** Control limits use the *within*-process variation,
   estimated from short-term differences (the moving range for individuals,
   R-bar or S-bar for subgroups), not the overall standard deviation. If the
   process drifts, `x.std()` absorbs the drift and inflates the limits,
   which is precisely the signal a chart exists to catch. For individuals
   the correct estimate is `mean(|x[i] - x[i-1]|) / d2(2)` with
   `d2(2) = 2/sqrt(pi) = 1.12838`.
2. **Phase confusion.** Limits are estimated once from a reference period
   (Phase I) and then *frozen*; new data is judged against the frozen limits
   (Phase II). Recomputing limits from each new batch silently moves the
   goalposts every week.

shewhart treats both as first-class:

```python
# Phase I: estimate and freeze
sw.imr(df_2025, value="torque").baseline.save("line3_baseline.json")

# Phase II: judge new data against the frozen baseline
r = sw.imr(df_this_week, value="torque", limits="line3_baseline.json")
sys.exit(0 if r.ok else 1)
```

## Choosing a chart

| Data | Chart |
|------|-------|
| one measurement per period | `sw.imr` |
| n measurements per subgroup, n <= 8 or so | `sw.xbar_r` |
| larger subgroups | `sw.xbar_s` |
| subgroups of differing sizes | `sw.xbar_s` (stair-step limits) |
| defective units out of n inspected | `sw.p_chart` (varying n) or `sw.np_chart` (constant n) |
| defect counts per unit of opportunity | `sw.c_chart` (constant) or `sw.u_chart` (varying) |
| small sustained shifts matter | `sw.ewma` |

## Variable subgroup sizes

When subgroups have different sizes (a common case once you subgroup by a
time window), `sw.xbar_s` estimates sigma once from the pooled
within-subgroup variance and draws each subgroup's limits for its own size:

```python
r = sw.xbar_s(df, value="torque", subgroup="shift")
r.table[["n", "mean_lcl", "mean_ucl", "stdev_lcl", "stdev_ucl"]]
```

The limits become a stair-step, so the scalar limit keys are absent from
`r.stats` (they live per row in the table). `sw.xbar_r` still needs equal
sizes; ranges and the average-range estimator assume a constant n.

## Where the numbers come from

Constants like d2 and the limit factors are computed from their defining
integrals and verified against Montgomery's tables and NIST reference data
in the [validation suite](../reference/validation.md). The run rules follow
Nelson (1984) and the Western Electric handbook; see
[Nelson and Western Electric rules](nelson-rules.md).
