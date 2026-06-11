import math

import pytest

from shewhart import beyond_limits, imr_limits


def test_imr_limits_hand_computed():
    # x = [10, 12, 11, 13, 12]: MRs = [2, 1, 2, 1] -> MRbar = 1.5, mean = 11.6
    lim = imr_limits([10, 12, 11, 13, 12])
    assert math.isclose(lim["i_center"], 11.6)
    assert math.isclose(lim["mr_center"], 1.5)
    sigma = 1.5 / 1.128
    assert math.isclose(lim["sigma_within"], sigma, rel_tol=1e-12)
    assert math.isclose(lim["i_ucl"], 11.6 + 3 * sigma, rel_tol=1e-12)
    assert math.isclose(lim["i_lcl"], 11.6 - 3 * sigma, rel_tol=1e-12)
    assert math.isclose(lim["mr_ucl"], 3.267 * 1.5, rel_tol=1e-12)
    assert lim["mr_lcl"] == 0.0
    assert lim["n"] == 5


def test_constant_series_limits_collapse_to_mean():
    lim = imr_limits([5.0] * 10)
    assert lim["i_lcl"] == lim["i_center"] == lim["i_ucl"] == 5.0
    assert lim["sigma_within"] == 0.0


def test_beyond_limits_flags_outliers():
    lim = imr_limits([10, 12, 11, 13, 12])
    flags = beyond_limits([11.0, 100.0, -50.0], lim)
    assert flags == [False, True, True]


def test_too_few_observations_raises():
    with pytest.raises(ValueError):
        imr_limits([1.0])
