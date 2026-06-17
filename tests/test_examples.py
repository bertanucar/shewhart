"""Run every example script, so the examples cannot rot."""

import importlib.util
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fit_freeze_monitor_detects_the_drift(tmp_path):
    module = _load("fit_freeze_monitor")
    assert module.main(tmp_path) == 1  # the drift is out of control
    assert (tmp_path / "torque_baseline.json").exists()


def test_weekly_report_writes_html(tmp_path):
    module = _load("weekly_report")
    assert module.main(tmp_path) == 0
    html = (tmp_path / "weekly_report.html").read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>")


def test_triage_with_review_writes_a_verdict(tmp_path):
    module = _load("triage_with_review")
    assert module.main(tmp_path) == 1  # in control but not capable
    import json

    verdict = json.loads((tmp_path / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["method"] == "review"
    assert "capability_inadequate" in verdict["failures"]
