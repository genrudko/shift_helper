from datetime import date, datetime, time

import pytest

from shift_helper.core.quick_input import (
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
        ("15:30:59", time(15, 30)),
    ],
)
def test_time_contract(raw: object, expected: time) -> None:
    assert parse_time_input(raw, previous=None, now=NOW).value == expected


def test_time_increment_reports_midnight_rollover() -> None:
    parsed = parse_time_input("+20", previous=time(23, 50), now=NOW)
    assert parsed.value == time(0, 10)
    assert parsed.day_offset == 1


@pytest.mark.parametrize("raw", ["24", "1260", "999", "15:99", "abc"])
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
