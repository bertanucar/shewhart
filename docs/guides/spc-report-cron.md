# SPC reports as a cron job

The task: every Monday at 06:00, pull last week's measurements from the
database, judge them against frozen control limits, write one HTML file
people can open, and fail loudly if anything is out of control. No clicks.

## The whole job

```python
# weekly_spc.py
import sys
import pandas as pd
import shewhart as sw

df = pd.read_sql("SELECT * FROM measurements WHERE week = current", engine)

results = [
    sw.imr(df, value="torque", limits="baselines/torque.json"),
    sw.xbar_r(df, value="dia", subgroup="batch", limits="baselines/dia.json"),
    sw.p_chart(df_insp, defectives="rejects", size="inspected"),
    sw.capability(df, value="torque", lsl=9.5, usl=11.0),
]

sw.report(results, "/srv/reports/line3_weekly.html", title="Line 3 weekly")
sys.exit(0 if all(r.ok for r in results) else 1)
```

```
# crontab
0 6 * * MON python /opt/quality/weekly_spc.py || notify-team
```

## The pieces that make this work

* **Frozen baselines.** Limits were estimated once from a reference period
  and live as JSON files in version control. Week 41 is judged by the same
  limits as week 40; recalculating limits weekly would defeat the chart.
  Refitting is an explicit, reviewable act: rerun the fit, commit the diff.
* **Exit codes.** `r.ok` is True only if no rule fired. The `all(...)`
  expression is the whole alerting logic; your scheduler already knows what
  to do with a non-zero exit.
* **Self-contained reports.** The HTML embeds the charts as images. One
  file, no asset server, mailable, archivable next to the batch record.
* **Structured signals.** Need the violations in your own system instead?
  `r.to_dict()["signals"]` is JSON with rule, chart, points, and note.

## Provenance

Every result carries the library version, an input-data hash, and a
timestamp in `r.meta`, and prints them in the report footer block. When an
auditor asks how a number was produced, the report answers.
