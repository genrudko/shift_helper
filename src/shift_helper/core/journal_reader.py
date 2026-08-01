"""Read the operational event journal without modifying the source workbook."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .events import JournalEvent, JournalReadResult, ValidationIssue
from .ooxml_reader import OOXMLReadError, StreamingWorkbook

JOURNAL_SHEET = "ЖС"
EXPECTED_HEADERS = {
    "B": "Дата останова ВЭУ",
    "C": "Время останова ВЭУ",
    "D": "№ ВЭУ",
    "E": "Описание",
    "F": "Причины возникновения",
    "I": "Дата пуска ВЭУ",
}
READ_COLUMNS = {"B", "C", "D", "E", "F", "I", "J"}
EXPECTED_KINDS = {"B": "date", "C": "time", "I": "date", "J": "time"}
_ASSET_RE = re.compile(r"(?i)(?:ВЭУ\s*[-№]?\s*)?(\d+)$")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean_text(value: object) -> str:
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
    if isinstance(value, timedelta):
        seconds = int(value.total_seconds()) % (24 * 60 * 60)
        return time(seconds // 3600, (seconds % 3600) // 60)
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
        return int(value) if value > 0 else None
    match = _ASSET_RE.fullmatch(str(value).strip())
    if match:
        number = int(match.group(1))
        return number if number > 0 else None
    return None


def _row_has_operational_data(values: dict[str, object]) -> bool:
    return any(values.get(column) not in (None, "") for column in READ_COLUMNS)


def _header_issues(values: dict[str, object]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for column, expected in EXPECTED_HEADERS.items():
        actual = _clean_text(values.get(column))
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
    actual_j = _clean_text(values.get("J"))
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


def read_event_journal(path: str | Path) -> JournalReadResult:
    """Stream valid event rows from `ЖС`; no workbook part is modified."""

    source = Path(path).resolve()
    result = JournalReadResult(source_sha256=file_sha256(source), source_name=source.name)
    try:
        with StreamingWorkbook(source) as workbook:
            for row, values in workbook.rows(
                JOURNAL_SHEET,
                columns=READ_COLUMNS,
                expected_kinds=EXPECTED_KINDS,
            ):
                if row == 1:
                    result.issues.extend(_header_issues(values))
                    continue
                if not _row_has_operational_data(values):
                    continue

                start_date = values.get("B")
                start_time = values.get("C")
                asset_raw = values.get("D")
                description = _clean_text(values.get("E"))
                reason = _clean_text(values.get("F"))
                end_date = values.get("I")
                end_time = values.get("J")

                started_at = _combine(start_date, start_time)
                asset_number = _asset_number(asset_raw)
                row_errors: list[ValidationIssue] = []
                if started_at is None:
                    row_errors.append(
                        ValidationIssue(
                            code="journal.row.invalid_start",
                            severity="error",
                            message=(
                                "Дата и время отключения должны быть числовыми "
                                "значениями Excel."
                            ),
                            row=row,
                            column="B:C",
                        )
                    )
                if asset_number is None:
                    row_errors.append(
                        ValidationIssue(
                            code="journal.row.invalid_asset",
                            severity="error",
                            message="Не удалось определить номер ВЭУ.",
                            row=row,
                            column="D",
                        )
                    )
                if not description:
                    row_errors.append(
                        ValidationIssue(
                            code="journal.row.missing_description",
                            severity="warning",
                            message="Описание события не заполнено.",
                            row=row,
                            column="E",
                        )
                    )

                has_end_date = end_date not in (None, "")
                has_end_time = end_time not in (None, "")
                ended_at: datetime | None = None
                if has_end_date != has_end_time:
                    row_errors.append(
                        ValidationIssue(
                            code="journal.row.partial_end",
                            severity="error",
                            message="Дата и время включения должны быть заполнены вместе.",
                            row=row,
                            column="I:J",
                        )
                    )
                elif has_end_date and has_end_time:
                    ended_at = _combine(end_date, end_time)
                    if ended_at is None:
                        row_errors.append(
                            ValidationIssue(
                                code="journal.row.invalid_end",
                                severity="error",
                                message=(
                                    "Дата и время включения должны быть числовыми "
                                    "значениями Excel."
                                ),
                                row=row,
                                column="I:J",
                            )
                        )
                    elif started_at is not None and ended_at < started_at:
                        row_errors.append(
                            ValidationIssue(
                                code="journal.row.end_before_start",
                                severity="error",
                                message="Время включения раньше времени отключения.",
                                row=row,
                                column="I:J",
                            )
                        )

                result.issues.extend(row_errors)
                if any(issue.severity == "error" for issue in row_errors):
                    result.ignored_rows.append(row)
                    continue
                assert started_at is not None and asset_number is not None
                result.events.append(
                    JournalEvent(
                        source_row=row,
                        started_at=started_at,
                        asset_number=asset_number,
                        description=description,
                        reason=reason,
                        ended_at=ended_at,
                    )
                )
    except OOXMLReadError as exc:
        result.issues.append(
            ValidationIssue(
                code="journal.workbook.invalid",
                severity="error",
                message=str(exc),
            )
        )
        return result

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
