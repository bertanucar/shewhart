# shewhart

Statistical process control for Python. Control charts with the standard run
rules, process capability analysis with confidence intervals, and (coming in
0.2) measurement systems analysis. Every released number is checked against
published reference values, including NIST-certified datasets, on every CI
run.

```
pip install git+https://github.com/bertanucar/shewhart
```

## Sixty seconds

```python
import shewhart as sw

r = sw.imr(df, value="torque", rules="nelson")
r.ok           # False if any rule fired
print(r.summary())
```

```text
shewhart imr - n=10 - rules=nelson - fitted (Phase I) - v0.1.0.dev0
  i_center=10.7  i_lcl=9.046  i_ucl=12.35  mr_center=0.6222  mr_lcl=0  mr_ucl=2.033  sigma_within=0.5514
verdict: OUT OF CONTROL - 3 signal(s):
  - nelson_1 (i): point 9 - 1 point beyond 3 sigma
  - nelson_2 (i): points 0-8 - 9 in a row on one side of center
  - beyond_limits (mr): point 9 - moving range beyond UCL
```

Fit limits once, monitor forever:

```python
sw.imr(df_baseline, value="torque").baseline.save("line3_baseline.json")

# in the weekly job:
r = sw.imr(df_new, value="torque", limits="line3_baseline.json")
sys.exit(0 if r.ok else 1)
```

## Why this library

* **Correct.** Chart constants are computed from their defining integrals;
  the published tables, NIST StRD certified values, and NIST/SEMATECH
  handbook examples are reproduced in the test suite. See
  [Validation](reference/validation.md).
* **Phase I and Phase II are different things.** Estimating limits and
  monitoring against frozen limits are separate operations, and baselines
  serialize to JSON you can commit next to your code.
* **Built for pipelines.** Rule violations are structured data, `r.ok` is an
  exit code, and reports are single self-contained HTML files.

## Where to start

* [Control charts in Python](guides/control-charts-in-python.md)
* [Process capability with confidence intervals](guides/cpk-in-python.md)
* [The full API on one page](reference/api.md)
