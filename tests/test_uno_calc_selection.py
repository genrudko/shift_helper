from datetime import date, datetime, time

import pytest

from shift_helper.uno_adapter.calc_selection import (
    CalcSelectionError,
    plan_date_selection,
    plan_time_selection,
    validate_vertical_selection,
)


def test_date_selection_preserves_bad_tokens_and_continues() -> None:
    plan = plan_date_selection(
        start_row=1,
        column=1,
        raw_values=[".", "+1", "3102", "0708"],
        previous_above=date(2026, 8, 1),
        today=date(2026, 8, 1),
    )
    assert [(write.row, write.value) for write in plan.writes] == [
        (1, date(2026, 8, 1)),
        (2, date(2026, 8, 2)),
        (4, date(2026, 8, 7)),
    ]
    assert len(plan.errors) == 1
    assert plan.errors[0].row == 3


def test_time_selection_applies_midnight_rollover_to_paired_date() -> None:
    plan = plan_time_selection(
        start_row=1,
        column=2,
        raw_values=[".", "+20"],
        previous_above=time(23, 50),
        paired_dates=[date(2026, 8, 1), date(2026, 8, 1)],
        now=datetime(2026, 8, 1, 20, 0),
    )
    assert [(write.row, write.column, write.value) for write in plan.writes] == [
        (1, 2, time(23, 50)),
        (2, 2, time(0, 10)),
        (2, 1, date(2026, 8, 2)),
    ]
    assert not plan.issues


def test_time_rollover_without_paired_date_is_visible() -> None:
    plan = plan_time_selection(
        start_row=2,
        column=9,
        raw_values=["+20"],
        previous_above=time(23, 50),
        paired_dates=[None],
        now=datetime(2026, 8, 1, 20, 0),
    )
    assert plan.changed_cells == 1
    assert len(plan.warnings) == 1
    assert plan.warnings[0].column == 8


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(start_row=1, end_row=2, start_column=1, end_column=2),
        dict(start_row=0, end_row=0, start_column=1, end_column=1),
    ],
)
def test_selection_contract_rejects_unsupported_ranges(kwargs: dict[str, int]) -> None:
    with pytest.raises(CalcSelectionError):
        validate_vertical_selection(**kwargs)


def test_column_contract_is_explicit() -> None:
    with pytest.raises(CalcSelectionError):
        plan_date_selection(
            start_row=1,
            column=3,
            raw_values=["!"],
            previous_above=None,
            today=date(2026, 8, 1),
        )
    with pytest.raises(CalcSelectionError):
        plan_time_selection(
            start_row=1,
            column=3,
            raw_values=["!"],
            previous_above=None,
            paired_dates=[date(2026, 8, 1)],
            now=datetime(2026, 8, 1, 20, 0),
        )
