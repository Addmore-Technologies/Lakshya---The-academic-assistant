"""Validation helpers for faculty-configurable CO attainment."""

import math
from decimal import Decimal


def validate_percentage(value, field_name: str) -> float:
    """Accept a finite percentage between 0 and 100."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(
            f"{field_name} must be a number between 0 and 100"
        )

    number = float(value)

    if not math.isfinite(number) or not 0 <= number <= 100:
        raise ValueError(
            f"{field_name} must be a number between 0 and 100"
        )

    return number
