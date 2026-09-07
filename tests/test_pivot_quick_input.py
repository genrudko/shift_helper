from datetime import date, datetime, time

import pytest

from shift_helper.core.quick_input import (
    accumulate_generation,
    is_stored_time,
    parse_combined_input,
    QuickInputError,
    normalize_date_paste,
    normalize_time_paste,
    parse_date_input,
    parse_time_input,
)

TODAY = date(2026, 8, 1)
NOW = datetime(2026, 8, 1, 20, 23, 45)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("!", date(2026, 8, 1)),
        ("7", date(2026, 8, 7)),
        ("07", date(2026, 8, 7)),
        ("0708", date(2026, 8, 7)),
        ("070826", date(2026, 8, 7)),
        ("07.08.2026", date(2026, 8, 7)),
        ("2026-08-07", date(2026, 8, 7)),
    ],
)
def test_date_contract(raw: object, expected: date) -> None:
    assert parse_date_input(raw, previous=None, today=TODAY) == expected


def test_date_previous_and_increment() -> None:
    previous = date(2026, 7, 31)
    assert parse_date_input(".", previous=previous, today=TODAY) == previous
    assert parse_date_input("+2", previous=previous, today=TODAY) == date(2026, 8, 2)


@pytest.mark.parametrize("raw", ["3102", "0008", "321226", "text", "+x"])
def test_impossible_date_is_visible(raw: str) -> None:
    with pytest.raises(QuickInputError):
        parse_date_input(raw, previous=None, today=TODAY)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("!", time(20, 23)),
        ("9", time(9, 0)),
        ("09", time(9, 0)),
        ("930", time(9, 30)),
        ("1530", time(15, 30)),
        ("15:30", time(15, 30)),
        ("15:30:59", time(15, 30, 59)),
    ],
)
def test_time_contract(raw: object, expected: time) -> None:
    assert parse_time_input(raw, previous=None, now=NOW).value == expected


def test_time_increment_reports_midnight_rollover() -> None:
    parsed = parse_time_input("+20", previous=time(23, 50), now=NOW)
    assert parsed.value == time(0, 10)
    assert parsed.day_offset == 1


@pytest.mark.parametrize(
    "raw",
    ["24", "1260", "999", "15:99", "09:30:-1", "09:+30", "09:30.5", "09:3e1", "abc"],
)
def test_impossible_time_is_visible(raw: str) -> None:
    with pytest.raises(QuickInputError):
        parse_time_input(raw, previous=None, now=NOW)


def test_bulk_date_and_time_paste_is_sequential() -> None:
    dates = normalize_date_paste(
        [".", "+1", "3102", "0708"],
        previous_above=date(2026, 8, 1),
        today=TODAY,
    )
    assert dates[0].value == date(2026, 8, 1)
    assert dates[1].value == date(2026, 8, 2)
    assert dates[2].error
    assert dates[3].value == date(2026, 8, 7)

    times = normalize_time_paste([".", "+20", "2500", "930"], previous_above=time(23, 50), now=NOW)
    assert times[0].value == time(23, 50)
    assert times[1].value == time(0, 10)
    assert times[1].day_offset == 1
    assert times[2].error
    assert times[3].value == time(9, 30)


def test_excel_numeric_compact_date_wins_only_when_it_is_a_valid_operator_date() -> None:
    assert parse_date_input(70926, previous=None, today=TODAY) == date(2026, 9, 7)
    assert parse_date_input(46272, previous=None, today=TODAY) == date(2026, 9, 7)


@pytest.mark.parametrize("token", ["+0", "+1.5", "+1e2", "+ 2", "+-2"])
def test_increment_is_a_strict_positive_integer(token: str) -> None:
    with pytest.raises(QuickInputError):
        parse_time_input(token, previous=time(9, 0), now=NOW)


def test_raw_integer_is_not_a_valid_stored_time() -> None:
    assert not is_stored_time(930)
    assert is_stored_time(0.5)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0709 930", datetime(2026, 9, 7, 9, 30)),
        ("070926 930", datetime(2026, 9, 7, 9, 30)),
        ("07092026 0930", datetime(2026, 9, 7, 9, 30)),
        ("07.09.2026 09:30", datetime(2026, 9, 7, 9, 30)),
        ("07.09.2026 09:30:45", datetime(2026, 9, 7, 9, 30, 45)),
    ],
)
def test_combined_datetime_contract(raw: str, expected: datetime) -> None:
    assert parse_combined_input(raw, previous=None, now=NOW).value == expected


def test_combined_time_only_inherits_date_and_increment_rolls_midnight() -> None:
    previous = datetime(2026, 9, 7, 23, 50)
    assert parse_combined_input("930", previous=previous, now=NOW).value == datetime(
        2026, 9, 7, 9, 30
    )
    assert parse_combined_input("09:30", previous=previous, now=NOW).value == datetime(
        2026, 9, 7, 9, 30
    )
    assert parse_combined_input("09:30:45", previous=previous, now=NOW).value == datetime(
        2026, 9, 7, 9, 30, 45
    )
    assert parse_combined_input("+20", previous=previous, now=NOW).value == datetime(
        2026, 9, 8, 0, 10
    )
    with pytest.raises(QuickInputError):
        parse_combined_input("930", previous=None, now=NOW)


def test_generation_accumulation_uses_fact_date_and_replaces_same_report_date() -> None:
    assert accumulate_generation(100, 5, date(2026, 10, 1), None, 0) == (105, date(2026, 9, 30))
    assert accumulate_generation(105, 7, date(2026, 10, 1), date(2026, 10, 1), 5) == (
        107,
        date(2026, 9, 30),
    )
    assert accumulate_generation(999, 8, date(2026, 10, 2), date(2026, 10, 1), 7) == (
        8,
        date(2026, 10, 1),
    )
