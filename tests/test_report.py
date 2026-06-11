import pathlib

import pandas as pd
import pytest

import shewhart as sw

CLEAN = [10.2, 10.4, 10.1, 10.5, 10.3, 10.2, 10.6, 10.3, 10.4, 10.2]


def test_to_html_returns_self_contained_page():
    html = sw.imr(CLEAN).to_html()
    assert html.startswith("<!DOCTYPE html>")
    assert "data:image/png;base64," in html  # embedded chart, no external assets
    assert "IN CONTROL" in html
    assert "i_center" in html
    assert "Provenance" in html


def test_to_html_writes_file(tmp_path):
    out = sw.imr(CLEAN).to_html(tmp_path / "r.html")
    assert isinstance(out, pathlib.Path)
    assert out.read_text(encoding="utf-8").count("data:image/png") == 1


def test_out_of_control_renders_red_badge_and_signals():
    html = sw.imr(CLEAN + [14.0]).to_html()
    assert "OUT OF CONTROL" in html
    assert "nelson_1" in html


def test_report_combines_results(tmp_path):
    r1 = sw.imr(CLEAN)
    r2 = sw.c_chart([3, 2, 4, 1, 3])
    r3 = sw.capability(CLEAN, lsl=9.5, usl=11.0)
    out = sw.report([r1, r2, r3], tmp_path / "weekly.html", title="Line 3 weekly")
    text = out.read_text(encoding="utf-8")
    assert "Line 3 weekly" in text
    assert text.count("data:image/png") == 3
    assert "ALL IN CONTROL" in text


def test_report_banner_counts_signalling_results():
    bad = sw.imr(CLEAN + [14.0])
    html = sw.report([sw.imr(CLEAN), bad])
    assert "1 of 2 analyses signal" in html


def test_report_empty_teaches():
    with pytest.raises(ValueError, match="at least one Result"):
        sw.report([])
