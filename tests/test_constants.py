"""Computed constants vs the published tables (Montgomery, App. VI) as oracles."""

import math

import pytest

from shewhart import constants as c

TABLE = 1e-3  # published tables carry 3-4 decimals


def test_c4_closed_form():
    assert math.isclose(c.c4(2), math.sqrt(2 / math.pi), rel_tol=1e-12)
    assert math.isclose(c.c4(5), 0.9400, abs_tol=TABLE)
    assert math.isclose(c.c4(10), 0.9727, abs_tol=TABLE)


def test_d2_matches_table_and_closed_form():
    assert math.isclose(c.d2(2), 2 / math.sqrt(math.pi), rel_tol=1e-9)
    assert math.isclose(c.d2(5), 2.326, abs_tol=TABLE)
    assert math.isclose(c.d2(10), 3.078, abs_tol=TABLE)


def test_d3_matches_table_and_closed_form():
    assert math.isclose(c.d3(2), math.sqrt(2 - 4 / math.pi), rel_tol=1e-6)
    assert math.isclose(c.d3(5), 0.864, abs_tol=TABLE)


def test_chart_factors():
    assert math.isclose(c.A2(5), 0.577, abs_tol=TABLE)
    assert math.isclose(c.D4(2), 3.267, abs_tol=TABLE)
    assert math.isclose(c.D4(5), 2.114, abs_tol=TABLE)
    assert c.D3(5) == 0.0
    assert math.isclose(c.D3(7), 0.076, abs_tol=TABLE)
    assert c.B3(5) == 0.0
    assert math.isclose(c.B4(5), 2.089, abs_tol=TABLE)
    assert math.isclose(c.B3(10), 0.284, abs_tol=TABLE)
    assert math.isclose(c.B4(10), 1.716, abs_tol=TABLE)


def test_invalid_n_teaches():
    with pytest.raises(ValueError, match="constants.d2"):
        c.d2(1)
