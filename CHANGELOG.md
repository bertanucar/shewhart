# Changelog

## 0.1.1

### Added

* `review()`: one call selects the chart (with an automatic Laney switch
  on sigma_z), runs assumption checks, gates capability behind stability,
  and returns a structured, JSON-safe verdict with machine-readable
  failure codes. The verdict schema is frozen, append-only.
* An agents page (docs: "Statistics is not a language task") and an
  llms.txt refresh for the new surface.
* Tabular CUSUM chart (`cusum`) with reference value and decision interval.
* Laney p' and u' charts (`laney_p`, `laney_u`) for overdispersed attribute
  data, reporting sigma_z.
* Tolerance intervals (`tolerance_interval`): normal method (Howe k2,
  anchored to the NIST handbook factor) and nonparametric (Wilks).
* Non-normal capability: `dist="lognormal" | "weibull" | "gamma" | "auto"`
  (percentile method) and `transform="boxcox"`.
* Named sigma estimators: `imr(method="median_mr")` with a closed-form
  d4(2), `xbar_s(method="pooled")` with B5/B6 limits.

## 0.1.0

First real release. The public API on the
[grammar page](https://bertanucar.github.io/shewhart/reference/api/) is
frozen from this version on: no public name, signature, default value, or
string alias will be removed or change meaning within major version 0/1.

### Added

* Control charts: `imr`, `xbar_r`, `xbar_s`, `p_chart`, `np_chart`,
  `c_chart`, `u_chart` (stair-step limits for varying sizes), `ewma`
  (exact and asymptotic limits), `run_chart` (four runs tests), `pareto`.
* Rules engine: Nelson 1-8 and Western Electric 1-4 as structured,
  JSON-able signal events; attribute charts apply the four attribute tests.
* `capability`: Cp/Cpk/Pp/Ppk/Cpm with confidence intervals (chi-square
  for Cp/Pp, Bissell approximation for Cpk/Ppk), within vs overall sigma,
  observed and expected PPM, stability gate, Anderson-Darling note.
* Phase I/II workflow: fit limits, save baselines as JSON, evaluate new
  data against frozen baselines (`limits=`).
* Time-window subgrouping on DatetimeIndex data (`subgroup="1H"`).
* Self-contained HTML reports: `Result.to_html()` and `sw.report()`.
* Chart constants computed from their defining integrals; published tables
  serve as test oracles.
* Validation suite with external anchors: NIST StRD certified values
  (Michelso, NumAcc1) and the NIST/SEMATECH e-Handbook EWMA example are
  reproduced in CI.

### Compatibility

* The 0.0.1 functions `imr_limits` and `beyond_limits` remain as permanent
  aliases.
