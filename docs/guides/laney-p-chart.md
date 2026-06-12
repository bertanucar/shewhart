# Laney p' charts in Python

The task: your p chart flags half the points as out of control, but the
process is visibly fine. With large subgroups this is expected, not a
process problem, and the Laney p' chart is the standard fix.

## The problem: overdispersion

Classic p-chart limits shrink with 1/sqrt(n). With subgroups of tens of
thousands (call-center days, e-commerce orders, high-volume lines), the
limits collapse onto the center line, and the ordinary day-to-day drift of
the true rate, which binomial theory does not model, makes nearly every
point signal. The chart is not detecting special causes; it is measuring
the failure of the binomial assumption.

## The fix

Laney (Quality Engineering, 2002) standardizes the points, measures their
short-term variation with a moving range (sigma_z), and widens the limits
accordingly:

    UCL_i = pbar + 3 * sigma_i * sigma_z

```python
import shewhart as sw

r = sw.laney_p(df, defectives="rejects", size="inspected")
r.stats["sigma_z"]
```

Reading sigma_z:

* **around 1**: no overdispersion; the classic `sw.p_chart` was fine, and
  the Laney chart reproduces it (sigma_z = 1 gives identical limits)
* **well above 1**: overdispersion confirmed; the Laney limits are the
  honest ones

The test suite contains exactly this contrast: binomial data yields
sigma_z near 1, while data with day-to-day rate variation yields a classic
chart that signals everywhere and a Laney chart that correctly stays quiet.

## Rate data

The same logic for defects per unit:

```python
r = sw.laney_u(df, defects="flaws", size="units")
```

Both charts support the usual Phase I/II workflow (`limits=`), varying
subgroup sizes with stair-step limits, and the four attribute-chart run
rules.
