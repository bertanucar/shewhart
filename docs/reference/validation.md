# Validation

"Validated" is a checkable claim here, not a marketing word. The repository
contains a versioned reference-case suite
([tests/validation_cases.json](https://github.com/bertanucar/shewhart/blob/main/tests/validation_cases.json))
that runs on every CI build. Each case states its inputs, its expected
values, the tolerance, and where the expected values come from.

## External anchors (public domain sources)

| Case | Source | What must match |
|------|--------|-----------------|
| `capability-nist-michelso` | NIST StRD, dataset Michelso | certified mean 299.8524 and certified std 0.0790105478190518, to 1e-9 |
| `capability-nist-numacc1` | NIST StRD, dataset NumAcc1 | exact certified mean and std on a catastrophic-cancellation probe |
| `ewma-nist-handbook` | NIST/SEMATECH e-Handbook 6.3.2.4 | the published EWMA limits and, in the unit tests, the full published EWMA series |

## Derived cases

The remaining cases are synthetic datasets whose expected values are fully
derived in the case file itself (formula by formula, with literature
references: Montgomery 8th ed. for charts and capability, Nelson 1984 for
the rules), at tolerance 1e-9. Synthetic-with-published-derivation means
the suite is redistributable without copyright concerns; commercial worked
examples (e.g. from the AIAG manuals) are checked privately and never
shipped.

## Constants are computed, then tested against tables

d2, d3, and c4 are computed from their defining integrals (closed forms for
n = 2, numerical integration otherwise). The published tables serve as test
oracles, not as the source: `tests/test_constants.py` checks the computed
values against Montgomery's Appendix VI to table precision and against the
exact closed forms where they exist.

## Policy

* Every new analysis ships with at least one reference case in the suite.
* Reference values are never adjusted to make a test pass; if a case fails,
  the code is wrong or the case's derivation is wrong, and either fix is a
  reviewed change.
* Wording discipline: results are "validated against NIST reference data"
  and published formulas. No compatibility claims about commercial products.
