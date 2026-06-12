# Statistics is not a language task

*For people building agents that touch process data.*

Every day, somewhere, an agent is asked whether a process is stable. It
writes three lines of pandas, draws two red lines, and answers with
confidence:

```python
ucl = data.mean() + 3 * data.std()
lcl = data.mean() - 3 * data.std()
```

The code runs. Nothing looks broken. Both of these are the problem.

The calculation is wrong twice over. Control limits use the within-process
sigma, estimated from successive differences, not the overall standard
deviation. And limits are estimated once from a reference period, then
frozen; they are not recomputed on whatever data arrived today. On a
drifting process, `data.std()` swallows the drift, the limits inflate, and
the chart goes blind at the exact moment it exists for.

No exception is raised. The verdict sounds certain. The number it rests on
is not a statistic. It is a sentence with digits in it.

## The failure mode is confidence

A human who hand-rolls a control chart writes the code once, and a colleague
might catch it. An agent writes it fresh in every conversation, thousands of
times a day, and discards it after running. No review. No version. No record
of which formula produced the number that someone then acted on.

Generated statistics do not fail by crashing. They fail by being believed.

## Three ways to be confidently wrong

**The wrong sigma.** Overall standard deviation where within-process sigma
belongs. The chart that results does not monitor the process; it monitors
its own complacency.

**cumsum is not CUSUM.** A cumulative sum has no reference value, no reset
at zero, no decision interval. It drifts with any nonzero mean. It is what
gets generated when someone asks for a CUSUM chart, and it answers nothing.

**The naked point estimate.** A Cpk computed from five parts, reported as
"1.10". The 95% interval on that number runs from 0.09 to 2.12. Omitting it
is not a simplification. It is a different claim, made silently.

## Correct is specific

None of this is deep mathematics. All of it is exact: bias-correction
constants derived from order statistics, estimators that auditors check by
name, the discipline of fitting limits once and judging new data against
them, run rules as Nelson and Western Electric published them, not as the
corpus half-remembers them. Twenty generated lines do not reliably contain
any of it.

And it is checkable. The same computation either reproduces NIST-certified
reference values or it does not. There is no third state.

## The division of labor

The conclusion is not that agents should keep away from process data. The
conclusion is a boundary:

> **The agent interprets. Validated code calculates.**

Language models are good at understanding what was asked, choosing the right
analysis, and explaining a verdict in plain words. They are not calculators,
and quality statistics is a domain where almost right and right are
indistinguishable until the recall.

## What an accountable number looks like

```json
{
  "method": "imr", "stats": {"i_ucl": 11.13, "...": "..."},
  "signals": [{"rule": "nelson_1", "points": [47]}],
  "meta": {"version": "0.1.1", "input": "sha256:9f2c...",
           "computed_at": "2026-06-13T09:14:02+00:00"}
}
```

Library version. Input hash. Timestamp. Named rules. Six months later, when
someone asks where the number came from, this is the difference between an
answer and a shrug.

A number you cannot recompute is an opinion.

## Five questions before trusting an agent's statistics

1. Computed by generated code, or by a versioned tool?
2. Which sigma estimator, and is it named in the output?
3. Limits frozen from a reference period, or improvised on today's data?
4. Interval, or naked point estimate?
5. Could you reproduce the number from the recorded inputs and version?

If the answer to the first question is "generated code", the remaining four
have no answers.

## The practical part

shewhart is built to sit behind agents. `sw.review(...)` is the one-call
entry point: it selects the right chart, checks the assumptions, and returns
a structured verdict with full provenance; the agent never touches a
formula. Every released number is reproduced against published reference
values, including NIST-certified datasets, on every CI run.

Use it, or use something else that is validated. The principle outranks the
package.
