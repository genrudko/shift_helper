"""Pure planning logic for applying Shift-Helper quick input to Calc selections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from shift_helper.core.quick_input import normalize_date_paste, normalize_time_paste

DATE_COLUMNS = frozenset({1, 8})  # B, I (zero-based)
TIME_COLUMNS = frozenset({2, 9})  # C, J (zero-based)
PAIRED_DATE_COLUMN = {2: 1, 9: 8}
HEADER_ROW = 0

IssueSeverity = Literal["error", "warning"]
WriteKind = Literal["date", "time"]


class CalcSelectionError(ValueError):
    """Raised when the active Calc selection is outside the supported contract."""


@dataclass(frozen=True, slots=True)
class CellWrite:
    row: int
    column: int
    value: date | time
    kind: WriteKind


@dataclass(frozen=True, slots=True)
class CellIssue:
    row: int
    column: int
    severity: IssueSeverity
    message: str


@dataclass(frozen=True, slots=True)
class SelectionPlan:
    writes: tuple[CellWrite, ...]
    issues: tuple[CellIssue, ...]

    @property
    def changed_cells(self) -> int:
        return len(self.writes)

    @property
    def errors(self) -> tuple[CellIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[CellIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")


def validate_vertical_selection(
    *, start_row: int, end_row: int, start_column: int, end_column: int
) -> None:
    if start_column != end_column:
        raise CalcSelectionError("Выделите ячейки только одного столбца.")
    if start_row < 0 or end_row < start_row:
        raise CalcSelectionError("Некорректный диапазон выделения.")
    if start_row <= HEADER_ROW:
        raise CalcSelectionError("Строка заголовков не обрабатывается.")


def plan_date_selection(
    *,
    start_row: int,
    column: int,
    raw_values: list[object],
    previous_above: date | None,
    today: date,
) -> SelectionPlan:
    if column not in DATE_COLUMNS:
        raise CalcSelectionError("Дата поддерживается только в столбцах B и I.")
    if start_row <= HEADER_ROW:
        raise CalcSelectionError("Строка заголовков не обрабатывается.")

    results = normalize_date_paste(raw_values, previous_above=previous_above, today=today)
    writes: list[CellWrite] = []
    issues: list[CellIssue] = []
    for offset, result in enumerate(results):
        row = start_row + offset
        if result.error:
            issues.append(CellIssue(row, column, "error", result.error))
        elif isinstance(result.value, date):
            writes.append(CellWrite(row, column, result.value, "date"))
    return SelectionPlan(tuple(writes), tuple(issues))


def plan_time_selection(
    *,
    start_row: int,
    column: int,
    raw_values: list[object],
    previous_above: time | None,
    paired_dates: list[date | None],
    now: datetime,
) -> SelectionPlan:
    if column not in TIME_COLUMNS:
        raise CalcSelectionError("Время поддерживается только в столбцах C и J.")
    if start_row <= HEADER_ROW:
        raise CalcSelectionError("Строка заголовков не обрабатывается.")
    if len(raw_values) != len(paired_dates):
        raise ValueError("Количество значений времени и парных дат должно совпадать.")

    results = normalize_time_paste(raw_values, previous_above=previous_above, now=now)
    writes: list[CellWrite] = []
    issues: list[CellIssue] = []
    date_column = PAIRED_DATE_COLUMN[column]

    for offset, result in enumerate(results):
        row = start_row + offset
        if result.error:
            issues.append(CellIssue(row, column, "error", result.error))
            continue
        if not isinstance(result.value, time):
            continue

        writes.append(CellWrite(row, column, result.value, "time"))
        if result.day_offset:
            paired_date = paired_dates[offset]
            if paired_date is None:
                issues.append(
                    CellIssue(
                        row,
                        date_column,
                        "warning",
                        "Время перешло через полночь, но парная дата не заполнена.",
                    )
                )
            else:
                writes.append(
                    CellWrite(
                        row,
                        date_column,
                        paired_date + timedelta(days=result.day_offset),
                        "date",
                    )
                )

    return SelectionPlan(tuple(writes), tuple(issues))
