"""EWMA chart, anchored to the NIST/SEMATECH e-Handbook worked example
(section 6.3.2.4): same data, parameters, limits, and EWMA series."""

import numpy as np
import pytest

import shewhart as sw

NIST_DATA = [52.0, 47.0, 53.0, 49.3, 50.1, 47.0, 51.0, 50.1, 51.2, 50.5,
             49.6, 47.6, 49.9, 51.3, 47.8, 51.2, 52.6, 52.4, 53.6, 52.1]
# Handbook EWMA series (2 decimals), without the EWMA_0 = 50.00 starting value.
NIST_EWMA = [50.60, 49.52, 50.56, 50.18, 50.16, 49.21, 49.75, 49.85, 50.26,
             50.33, 50.11, 49.36, 49.52, 50.05, 49.38, 49.92, 50.73, 51.23,
             51.94, 51.99]


def nist_result():
    return sw.ewma(NIST_DATA, center=50, sigma=2.0539, lam=0.3, k=3, asymptotic=True)


def test_nist_handbook_series_reproduced():
    r = nist_result()
    np.testing.assert_allclose(r.table["ewma"].to_numpy(), NIST_EWMA, atol=0.005)


def test_nist_handbook_limits_and_verdict():
    r = nist_result()
    assert r.stats["ewma_ucl"] == pytest.approx(52.5884, abs=1e-3)
    assert r.stats["ewma_lcl"] == pytest.approx(47.4115, abs=1e-3)
    assert r.ok  # handbook conclusion: process in control
    assert "Phase II" in r.meta["source"]


def test_exact_limits_widen_toward_asymptote():
    r = sw.ewma(NIST_DATA, center=50, sigma=2.0539, lam=0.3, k=3)
    ucl = r.table["ucl"].to_numpy()
    assert np.all(np.diff(ucl) > 0)  # exact limits widen with t
    asym = nist_result().stats["ewma_ucl"]
    assert ucl[-1] < asym + 1e-9
    assert ucl[0] < asym  # early limits are tighter: that is the point


def test_fit_path_estimates_center_and_sigma():
    r = sw.ewma(NIST_DATA, lam=0.3)
    assert r.stats["center"] == pytest.approx(np.mean(NIST_DATA))
    assert "Phase I" in r.meta["source"]
    assert r.baseline.chart == "ewma"


def test_shift_is_detected():
    shifted = NIST_DATA + [55.0, 55.5, 56.0, 55.8]
    r = sw.ewma(shifted, center=50, sigma=2.0539, lam=0.3)
    assert not r.ok
    assert all(s.chart == "ewma" for s in r.signals)


def test_lam_validation_teaches():
    with pytest.raises(ValueError, match="lam must be in"):
        sw.ewma(NIST_DATA, lam=1.5)


def test_baseline_roundtrip(tmp_path):
    path = tmp_path / "ewma.json"
    sw.ewma(NIST_DATA, lam=0.3).baseline.save(path)
    r = sw.ewma(NIST_DATA, lam=0.3, limits=str(path))
    assert "Phase II" in r.meta["source"]


def test_plot_smoke():
    import matplotlib

    matplotlib.use("Agg")
    ax = nist_result().plot()
    assert hasattr(ax, "axhline")
