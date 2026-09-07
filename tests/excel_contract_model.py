"""Executable Excel VBA contract model used by tests; this is not production code."""

from datetime import date, datetime, time, timedelta

_EXCEL_EPOCH = datetime(1899, 12, 30)


def excel_numeric_date(value: int, today: date) -> date:
    """Model VBA's serial-first handling of numeric date cells."""
    serial_floor = (date(1990, 1, 1) - _EXCEL_EPOCH.date()).days
    serial_ceiling = (today.replace(year=today.year + 10) - _EXCEL_EPOCH.date()).days
    if serial_floor <= value <= serial_ceiling:
        return (_EXCEL_EPOCH + timedelta(days=value)).date()
    compact = f"{value:06d}"
    return date(2000 + int(compact[4:]), int(compact[2:4]), int(compact[:2]))


def strict_colon_time(token: str) -> time:
    """Model VBA's digits-only colon components, including explicit seconds."""
    pieces = token.split(":")
    if len(pieces) not in (2, 3) or any(not piece.isdigit() for piece in pieces):
        raise ValueError(token)
    hour, minute = (int(piece) for piece in pieces[:2])
    second = int(pieces[2]) if len(pieces) == 3 else 0
    return time(hour, minute, second)


def combined_time(previous: datetime, token: str) -> datetime:
    return datetime.combine(previous.date(), strict_colon_time(token))


def accumulate_generation(
    current_month: float,
    daily: float,
    report_date: date,
    previous_report_date: date | None,
    previous_daily: float,
) -> tuple[float, date]:
    """Model VBA's reset/add/replace generation accumulator contract."""
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
