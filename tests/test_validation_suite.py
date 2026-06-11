"""Runner for the reference-case validation suite (tests/validation_cases.json).

Every released analysis must reproduce its reference cases to the stated
tolerance. This file is the seed of the public validation suite that later
ships as a product feature (sw.validation.report()).
"""

import json
import pathlib

import pandas as pd
import pytest

import shewhart as sw

CASES = json.loads(
    (pathlib.Path(__file__).parent / "validation_cases.json").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_reference_case(case):
    inputs = case["inputs"]
    if "frame" in inputs:
        data = pd.DataFrame(inputs["frame"])
    else:
        data = inputs["data"]

    result = sw.chart(case["chart"], data, **inputs.get("kwargs", {}))

    for key, expected in case["expected"].items():
        got = result.stats[key]
        assert got == pytest.approx(expected, abs=case["tol"]), (
            f"{case['id']}: {key} = {got!r}, expected {expected!r} "
            f"(source: {case['source']})"
        )
