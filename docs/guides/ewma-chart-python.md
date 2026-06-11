# EWMA charts in Python

The task: detect small sustained shifts (around 0.5 to 1.5 sigma) that a
Shewhart chart is slow to catch.

## Usage

```python
import shewhart as sw

r = sw.ewma(df, value="torque", lam=0.2)
```

Smaller `lam` reacts to smaller shifts; 0.1 to 0.3 are the common choices.
Limits are exact (time-varying) by default and widen toward the asymptote;
pass `asymptotic=True` for fixed steady-state limits.

Monitoring against known parameters, for example from a historical study:

```python
r = sw.ewma(df_new, value="torque", center=50.0, sigma=2.0539, lam=0.3)
sys.exit(0 if r.ok else 1)
```

## Checked against NIST

The implementation reproduces the NIST/SEMATECH e-Handbook worked example
(section 6.3.2.4) end to end in CI: the same 20 observations, lambda = 0.3,
center 50, historical sigma 2.0539, the published limits 52.5884 / 47.4115,
and the full published EWMA series. The handbook's verdict (in control,
with a late upward trend) is exactly what `r.summary()` reports.

## Two things worth knowing

* **No run rules on EWMA.** The EWMA statistic is autocorrelated by
  construction, so zone and run tests are statistically invalid on it.
  shewhart signals on limit violations only, and says so in the result
  parameters instead of silently applying tests that do not apply.
* **Exact vs asymptotic limits.** Early EWMA values have smaller variance;
  exact limits reflect that and are tighter for the first points. The
  asymptotic option exists because many textbooks (and the NIST example)
  use the steady-state factor sqrt(lam / (2 - lam)).
