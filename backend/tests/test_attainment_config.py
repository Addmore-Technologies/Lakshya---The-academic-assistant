"""Tests for faculty-configurable CO attainment percentages."""

import math
from decimal import Decimal

import pytest

from backend.app.engine.attainment_config import validate_percentage


@pytest.mark.parametrize(
    "value",
    [0, 25, 60, 75.5, 100, Decimal("0"), Decimal("60.5"), Decimal("100")],
)
def test_accepts_valid_percentages(value):
    assert validate_percentage(value, "threshold_pct") == float(value)


@pytest.mark.parametrize(
    "value",
    [
        -1,
        100.1,
        101,
        None,
        True,
        False,
        "60",
        "",
        float("nan"),
        float("inf"),
        -float("inf"),
        Decimal("-1"),
        Decimal("100.1"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_rejects_invalid_percentages(value):
    with pytest.raises(ValueError, match="between 0 and 100"):
        validate_percentage(value, "threshold_pct")


def test_validation_error_identifies_field():
    with pytest.raises(ValueError, match="target_attainment_pct"):
        validate_percentage(150, "target_attainment_pct")
