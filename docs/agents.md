# Statistics is not a language task

*For people building agents that touch process data.*

Ask an agent whether a process is stable and it will, with great confidence,
write something like this:

```python
ucl = data.mean() + 3 * data.std()
lcl = data.mean() - 3 * data.std()
```

It runs. It plots. It is wrong twice.

Control limits are built on the within-process sigma, estimated from
successive differences; `data.std()` measures the overall spread. And
limits get fitted once, on a reference period, then frozen; you do not
recompute them on whatever data showed up today. On a drifting process,
`data.std()` quietly swallows the drift, the limits balloon, and the chart
goes blind at exactly the moment you bought it for.

No exception. No warning. Just a confident number that happens to be
fiction.

## The failure mode is confidence

When a human hand-rolls a control chart, the code gets written once, and
there is at least a chance a colleague catches the bug. An agent writes it
fresh, thousands of times a day, and throws it away after running. Nobody
reviews code that lives for four seconds.

A crash would be merciful. Generated statistics fail by being believed.

## Three classics

**The wrong sigma.** Overall standard deviation where within-process sigma
belongs. The chart you get out of it monitors its own complacency.

**cumsum is not CUSUM.** A cumulative sum has no reference value, no reset,
no decision interval. It just wanders off with any nonzero mean. It is what
you get when you ask for a CUSUM chart and nobody checks, and it answers
nothing.

**The naked Cpk.** Five parts, "Cpk = 1.10", case closed. The 95% interval
on that number runs from 0.09 to 2.12. Leaving that out changes the
claim, quietly.

## None of this is hard. All of it is exact.

Bias-correction constants derived from order statistics. Estimators that
auditors check by name. Limits fitted once, then frozen. Run rules exactly as
Nelson and Western Electric published them; the training corpus remembers
them about half right. Twenty freshly generated lines do not reliably
contain any of that. And there is a simple test: the code either reproduces
NIST-certified reference values or it does not. There is no third state.

## The division of labor

Keep agents on the process data. Keep them off the arithmetic.

> **The agent interprets. Validated code calculates.**

Models are genuinely good at figuring out what was asked, picking the right
analysis, and explaining a verdict in plain words. They are just not
calculators. And quality statistics is a field where almost right and right
look identical until the recall.

## What an accountable number looks like

```json
{
  "method": "imr", "stats": {"i_ucl": 11.13, "...": "..."},
  "signals": [{"rule": "nelson_1", "points": [47]}],
  "meta": {"version": "0.1.1", "input": "sha256:9f2c...",
           "computed_at": "2026-06-13T09:14:02+00:00"}
}
```

Library version, input hash, timestamp, named rules. Six months from now,
when someone asks where that number came from, this is the difference
between an answer and a shrug.

A number you cannot recompute is an opinion.

## The practical part

This is why shewhart is built the way it is. `sw.review(...)` is one call:
it picks the chart, checks the assumptions, and returns a structured
verdict with full provenance. The agent never touches a formula. Every
released number is re-derived against published reference values,
NIST-certified datasets included, on every CI run.

Use it, or use something else that is validated. The principle outranks the
package.
