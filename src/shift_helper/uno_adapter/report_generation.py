"""Pure normalization helpers for Calc-driven morning-report generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Iterable, Mapping

from shift_helper.core.events import JournalEvent, ValidationIssue

JOURNAL_SHEET = "ЖС"
REPORT_SHEET = "Аварийные отключения ЛЭП"
EXPECTED_JOURNAL_HEADERS = {
    "B": "Дата останова ВЭУ",
    "C": "Время останова ВЭУ",
    "D": "№ ВЭУ",
    "E": "Описание",
    "F": "Причины возникновения",
    "I": "Дата пуска ВЭУ",
}
EXPECTED_REPORT_HEADERS = (
    "Диспетчерское наименование ЛЭП, ВЭУ и оборудования",
    "Дата, время отключения",
    "Причина",
    "Работа защит",
    "Дата, время включения в работу",
)
READ_COLUMNS = ("B", "C", "D", "E", "F", "I", "J")
_ASSET_RE = re.compile(r"(?i)(?:ВЭУ\s*[-№]?\s*)?(\d+)$")


@dataclass(slots=True)
class UnoJournalReadResult:
    events: list[JournalEvent] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    ignored_rows: list[int] = field(default_factory=list)

    @property
    def blocking_structure_errors(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "error" and (issue.row is None or issue.row == 1)
        ]


def parse_report_date(value: str) -> date:
    """Parse operator input in Russian display format or ISO format."""

    text = value.strip()
    for pattern in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise ValueError("Введите дату рапорта в формате ДД.ММ.ГГГГ.")


def default_report_filename(report_date: date) -> str:
    return f"Рапорт НСС Кочубеевская ВЭС от {report_date.isoformat()}.xlsx"


def update_report_title(title: str, report_date: date) -> str:
    replacement = report_date.strftime("%d.%m.%Y")
    if re.search(r"\d{2}\.\d{2}\.\d{4}", title):
        return re.sub(r"\d{2}\.\d{2}\.\d{4}", replacement, title, count=1)
    return title


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\u00a0", " ").split())


def _date_value(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _time_value(value: object) -> time | None:
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    return None


def _combine(date_raw: object, time_raw: object) -> datetime | None:
    day = _date_value(date_raw)
    clock = _time_value(time_raw)
    if day is None or clock is None:
        return None
    return datetime.combine(day, clock)


def _asset_number(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and value.is_integer():
        number = int(value)
        return number if number > 0 else None
    match = _ASSET_RE.fullmatch(str(value).strip())
    if match:
        number = int(match.group(1))
        return number if number > 0 else None
    return None


def row_has_operational_data(values: Mapping[str, object]) -> bool:
    return any(values.get(column) not in (None, "") for column in READ_COLUMNS)


def journal_header_issues(values: Mapping[str, object]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for column, expected in EXPECTED_JOURNAL_HEADERS.items():
        actual = clean_text(values.get(column))
        if column == "D" and actual != expected:
            issues.append(
                ValidationIssue(
                    code="journal.header.asset_mismatch",
                    severity="warning",
                    message=f"Ожидался заголовок {expected!r}, фактически {actual!r}.",
                    row=1,
                    column="D",
                )
            )
        elif actual != expected:
            issues.append(
                ValidationIssue(
                    code="journal.header.mismatch",
                    severity="error",
                    message=f"{column}1: ожидалось {expected!r}, фактически {actual!r}.",
                    row=1,
                    column=column,
                )
            )
    actual_j = clean_text(values.get("J"))
    if not actual_j.startswith("Время пуска ВЭУ"):
        issues.append(
            ValidationIssue(
                code="journal.header.mismatch",
                severity="error",
                message=f"J1: неожиданный заголовок {actual_j!r}.",
                row=1,
                column="J",
            )
        )
    return issues


def normalize_event_row(
    source_row: int,
    values: Mapping[str, object],
) -> tuple[JournalEvent | None, list[ValidationIssue]]:
    started_at = _combine(values.get("B"), values.get("C"))
    asset_number = _asset_number(values.get("D"))
    description = clean_text(values.get("E"))
    reason = clean_text(values.get("F"))
    end_date = values.get("I")
    end_time = values.get("J")

    issues: list[ValidationIssue] = []
    if started_at is None:
        issues.append(
            ValidationIssue(
                code="journal.row.invalid_start",
                severity="error",
                message="Дата и время отключения должны быть числовыми значениями Excel.",
                row=source_row,
                column="B:C",
            )
        )
    if asset_number is None:
        issues.append(
            ValidationIssue(
                code="journal.row.invalid_asset",
                severity="error",
                message="Не удалось определить номер ВЭУ.",
                row=source_row,
                column="D",
            )
        )
    if not description:
        issues.append(
            ValidationIssue(
                code="journal.row.missing_description",
                severity="warning",
                message="Описание события не заполнено.",
                row=source_row,
                column="E",
            )
        )

    has_end_date = end_date not in (None, "")
    has_end_time = end_time not in (None, "")
    ended_at: datetime | None = None
    if has_end_date != has_end_time:
        issues.append(
            ValidationIssue(
                code="journal.row.partial_end",
                severity="error",
                message="Дата и время включения должны быть заполнены вместе.",
                row=source_row,
                column="I:J",
            )
        )
    elif has_end_date and has_end_time:
        ended_at = _combine(end_date, end_time)
        if ended_at is None:
            issues.append(
                ValidationIssue(
                    code="journal.row.invalid_end",
                    severity="error",
                    message="Дата и время включения должны быть числовыми значениями Excel.",
                    row=source_row,
                    column="I:J",
                )
            )
        elif started_at is not None and ended_at < started_at:
            issues.append(
                ValidationIssue(
                    code="journal.row.end_before_start",
                    severity="error",
                    message="Время включения раньше времени отключения.",
                    row=source_row,
                    column="I:J",
                )
            )

    if any(issue.severity == "error" for issue in issues):
        return None, issues
    assert started_at is not None and asset_number is not None
    return (
        JournalEvent(
            source_row=source_row,
            started_at=started_at,
            asset_number=asset_number,
            description=description,
            reason=reason,
            ended_at=ended_at,
        ),
        issues,
    )


def _leading_outlier(events: list[JournalEvent]) -> int | None:
    if len(events) < 3:
        return None
    first, second, third = events[0], events[1], events[2]
    if (
        first.source_row == 2
        and first.started_at > second.started_at
        and second.started_at <= third.started_at
    ):
        return first.source_row
    return None


def read_uno_journal(
    *,
    headers: Mapping[str, object],
    rows: Iterable[tuple[int, Mapping[str, object]]],
) -> UnoJournalReadResult:
    result = UnoJournalReadResult()
    result.issues.extend(journal_header_issues(headers))
    for source_row, values in rows:
        if not row_has_operational_data(values):
            continue
        event, issues = normalize_event_row(source_row, values)
        result.issues.extend(issues)
        if event is None:
            result.ignored_rows.append(source_row)
        else:
            result.events.append(event)

    outlier = _leading_outlier(result.events)
    if outlier is not None:
        result.events = [event for event in result.events if event.source_row != outlier]
        result.ignored_rows.append(outlier)
        result.issues.append(
            ValidationIssue(
                code="journal.row.leading_chronology_outlier",
                severity="warning",
                message=(
                    "Первая строка данных исключена как известный перенос "
                    "вне основной хронологии."
                ),
                row=outlier,
            )
        )
    return result
