# Process capability for non-normal data in Python

Flatness, roughness, runout, particle counts, impurity levels, time to
failure: a lot of what gets measured on a shop floor is bounded at zero and
skewed to the right. Run a textbook Cpk on data like that and the normal
model invents a left tail that does not exist and thins out the right tail
that actually produces your scrap. The index looks fine. The process is not.

shewhart handles non-normal capability two ways, both in one call.

## The problem, in numbers

Two hundred flatness measurements, bounded at zero, right-skewed, with an
upper specification of 0.060 mm:

```python
import shewhart as sw

r = sw.capability(x, usl=0.060)        # default: normal model
r.stats["ppk"]            # 1.55
r.stats["ppm_overall"]    # 1.6   expected parts-per-million over spec
r.meta["normality"]       # "Anderson-Darling = 3.249, rejected at 5%"
```

Ppk 1.55 reads as a comfortably capable process. The normality note says the
number rests on a model the data already rejected. Fit a distribution that
matches the shape and the picture changes:

```python
r = sw.capability(x, usl=0.060, dist="auto")
r.meta["dist_selected"]   # "gamma"
r.stats["ppk"]            # 0.95
r.stats["ppm_overall"]    # 1862
```

Same data, same spec. The normal model overstates the index by about 60% and
understates the expected nonconforming rate by three orders of magnitude. The
gamma fit is where the real tail lives.

## Route 1: the percentile method

`dist="lognormal" | "weibull" | "gamma" | "auto"` fits the distribution and
reads the capability indices off its quantiles, the way ISO 22514 defines it.
The spec spread is compared to the 0.135% and 99.865% percentiles of the
fitted model instead of to multiples of a standard deviation:

```python
r = sw.capability(x, usl=0.060, dist="weibull")
r.stats["ppk"]            # 1.20
r.stats["q_upper"]        # 0.0525, the 99.865% percentile of the fit
```

The distribution you assume drives the answer: on this data a Weibull fit
gives Ppk 1.20, gamma gives 0.95, lognormal gives 0.50. That spread is the
reason to let the data choose. `dist="auto"` fits lognormal, Weibull, gamma,
and normal, ranks them by the Anderson-Darling statistic, and keeps the best
one. The full comparison stays in the metadata so the choice is auditable:

```python
r = sw.capability(x, usl=0.060, dist="auto")
r.meta["dist_fit_ad"]
# {'lognormal': 1.5516, 'weibull': 0.5633, 'gamma': 0.4819, 'normal': 3.2489}
```

The percentile route reports performance indices (Pp, Ppk) and the fitted
quantiles. Within-sigma Cp/Cpk and the normal-theory confidence intervals are
normal-model quantities, so they are left out rather than printed next to a
distribution that does not support them.

## Route 2: Box-Cox

`transform="boxcox"` estimates one Box-Cox lambda, applies it to the data and
to the specification limits together, and runs the ordinary normal capability
analysis on the transformed scale. You get the whole set back, indices and
confidence intervals included, expressed on that scale:

```python
r = sw.capability(x, usl=0.060, transform="boxcox")
r.stats["boxcox_lambda"]  # 0.40
r.stats["ppk"]            # 1.01
r.stats["ppk_lci"], r.stats["ppk_uci"]   # the interval comes along
```

Box-Cox needs strictly positive data and strictly positive specification
limits, because the transform is only defined there.

## Which route

The percentile method matches what most customer and ISO 22514 documents
expect for non-normal characteristics, and `dist="auto"` removes the "which
distribution" argument by letting the fit decide. Box-Cox is the better choice
when you want confidence intervals on the indices, or when the same transform
is already used elsewhere in the analysis. When the data passes a normality
check, neither is needed; plain `sw.capability(...)` is the right call, and
the [Cpk guide](cpk-in-python.md) covers it.

One rule holds across all three: capability assumes a stable process. shewhart
runs the stability gate first and refuses to dress up indices computed on a
process that is out of control. A capable-looking number on an unstable
process is the most expensive kind of wrong.

## Validation

The normal-model mean and sigma reproduce NIST StRD certified values in CI;
the distribution fits use scipy's maximum-likelihood estimators and the
Anderson-Darling statistic. See [Validation](../reference/validation.md).
