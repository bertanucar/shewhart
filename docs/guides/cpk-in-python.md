# Process capability (Cp, Cpk) in Python

The task: given measurements and specification limits, report how capable
the process is, in the format a customer or auditor expects.

## The three-line version

```python
import shewhart as sw

r = sw.capability(df, value="dia", lsl=9.95, usl=10.05)
print(r.stats["cpk"], r.stats["cpk_lci"], r.stats["cpk_uci"])
```

## Why the usual snippet is wrong twice

The standard search result computes:

```python
# wrong, but everywhere:
cpk = min(usl - x.mean(), x.mean() - lsl) / (3 * x.std())
```

1. **Wrong sigma.** Cp and Cpk are defined on the *within*-process sigma
   (moving range / d2 for individuals, pooled standard deviation for
   subgroups). `x.std()` is the *overall* sigma, which defines Pp and Ppk.
   The two pairs answer different questions (short-term potential vs
   long-term performance), and mixing them up changes the number a customer
   sees. shewhart reports both, labeled correctly.
2. **No interval.** A Cpk from 30 parts is a point estimate with enormous
   uncertainty. shewhart returns confidence intervals: exact chi-square
   intervals for Cp/Pp, the Bissell approximation (Montgomery, 8th ed.,
   eq. 8.19) for Cpk/Ppk. With 5 observations, a Cpk of 1.10 carries a 95%
   interval of roughly [0.09, 2.12]. If that surprises you, that is the
   point: report the interval, not just the index.

```python
r = sw.capability(x, lsl=9.8, usl=10.8)
# cpk 0.739, 95% CI [0.259, 1.219]   (n = 10)
```

## What else you get

* `pp`, `ppk` with their own intervals, `cpm` if you pass `target=`
* observed and expected PPM beyond the specification limits
* a **stability gate**: `r.ok` is False if any observation is beyond
  3 sigma of the mean, because capability indices of an unstable process
  are not meaningful, and that should be visible rather than silent
* an Anderson-Darling normality note in `r.meta["normality"]`
* subgrouped data: `sw.capability(df, value=, subgroup=, ...)` uses the
  pooled standard deviation with exact degrees of freedom

## Non-normal data

Two routes, depending on what the customer expects:

```python
# percentile method (ISO 22514 style): fit a model, indices from quantiles
r = sw.capability(x, lsl=0.5, usl=15.0, dist="lognormal")   # or "auto"
r.stats["ppk"], r.meta["dist_selected"]

# or transform data and specs together, then analyze on the normal scale
r = sw.capability(x, lsl=0.5, usl=15.0, transform="boxcox")
```

The percentile method reports performance indices (Pp/Ppk) only: within
sigma and normal-theory intervals are normal-model concepts and are
deliberately omitted rather than printed with silent invalidity.
`dist="auto"` fits lognormal, Weibull, gamma, and normal, picks by
Anderson-Darling fit, and reports the comparison in `r.meta["dist_fit_ad"]`.
The dedicated guide,
[non-normal capability](non-normal-capability-python.md), works a full
example through both routes.

## Validation

The mean and overall sigma reproduce NIST StRD certified values (datasets
Michelso and NumAcc1) to full precision in CI; the interval formulas are
locked by hand-derived reference cases. See
[Validation](../reference/validation.md).
