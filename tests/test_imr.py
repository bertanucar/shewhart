import json

import numpy as np
import pandas as pd
import pytest

import shewhart as sw
from shewhart import constants as c

CLEAN = [10.2, 10.4, 10.1, 10.5, 10.3, 10.2, 10.6, 10.3, 10.4, 10.2]


def test_phase_one_stats_exact():
    x = [10.0, 12.0, 11.0, 13.0, 12.0]
    r = sw.imr(x, rules="none")
    mr_bar = 1.5
    sigma = mr_bar / c.d2(2)
    assert r.stats["i_center"] == pytest.approx(11.6)
    assert r.stats["mr_center"] == pytest.approx(mr_bar)
    assert r.stats["sigma_within"] == pytest.approx(sigma)
    assert r.stats["i_ucl"] == pytest.approx(11.6 + 3 * sigma)
    assert r.stats["i_lcl"] == pytest.approx(11.6 - 3 * sigma)
    assert r.stats["mr_ucl"] == pytest.approx(c.D4(2) * mr_bar)
    assert r.ok
    assert r.meta["n"] == 5


def test_spike_triggers_nelson_1():
    r = sw.imr(CLEAN + [14.0])
    assert not r.ok
    assert any(s.rule == "nelson_1" and s.chart == "i" for s in r.signals)
    assert any(s.chart == "mr" for s in r.signals)  # the jump also blows the MR


def test_frozen_baseline_workflow(tmp_path):
    path = tmp_path / "line3_baseline.json"
    sw.imr(CLEAN, rules="none").baseline.save(path)

    shifted = [v + 1.0 for v in CLEAN]
    r = sw.imr(shifted, limits=str(path))
    assert not r.ok
    assert "Phase II" in r.meta["source"]

    again = sw.Baseline.load(path)
    assert again.stats["i_center"] == pytest.approx(np.mean(CLEAN))


def test_baseline_json_roundtrip():
    b = sw.imr(CLEAN, rules="none").baseline
    b2 = sw.Baseline.from_json(b.to_json())
    assert b2.stats == dict(b.stats)
    assert b2.chart == "imr"


def test_dataframe_requires_value_and_teaches():
    df = pd.DataFrame({"torque": CLEAN, "batch": range(len(CLEAN))})
    with pytest.raises(ValueError, match='value="torque"'):
        sw.imr(df)
    r = sw.imr(df, value="torque", rules="none")
    assert r.ok


def test_result_is_json_safe_and_table_is_copy():
    r = sw.imr(CLEAN)
    json.dumps(r.to_dict())
    t = r.table
    t["value"] = 0.0
    assert r.table["value"].iloc[0] == CLEAN[0]


def test_registry_dispatch_and_teaching_error():
    r = sw.chart("imr", CLEAN, rules="none")
    assert r.method == "imr"
    with pytest.raises(ValueError, match="Registered charts"):
        sw.chart("xmr_typo", CLEAN)


def test_summary_reads_like_a_verdict():
    text = sw.imr(CLEAN + [14.0]).summary()
    assert "OUT OF CONTROL" in text
    assert "nelson_1" in text


def test_plot_smoke():
    import matplotlib

    matplotlib.use("Agg")
    axes = sw.imr(CLEAN).plot()
    assert len(axes) == 2
