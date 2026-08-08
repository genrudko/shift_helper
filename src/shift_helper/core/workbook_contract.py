"""Cross-platform workbook facts shared by Calc and Excel adapters."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

JOURNAL_SHEET = "ЖС"
PREP_SHEET = "Подготовка рапорта"
INPUT_MAIN = "Ввод - Основные"
INPUT_OUTAGES = "Ввод - Аварийные отключения"
INPUT_COMMANDS = "Ввод - Команды"
INPUT_VIOLATIONS = "Ввод - Нарушения"
INPUT_STATE = "Ввод - Состояние ВЭУ"
INPUT_WORKS = "Ввод - Работы"
INPUT_DEFECTS = "Ввод - Дефекты"
INSPECTION_SHEET = "График осмотров КТП"

REPORT_SHEETS = (
    "Основные данные",
    "Аварийные отключения ЛЭП",
    "Команды по внешней инициативе",
    "Нарушения ОТиПБ + Экология",
    "Состояние ВЭУ",
    "Запланированные работы",
    "Дефекты оборудования",
)
INPUT_SHEETS = (
    INPUT_MAIN,
    INPUT_OUTAGES,
    INPUT_COMMANDS,
    INPUT_VIOLATIONS,
    INPUT_STATE,
    INPUT_WORKS,
    INPUT_DEFECTS,
)
REPORT_TO_INPUT = dict(zip(REPORT_SHEETS, INPUT_SHEETS, strict=True))

REPORT_DATE_CELL = "B3"
REPORT_OFFSET_CELL = "B6"
REPORT_WINDOW_HOUR = 7
WTG_COUNT = 84
WTG_STATUSES = ("Работа", "Останов", "Авария", "Ремонт")
WTG_STATUS_COLUMN = "L"
WTG_STATE_FIRST_ROW = 4
WTG_STATE_SCAN_LAST_ROW = 98
AVERAGE_LOAD_FORMULA = "=IFERROR(C10/24000,0)"
APPROVED_REPORT_TEMPLATE_SHA256 = (
    "cde2d2fb042f27dc514f71ac991676e423dd6a68667fbb6d3f928ab610acbb32"
)

# Report-output timestamps only. The source journal keeps local factual time.
REPORT_TIMESTAMP_COLUMNS: dict[str, tuple[str, ...]] = {
    REPORT_SHEETS[1]: ("C", "F"),
    REPORT_SHEETS[2]: ("E", "F"),
    REPORT_SHEETS[3]: ("D",),
    REPORT_SHEETS[4]: ("J", "K"),
    REPORT_SHEETS[5]: ("I", "J"),
    REPORT_SHEETS[6]: ("C", "I", "J"),
}


@dataclass(frozen=True, slots=True)
class ReportWindow:
    start: datetime
    end: datetime

    def contains(self, value: datetime) -> bool:
        return self.start <= value < self.end


def report_window(report_date: date) -> ReportWindow:
    """Return the accepted previous-day 07:00 -> report-day 07:00 window."""

    end = datetime.combine(report_date, time(REPORT_WINDOW_HOUR))
    return ReportWindow(start=end - timedelta(days=1), end=end)


def average_load_mw(daily_generation_kwh: float) -> float:
    """Convert previous-day kWh to the accepted 24-hour mean MW."""

    return float(daily_generation_kwh) / 24_000.0


def available_power_mw(setpoint_mw: float, repair_mw: float) -> float:
    """Return the accepted per-WTG available-power value."""

    return max(float(setpoint_mw) - float(repair_mw), 0.0)


def remaining_month_hours(report_date: date) -> int:
    """Hours from 00:00 of report date through the end of its month."""

    days = monthrange(report_date.year, report_date.month)[1]
    return (days - report_date.day + 1) * 24


def required_remaining_mean_power_kw(
    monthly_plan_kwh: float,
    month_generation_kwh: float,
    report_date: date,
) -> float:
    """Match the accepted C15 semantics, including the -1 ahead-of-plan sentinel."""

    balance = float(monthly_plan_kwh) - float(month_generation_kwh)
    if balance <= 0:
        return -1.0
    return balance / remaining_month_hours(report_date)


def plan_to_elapsed_days_kwh(monthly_plan_kwh: float, report_date: date) -> float:
    """Plan through fully elapsed days before the report date."""

    days = monthrange(report_date.year, report_date.month)[1]
    return float(monthly_plan_kwh) * (report_date.day - 1) / days


def shifted_report_timestamp(value: datetime, offset_hours: float) -> datetime:
    """Apply the report-output-only offset without altering source values."""

    return value + timedelta(hours=float(offset_hours))
