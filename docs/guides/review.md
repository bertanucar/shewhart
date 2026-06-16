# One-call SPC review

`sw.review()` answers the question most people actually have: *is this
process okay?* It selects the right control chart for the data, checks the
assumptions behind it, runs capability against specification limits if you
have them, and returns a single structured verdict.

```python
import shewhart as sw

rv = sw.review(df, value="torque", lsl=9.95, usl=10.05)
rv.ok          # the gate: stable, capable, no failed checks
rv.headline    # "In control: no rule violations on the imr chart. Cpk 1.41 (capable)."
rv.summary()   # the audit text
```

review() is pure composition: every number comes from the validated chart
and capability functions, and `rv.chart` / `rv.capability` hold the full
underlying results. The selection logic below is a set of documented
conventions, not new statistics.

## How the chart is selected

| Your data | Call | Selected chart |
|-----------|------|----------------|
| measurements, no subgroups | `review(df, value="x")` | I-MR |
| measurements in subgroups of 2-8 | `review(df, value="x", subgroup="batch")` | Xbar-R |
| measurements in subgroups of 9+ | same | Xbar-S |
| measurements in subgroups of differing sizes | same | Xbar-S (stair-step) |
| defective units + inspection size | `review(df, defectives="rej", size="insp")` | np (constant size) or p (varying) |
| ... with over/underdispersion | same | Laney p' (automatic) |
| defect counts + inspection size | `review(df, defects="dents", size="area")` | u, or Laney u' (automatic) |
| defect counts, constant opportunity | `review(df, defects="dents")` | c |

The subgroup-size cutoff follows Montgomery (R loses efficiency above n=8).
The Laney switch fires when sigma_z, the variation of the standardized
points, reaches 0.667 or 1.5 - Laney's own reading is that values near 1 mean
the classic chart was fine. The sigma_z value and the reason for every
selection are part of the verdict; nothing is chosen silently.

EWMA and CUSUM are never auto-selected. They have tuning parameters that
belong to you, not to a dispatcher; review() flags the conditions that
call for a different design (such as autocorrelation) and leaves the
choice to you.

## The checks

| Check | When it runs | Boundary |
|-------|--------------|----------|
| `sample_size` | Phase I only | fail below 10 subgroups, warn below 25 (AIAG) |
| `variation` | measurements | fail when all values are identical |
| `normality` | measurements, n >= 8 | warn above the Anderson-Darling 5% critical value |
| `autocorrelation` | individuals, n >= 20 | warn when \|lag-1 r\| exceeds 0.5 |
| `overdispersion` | attribute charts | sigma_z at or beyond 0.667 / 1.5 |
| `binary_data` | measurements | warn when values are only 0/1 |
| `spec_plausibility` | with specs | warn when no observation is inside the limits |
| `target_within_specs` | with target= and specs | warn when the target lies outside the limits |

Checks that did not run are absent from the verdict, and `variation`,
`binary_data`, and `target_within_specs` appear only when they trigger.
`warn` never gates; `fail` does. The check set is open: later versions may add checks, so pin
the version where bit-stable gates matter.

## Capability doctrine

With specification limits, capability runs only when the chart is in
control - indices from an unstable process are not meaningful, so the
verdict withholds them (`status: "not_assessed"`, with a reason code)
instead of reporting a number with a footnote nobody reads. The judged
index is Cpk when available, Ppk on the percentile path; 1.33 and 1.00 are
the conventional boundaries for `capable` / `marginal` / `inadequate`.
A marginal process gates `ok=False` deliberately: whoever accepts Cpk 1.1
should do it looking at the confidence interval, not at a green light.

## Fit once, monitor forever

```python
# Phase I: fit and freeze
sw.review(df_2025, value="torque").baseline.save("line3.json")

# Phase II, nightly: judge new data against the frozen limits
import sys
rv = sw.review(df_today, value="torque", limits="line3.json")
sys.exit(0 if rv.ok else 1)
```

In Phase II the chart comes from the baseline, never re-derived from the
data - new-window quirks like a high sigma_z are findings (they appear as
checks), not grounds to switch charts mid-monitoring. The `sample_size`
check does not run in Phase II: the 25-subgroup guidance is about fitting
limits, and yours are frozen.

## The verdict as JSON

`rv.to_dict()` is built for pipelines and agents - see the
[API page](../reference/api.md#the-review-verdict) for the frozen schema and
[Statistics is not a language task](../agents.md) for why this exists:

```json
{
  "ok": false,
  "failures": ["out_of_control"],
  "headline": "Out of control: 2 signal(s) on the xbar_r chart. Capability not assessed (not in control).",
  "selection": {"chart": "xbar_r", "reason": "subgroup size 4 (2-8 -> Xbar-R)"},
  "control": {"status": "out_of_control", "signals": [{"rule": "nelson_1", "points": [17], "labels": ["2026-06-12 14:00:00"]}]},
  "capability": {"status": "not_assessed", "reason": "not_in_control"},
  "checks": [{"name": "normality", "status": "pass", "value": 0.31, "threshold": 0.75}],
  "recommendations": [{"code": "investigate_signals", "message": "...", "call": null}]
}
```
