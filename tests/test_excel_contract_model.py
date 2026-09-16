from datetime import date, datetime, time

import pytest
from excel_contract_model import (
    accumulate_generation,
    combined_time,
    excel_numeric_date,
    stored_excel_time,
    strict_colon_time,
)


def test_excel_numeric_date_model_distinguishes_serial_and_compact_values() -> None:
    today = date(2026, 8, 1)
    assert excel_numeric_date(40926, today) == date(2012, 1, 18)
    assert excel_numeric_date(70926, today) == date(2026, 9, 7)


def test_excel_time_model_is_strict_and_preserves_combined_seconds() -> None:
    assert strict_colon_time("09:30:45") == time(9, 30, 45)
    assert combined_time(datetime(2026, 9, 7, 23, 50), "09:30:45") == datetime(
        2026, 9, 7, 9, 30, 45
    )
    for token in ("09:30:-1", "09:+30", "09:30.5", "09:3e1", "24:00"):
        with pytest.raises(ValueError):
            strict_colon_time(token)


def test_stored_excel_time_accepts_midnight_but_rejects_raw_nonzero_integers() -> None:
    assert stored_excel_time(0) == time(0, 0)
    assert stored_excel_time(0.5) == time(12, 0)
    for raw_value in (1, 930):
        with pytest.raises(ValueError):
            stored_excel_time(raw_value)


def test_excel_generation_model_resets_adds_and_replaces() -> None:
    assert accumulate_generation(100, 5, date(2026, 10, 1), None, 0) == (5, date(2026, 9, 30))
    assert accumulate_generation(100, 5, date(2026, 10, 1), date(2026, 9, 30), 4) == (
        105,
        date(2026, 9, 30),
    )
    assert accumulate_generation(105, 7, date(2026, 10, 1), date(2026, 10, 1), 5) == (
        107,
        date(2026, 9, 30),
    )
    assert accumulate_generation(999, 8, date(2026, 10, 2), date(2026, 10, 1), 7) == (
        8,
        date(2026, 10, 1),
    )
