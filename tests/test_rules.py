import numpy as np
import pytest

from shewhart._rules import RULES, apply_rules, resolve_ruleset


def run(key, z):
    return RULES[key].fn(np.asarray(z, dtype="float64"))


def test_nelson_1_points_beyond_3_sigma():
    assert run("nelson_1", [0, 3.5, 0, -4.0]) == [(1,), (3,)]
    assert run("nelson_1", [0, 2.9, -2.9]) == []


def test_nelson_2_nine_same_side():
    nine = [0.5] * 9
    assert run("nelson_2", nine) == [tuple(range(9))]
    assert run("nelson_2", [0.5] * 8) == []
    assert run("nelson_2", [-0.5] * 10) == [tuple(range(10))]


def test_nelson_3_trend_of_six():
    assert run("nelson_3", [0, 0.1, 0.2, 0.3, 0.4, 0.5]) == [tuple(range(6))]
    assert run("nelson_3", [0, 0.1, 0.1, 0.3, 0.4, 0.5]) == []  # plateau breaks it
    assert run("nelson_3", [0.5, 0.4, 0.3, 0.2, 0.1, 0.0]) == [tuple(range(6))]


def test_nelson_4_fourteen_alternating():
    z = [0.5 * (-1) ** i for i in range(14)]
    assert run("nelson_4", z) == [tuple(range(14))]
    assert run("nelson_4", z[:13]) == []


def test_nelson_5_two_of_three_beyond_two_sigma():
    assert run("nelson_5", [2.5, 0.0, 2.5]) == [(0, 2)]
    assert run("nelson_5", [2.5, 0.0, -2.5]) == []  # opposite sides do not count
    assert run("nelson_5", [2.5, 2.5, 0.0]) == [(0, 1)]


def test_nelson_6_four_of_five_beyond_one_sigma():
    assert run("nelson_6", [1.5, 1.5, 0.0, 1.5, 1.5]) == [(0, 1, 3, 4)]
    assert run("nelson_6", [1.5, 1.5, 0.0, 0.0, 1.5]) == []


def test_nelson_7_fifteen_within_one_sigma():
    assert run("nelson_7", [0.2] * 15) == [tuple(range(15))]
    assert run("nelson_7", [0.2] * 14) == []


def test_nelson_8_eight_beyond_one_sigma_mixed_sides():
    z = [1.5 * (-1) ** i for i in range(8)]
    assert run("nelson_8", z) == [tuple(range(8))]
    assert run("nelson_8", z[:7]) == []


def test_we_4_eight_same_side():
    assert run("we_4", [0.5] * 8) == [tuple(range(8))]


def test_resolve_ruleset_teaches_on_typo():
    with pytest.raises(ValueError, match="Available:"):
        resolve_ruleset("westernelectric")


def test_apply_rules_returns_structured_tuples():
    found = apply_rules(np.array([0.0, 3.5, 0.0]), resolve_ruleset("nelson"))
    assert ("nelson_1", RULES["nelson_1"].note, (1,)) in found
