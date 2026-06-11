# shewhart

**Statistical process control (SPC) for Python — validated, pandas-native, automation-first.**

Named after Walter A. Shewhart, the father of statistical process control.

## Why

Quality engineering is the most under-served statistical vertical in Python. R has had
`qcc` since 2004; Python has a graveyard of abandoned fragments. Nothing does proper
ANOVA Gauge R&R, capability indices ship without confidence intervals, and none of it
is built for the way modern process data actually lives: in pandas, in databases, in
pipelines that should produce Monday-morning reports without anyone clicking a mouse.

`shewhart` is being built to close that gap:

- **Control charts** that respect Phase I / Phase II separation, with Nelson and
  Western Electric rule engines
- **Process capability** (Cp/Cpk/Pp/Ppk) with honest confidence intervals and
  non-normal methods
- **Measurement systems analysis** — full ANOVA Gauge R&R the way the AIAG manual
  defines it
- **One-call HTML reports** — your weekly control chart review as a cron job
- **A public validation suite** against NIST/SEMATECH reference datasets

## Status

`v0.0.1` — first working primitives while the full `v0.1` is under active development
(target: 2026). The API below is real and tested; everything else is on the
[roadmap](#roadmap).

```python
import shewhart as sw

limits = sw.imr_limits([10.2, 10.4, 10.1, 10.5, 10.3, 10.2, 10.6])
# {'i_center': 10.329, 'i_lcl': 9.531, 'i_ucl': 11.126, ...}

flags = sw.beyond_limits([10.2, 10.4, 12.9, 10.5], limits)
# [False, False, True, False]
```

## Roadmap

| Version | Scope |
|---------|-------|
| v0.1    | Shewhart chart family (I-MR, X̄-R, X̄-S, p/np/c/u), EWMA, CUSUM, rule engines, capability with CIs, HTML reports, NIST validation suite |
| v0.2    | Measurement systems analysis: crossed/nested ANOVA Gauge R&R, Type 1 studies, attribute agreement |
| v0.3    | `monitor` — drift and change-point detection with control-chart semantics (ARL-calibrated) for sensor streams and ML-model outputs |
| v0.4    | Multivariate: Hotelling T², MEWMA, PCA-based monitoring |

Out of scope by design: DOE (see `pyDOE3`), reliability (see `reliability`),
general statistics (see `statsmodels`, `pingouin`), GUIs.

## Author

Built by [Bertan Ucar](https://github.com/bertanucar) — PhD researcher in
AI-driven quality engineering at Tsinghua University.

## License

MIT
