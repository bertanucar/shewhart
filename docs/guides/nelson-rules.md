# Nelson and Western Electric rules in Python

The task: flag non-random patterns on a control chart, the way Nelson
(Journal of Quality Technology, 1984) and the Western Electric handbook
(1956) define them, and get the violations as data you can route, not just
as red dots on a plot.

## Usage

```python
import shewhart as sw

r = sw.imr(df, value="torque", rules="nelson")           # rules 1-8
r = sw.imr(df, value="torque", rules="western_electric") # WE 1-4
r = sw.imr(df, value="torque", rules="none")             # limits only

for s in r.signals:
    print(s.rule, s.chart, s.points, s.note)
```

Signals are structured events. `r.ok` is False as soon as any rule fires,
and `r.to_dict()["signals"]` is JSON, which makes routing to Slack,
dashboards, or ticket systems a one-liner.

## The rules

| Alias | Pattern |
|-------|---------|
| `nelson_1` | 1 point beyond 3 sigma |
| `nelson_2` | 9 in a row on one side of the center line |
| `nelson_3` | 6 in a row steadily increasing or decreasing |
| `nelson_4` | 14 in a row alternating up and down |
| `nelson_5` | 2 of 3 beyond 2 sigma, same side |
| `nelson_6` | 4 of 5 beyond 1 sigma, same side |
| `nelson_7` | 15 in a row within 1 sigma |
| `nelson_8` | 8 in a row beyond 1 sigma, either side |
| `we_1` to `we_4` | the Western Electric zone tests (1 beyond 3 sigma; 2 of 3 beyond 2; 4 of 5 beyond 1; 8 on one side) |

Two details that hand-rolled implementations usually get wrong:

* **Attribute charts use four tests, not eight.** Zone tests assume
  symmetric normal zones around the center line; p/np/c/u data is not
  normal, so shewhart applies only the four pattern tests there and rejects
  zone rule sets with an explanatory error.
* **EWMA gets no run rules at all.** EWMA values are autocorrelated by
  construction, which invalidates run tests; the EWMA chart signals on
  limit violations only.

## Semantics

Rules operate on the standardized distance from the center line using the
within-process sigma, exactly as on the chart itself. Runs are reported as
one signal covering the full run, not as eight separate flags, so
downstream consumers can deduplicate trivially.
