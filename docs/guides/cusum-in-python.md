# CUSUM charts in Python (and why pandas.cumsum is not one)

The task: detect small sustained shifts, around one sigma, as early as
possible. The CUSUM chart is the classic answer, and it is frequently
confused with a plain cumulative sum. They are not the same thing.

## The three-line version

```python
import shewhart as sw

r = sw.cusum(df, value="torque")          # k=0.5, h=4 by default
r = sw.cusum(df, value="torque", center=10.0, sigma=1.0)   # known parameters
```

## cusum is not cumsum

`pandas.Series.cumsum()` adds up raw values. A CUSUM *chart* accumulates
deviations beyond a reference value and resets at zero:

    C+_i = max(0, x_i - (center + K) + C+_{i-1})
    C-_i = max(0, (center - K) - x_i + C-_{i-1})

The reference value K = k * sigma (k = 0.5 by convention) makes the sums
ignore noise smaller than half a sigma; the reset at zero means in-control
periods do not build up; and the decision interval H = h * sigma turns the
plot into a test. A raw cumulative sum has none of these, drifts with any
nonzero mean, and cannot serve as a control chart.

## Worked example

For values `[10, 10, 10, 11, 12, 13]` with center 10, sigma 1, k = 0.5:
the upper sums are `[0, 0, 0, 0.5, 2.0, 4.5]`, and with h = 4 the last
point crosses the decision interval, so the chart signals at observation 5.
This example runs verbatim in the test suite.

## CUSUM or EWMA?

Both detect small shifts well; both are autocorrelated by construction,
which is why shewhart offers no run rules on either (zone tests would be
statistically invalid). Practical guidance: CUSUM is slightly sharper for a
known shift size (tune k to half the shift you care about); EWMA is easier
to read as a smoothed level. Use `sw.imr()` alongside either to keep
sensitivity to large isolated spikes.
