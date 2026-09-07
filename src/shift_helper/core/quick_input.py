"""Locale-independent parsing for Calc/Excel quick date and time input."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

_DATE_FORMATS = ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d")
_TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{1,2})(?::(?P<second>\d{1,2}))?$")
_PLUS_RE = re.compile(r"^\+(?P<amount>\d+)$")
_DIGITS_RE = re.compile(r"^\d+$")
_EXCEL_DATE_EPOCH = datetime(1899, 12, 30)
_OPERATIONAL_SERIAL_START = date(1990, 1, 1)
_OPERATIONAL_SERIAL_FUTURE_YEARS = 10


class QuickInputError(ValueError):
    """Raised when a quick-input token cannot be converted safely."""


@dataclass(frozen=True, slots=True)
class ParsedTime:
    value: time
    day_offset: int = 0


@dataclass(frozen=True, slots=True)
class ParsedDateTime:
    value: datetime
    explicit_seconds: bool = False


@dataclass(frozen=True, slots=True)
class BulkCellResult:
    value: date | time | None
    day_offset: int = 0
    error: str | None = None


def _text(raw: object) -> str:
    if isinstance(raw, str):
        return raw.strip()
    return str(raw).strip()


def _require_previous(previous: date | time | None, token: str) -> date | time:
    if previous is None:
        raise QuickInputError(f"Токен {token!r} требует предыдущего корректного значения выше.")
    return previous


def _strict_date(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise QuickInputError(f"Невозможная дата: {day:02d}.{month:02d}.{year:04d}.") from exc


def _plausible_operational_serial_bounds(today: date) -> tuple[int, int]:
    try:
        future = today.replace(year=today.year + _OPERATIONAL_SERIAL_FUTURE_YEARS)
    except ValueError:
        future = today.replace(year=today.year + _OPERATIONAL_SERIAL_FUTURE_YEARS, day=28)
    return (
        (_OPERATIONAL_SERIAL_START - _EXCEL_DATE_EPOCH.date()).days,
        (future - _EXCEL_DATE_EPOCH.date()).days,
    )


def _is_plausible_operational_excel_serial(numeric: float, today: date) -> bool:
    lower, upper = _plausible_operational_serial_bounds(today)
    return numeric.is_integer() and lower <= numeric <= upper


def parse_date_input(
    raw: object,
    *,
    previous: date | None,
    today: date,
) -> date:
    """Parse one date token without relying on OS or office-suite locale."""

    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw

    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        numeric = float(raw)
        # Numeric coercion loses provenance: if a compact DDMMYY integer also falls
        # inside the operational serial window, it cannot be distinguished from a
        # real Excel serial. Preserving the serial wins in that ambiguous case.
        if _is_plausible_operational_excel_serial(numeric, today):
            return (_EXCEL_DATE_EPOCH + timedelta(days=numeric)).date()
        if numeric.is_integer():
            compact = str(int(numeric)).zfill(6)
            if len(compact) == 6:
                try:
                    return _strict_date(
                        2000 + int(compact[4:6]), int(compact[2:4]), int(compact[0:2])
                    )
                except QuickInputError:
                    pass
        if 20_000 <= numeric <= 80_000:
            return (_EXCEL_DATE_EPOCH + timedelta(days=numeric)).date()

    token = _text(raw)
    if not token:
        raise QuickInputError("Дата не заполнена.")
    if token == ".":
        return _require_previous(previous, token)  # type: ignore[return-value]
    if token == "!":
        return today

    plus = _PLUS_RE.fullmatch(token)
    if plus:
        if int(plus.group("amount")) <= 0:
            raise QuickInputError("Приращение должно быть положительным целым числом.")
        base = _require_previous(previous, token)
        return base + timedelta(days=int(plus.group("amount")))  # type: ignore[operator]

    if any(separator in token for separator in (".", "/", "-")):
        for date_format in _DATE_FORMATS:
            try:
                parsed = datetime.strptime(token, date_format).date()
            except ValueError:
                continue
            if parsed.strftime(date_format) == token.zfill(len(parsed.strftime(date_format))):
                return parsed
            return parsed
        raise QuickInputError(f"Некорректная полная дата: {token!r}.")

    compact = token.replace(" ", "")
    if not _DIGITS_RE.fullmatch(compact):
        raise QuickInputError(f"Некорректная дата: {token!r}.")

    if len(compact) in (1, 2):
        return _strict_date(today.year, today.month, int(compact))
    if len(compact) == 4:
        return _strict_date(today.year, int(compact[2:4]), int(compact[0:2]))
    if len(compact) == 6:
        return _strict_date(2000 + int(compact[4:6]), int(compact[2:4]), int(compact[0:2]))
    if len(compact) == 8:
        return _strict_date(int(compact[4:8]), int(compact[2:4]), int(compact[0:2]))

    raise QuickInputError(f"Неподдерживаемый формат даты: {token!r}.")


def _strict_time(hour: int, minute: int, second: int = 0) -> time:
    try:
        return time(hour, minute, second)
    except ValueError as exc:
        raise QuickInputError(f"Невозможное время: {hour:02d}:{minute:02d}.") from exc


def _time_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def parse_time_input(
    raw: object,
    *,
    previous: time | None,
    now: datetime,
) -> ParsedTime:
    """Parse one time token and expose midnight rollover explicitly."""

    if isinstance(raw, datetime):
        return ParsedTime(raw.time().replace(second=0, microsecond=0))
    if isinstance(raw, time):
        return ParsedTime(raw.replace(second=0, microsecond=0))

    token = _text(raw)
    if not token:
        raise QuickInputError("Время не заполнено.")
    if token == ".":
        return ParsedTime(_require_previous(previous, token))  # type: ignore[arg-type]
    if token == "!":
        return ParsedTime(time(now.hour, now.minute))

    plus = _PLUS_RE.fullmatch(token)
    if plus:
        if int(plus.group("amount")) <= 0:
            raise QuickInputError("Приращение должно быть положительным целым числом.")
        base = _require_previous(previous, token)
        total = _time_minutes(base) + int(plus.group("amount"))  # type: ignore[arg-type]
        day_offset, minute_of_day = divmod(total, 24 * 60)
        return ParsedTime(time(minute_of_day // 60, minute_of_day % 60), day_offset)

    match = _TIME_RE.fullmatch(token)
    if match:
        second = int(match.group("second") or 0)
        if second > 59:
            raise QuickInputError(f"Невозможное время: {token!r}.")
        return ParsedTime(
            _strict_time(int(match.group("hour")), int(match.group("minute")), second)
        )

    compact = token.replace(" ", "")
    if not _DIGITS_RE.fullmatch(compact):
        raise QuickInputError(f"Некорректное время: {token!r}.")

    if len(compact) in (1, 2):
        return ParsedTime(_strict_time(int(compact), 0))
    if len(compact) == 3:
        return ParsedTime(_strict_time(int(compact[0]), int(compact[1:3])))
    if len(compact) == 4:
        return ParsedTime(_strict_time(int(compact[0:2]), int(compact[2:4])))

    raise QuickInputError(f"Неподдерживаемый формат времени: {token!r}.")


def is_stored_time(raw: object) -> bool:
    """Return whether an existing cell value is a real Excel time fraction."""

    if isinstance(raw, datetime | time):
        return True
    return isinstance(raw, (int, float)) and not isinstance(raw, bool) and 0 <= float(raw) < 1


def parse_combined_input(
    raw: object,
    *,
    previous: datetime | None,
    now: datetime,
) -> ParsedDateTime:
    """Parse a mapped combined date/time field without locale-dependent conversion."""

    if isinstance(raw, datetime):
        return ParsedDateTime(raw, raw.second != 0)
    token = _text(raw)
    if token == "!":
        return ParsedDateTime(now.replace(microsecond=0), now.second != 0)
    if token == ".":
        if previous is None:
            raise QuickInputError("Требуется предыдущее корректное значение выше.")
        return ParsedDateTime(previous, previous.second != 0)
    plus = _PLUS_RE.fullmatch(token)
    if plus:
        amount = int(plus.group("amount"))
        if amount <= 0:
            raise QuickInputError("Приращение должно быть положительным целым числом.")
        if previous is None:
            raise QuickInputError("Требуется предыдущее корректное значение выше.")
        return ParsedDateTime(previous + timedelta(minutes=amount), previous.second != 0)

    pieces = token.split()
    if len(pieces) == 1:
        if previous is None:
            raise QuickInputError("Время без даты требует предыдущего значения выше.")
        parsed_time = parse_time_input(pieces[0], previous=None, now=now).value
        return ParsedDateTime(datetime.combine(previous.date(), parsed_time))
    if len(pieces) != 2:
        raise QuickInputError(f"Некорректные дата и время: {token!r}.")

    parsed_date = parse_date_input(pieces[0], previous=None, today=now.date())
    time_token = pieces[1]
    parsed_time = parse_time_input(time_token, previous=None, now=now).value
    explicit_seconds = time_token.count(":") == 2
    if explicit_seconds:
        parsed_time = time.fromisoformat(time_token)
    return ParsedDateTime(datetime.combine(parsed_date, parsed_time), explicit_seconds)


def accumulate_generation(
    current_month: float,
    daily: float,
    report_date: date,
    previous_report_date: date | None,
    previous_daily: float,
) -> tuple[float, date]:
    """Accumulate a daily import in the month of report_date - 1 day."""

    fact_date = report_date - timedelta(days=1)
    if previous_report_date == report_date:
        return current_month + daily - previous_daily, fact_date
    previous_fact = previous_report_date - timedelta(days=1) if previous_report_date else None
    if previous_fact and (previous_fact.year, previous_fact.month) == (
        fact_date.year,
        fact_date.month,
    ):
        return current_month + daily, fact_date
    return daily, fact_date


def normalize_date_paste(
    values: Sequence[object],
    *,
    previous_above: date | None,
    today: date,
) -> list[BulkCellResult]:
    """Normalize a pasted date column sequentially without hiding bad cells."""

    previous = previous_above
    results: list[BulkCellResult] = []
    for raw in values:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            results.append(BulkCellResult(None))
            continue
        try:
            parsed = parse_date_input(raw, previous=previous, today=today)
        except QuickInputError as exc:
            results.append(BulkCellResult(None, error=str(exc)))
        else:
            previous = parsed
            results.append(BulkCellResult(parsed))
    return results


def normalize_time_paste(
    values: Sequence[object],
    *,
    previous_above: time | None,
    now: datetime,
) -> list[BulkCellResult]:
    """Normalize a pasted time column sequentially and retain rollover metadata."""

    previous = previous_above
    results: list[BulkCellResult] = []
    for raw in values:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            results.append(BulkCellResult(None))
            continue
        try:
            parsed = parse_time_input(raw, previous=previous, now=now)
        except QuickInputError as exc:
            results.append(BulkCellResult(None, error=str(exc)))
        else:
            previous = parsed.value
            results.append(BulkCellResult(parsed.value, day_offset=parsed.day_offset))
    return results
