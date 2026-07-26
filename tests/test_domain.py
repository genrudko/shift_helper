from decimal import Decimal

import pytest

from shift_helper.domain import calculate_repair_power_mw, parse_rotor_limit


@pytest.mark.parametrize(
    ("rotor_limit", "expected"),
    [
        ("1.00", "0.00"),
        ("0.95", "0.00"),
        ("0.90", "0.55"),
        ("0.85", "0.75"),
        ("0.80", "1.00"),
        ("0.75", "1.20"),
        ("0.70", "1.40"),
        ("0.69", "2.50"),
        ("0.92", "0.45"),
    ],
)
def test_approved_repair_power_table(rotor_limit: str, expected: str) -> None:
    assert calculate_repair_power_mw(Decimal(rotor_limit)) == Decimal(expected)


def test_repair_power_without_limit_is_empty() -> None:
    assert calculate_repair_power_mw(None) is None


def test_rotor_limit_accepts_comma_separator() -> None:
    assert parse_rotor_limit("0,80") == Decimal("0.80")
