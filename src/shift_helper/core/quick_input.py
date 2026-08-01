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


class QuickInputError(ValueError):
    """Raised when a quick-input token cannot be converted safely."""


@dataclass(frozen=True, slots=True)
class ParsedTime:
    value: time
    day_offset: int = 0


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

    token = _text(raw)
    if not token:
        raise QuickInputError("Дата не заполнена.")
    if token == ".":
        return _require_previous(previous, token)  # type: ignore[return-value]
    if token == "!":
        return today

    plus = _PLUS_RE.fullmatch(token)
    if plus:
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


def _strict_time(hour: int, minute: int) -> time:
    try:
        return time(hour, minute)
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
        base = _require_previous(previous, token)
        total = _time_minutes(base) + int(plus.group("amount"))  # type: ignore[arg-type]
        day_offset, minute_of_day = divmod(total, 24 * 60)
        return ParsedTime(time(minute_of_day // 60, minute_of_day % 60), day_offset)

    match = _TIME_RE.fullmatch(token)
    if match:
        second = int(match.group("second") or 0)
        if second > 59:
            raise QuickInputError(f"Невозможное время: {token!r}.")
        return ParsedTime(_strict_time(int(match.group("hour")), int(match.group("minute"))))

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
