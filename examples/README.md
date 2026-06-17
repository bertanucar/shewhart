# Examples

Runnable end-to-end scripts. Each generates its own data, so you can run it
straight after `pip install shewhart` and read real output. They are executed
on every CI run, so they stay working.

| Script | What it shows |
|--------|---------------|
| [`fit_freeze_monitor.py`](fit_freeze_monitor.py) | Fit limits from a reference period, freeze them to a JSON baseline, judge new data against the frozen limits, and exit non-zero when out of control. The cron / CI pattern. |
| [`weekly_report.py`](weekly_report.py) | One self-contained HTML report combining a variables chart (weekly calendar subgrouping, stair-step limits) and a p chart. The Monday-morning report. |
| [`triage_with_review.py`](triage_with_review.py) | One `sw.review()` call that selects the chart, checks the assumptions, runs capability, and writes the JSON verdict an agent would act on. |

Run any of them:

```bash
python examples/fit_freeze_monitor.py
```
