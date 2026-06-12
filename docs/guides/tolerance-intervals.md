# Tolerance intervals in Python

The task: state bounds that contain at least 99% of production, with 95%
confidence. That is a tolerance interval. It is routinely confused with two
other intervals that answer different questions:

* a **confidence interval** brackets a parameter (the mean),
* a **prediction interval** brackets the next single observation,
* a **tolerance interval** brackets a chosen proportion of the whole
  population. Specification work in pharma and medical devices means this
  one.

## Usage

```python
import shewhart as sw

r = sw.tolerance_interval(df, value="potency", coverage=0.99, confidence=0.95)
r.stats["lower"], r.stats["upper"]
```

Distribution-free, using only the sample extremes:

```python
r = sw.tolerance_interval(df, value="potency", coverage=0.90,
                          confidence=0.95, method="nonparametric")
```

The nonparametric route needs a minimum sample size that depends only on n;
if the data cannot support the requested confidence, the error message says
exactly how many observations would.

## Where the numbers come from

The normal method uses Howe's k2 approximation, the same formula the
NIST/SEMATECH e-Handbook documents (section 7.2.6.3). The handbook's
published factor for n = 43, 90% coverage, 99% confidence is k2 = 2.217;
shewhart reproduces it in the validation suite. The nonparametric method is
Wilks' classic result for the (min, max) interval.

The normal method is sensitive to the normality
assumption precisely because it reaches into the far tails. Check
normality first (a capability study reports an Anderson-Darling note), and
prefer the nonparametric method when in doubt and the sample is large
enough.
