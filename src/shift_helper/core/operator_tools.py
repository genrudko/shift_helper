"""Pure helpers for Shift-Helper operator macros migrated from legacy VBA."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

_SPACE_RE = re.compile(r"[\t\r\n\u00a0 ]+")
_CELL_REF_RE = re.compile(
    r"(?<![A-Z0-9_])(?P<col>\$?[A-Z]{1,3})(?P<row>\$?\d+)(?![A-Z0-9_])"
)
_LIMIT_RE = re.compile(r"0[.,]\d{1,2}")
_WTG_RE = re.compile(r"(?:ВЭУ[-\s]*)?(\d{1,3})", re.IGNORECASE)


def normalize_spaces(value: object) -> str:
    """Collapse tabs, line breaks, NBSP and repeated spaces to one space."""

    return _SPACE_RE.sub(" ", str(value or "")).strip()


def merge_nonempty(values: Iterable[object]) -> str:
    """Join non-empty cell values in row-major order with single spaces."""

    return " ".join(text for value in values if (text := normalize_spaces(value)))


def russian_year_word(number: int) -> str:
    """Return the grammatically correct Russian word for a year count."""

    number = abs(int(number))
    last_digit = number % 10
    last_two = number % 100
    if last_digit == 1 and last_two != 11:
        return "год"
    if 2 <= last_digit <= 4 and not 12 <= last_two <= 14:
        return "года"
    return "лет"


def parse_wtg_numbers(
    raw: str,
    *,
    minimum: int = 1,
    maximum: int = 84,
) -> list[int]:
    """Parse comma/semicolon/space separated WTG identifiers without duplicates."""

    tokens = re.split(r"[,;\s]+", str(raw).strip())
    result: list[int] = []
    seen: set[int] = set()
    for token in tokens:
        if not token:
            continue
        match = _WTG_RE.fullmatch(token)
        if match is None:
            raise ValueError(
                f"Не удалось распознать номер ВЭУ: {token!r}."
            )
        number = int(match.group(1))
        if number < minimum or number > maximum:
            raise ValueError(
                "Номер ВЭУ должен быть в диапазоне "
                f"{minimum}–{maximum}: {number}."
            )
        if number not in seen:
            result.append(number)
            seen.add(number)
    if not result:
        raise ValueError("Не указаны номера ВЭУ.")
    return result


def maintenance_text(
    wtg_number: int,
    *,
    half_year: bool = False,
    years: int | None = None,
    bolt_torque_check: bool = False,
) -> str:
    """Build the accepted WTG maintenance wording from the legacy macro."""

    number = int(wtg_number)
    if half_year:
        return (
            f"ВЭУ-{number}: базовая платформа, гондола, ступица - "
            "Техническое обслуживание ВЭУ в объеме ТО-6 месяцев "
            "за исключением работ на токоведущих частях в конвертере "
            f"К-1-{number}, конвертере К-2-{number}, ВРУ-0,69, "
            "технический осмотр системы охлаждения конвертера "
            f"К-1-{number} и конвертера К-2-{number} без проникновения "
            "за защитные ограждения."
        )
    if years is None or int(years) <= 0:
        raise ValueError("Количество лет ТО должно быть положительным.")
    years = int(years)
    years_text = f"{years} {russian_year_word(years)}"
    if bolt_torque_check:
        return (
            f"ВЭУ-{number}: базовая платформа, конвертер К-1-{number}, "
            f"конвертер К-2-{number}, ТСН ВЭУ-{number}, ВРУ-0,69 - "
            f"Техническое обслуживание ВЭУ в объеме ТО {years_text}, "
            "проверка моментов затяжки болтовых контактных соединений "
            f"в конвертере К-1-{number}, конвертере К-2-{number}, "
            f"ТСН ВЭУ-{number}, ВРУ-0,69."
        )
    return (
        f"ВЭУ-{number}: базовая платформа, гондола, ступица - "
        f"Техническое обслуживание ВЭУ в объеме ТО {years_text} "
        "за исключением работ на токоведущих частях в конвертере "
        f"К-1-{number}, конвертере К-2-{number}, ВРУ-0,69, "
        "технический осмотр системы охлаждения конвертера "
        f"К-1-{number} и конвертера К-2-{number} без проникновения "
        "за защитные ограждения."
    )


def extract_rotor_limit(text: object) -> float | None:
    """Extract a rotor-speed limitation such as 0,85 from an event description."""

    normalized = str(text or "").lower()
    match = _LIMIT_RE.search(normalized)
    if match is None:
        return None
    return float(match.group(0).replace(",", "."))


def rotor_repair_power(limit_value: float) -> float:
    """Return the accepted P-repair mapping from the VBA beta macro."""

    value = round(float(limit_value), 2)
    if value < 0.7:
        return 2.5
    if value >= 0.95:
        return 0.0
    mapping = {
        0.90: 0.55,
        0.85: 0.75,
        0.80: 1.0,
        0.75: 1.2,
        0.70: 1.4,
    }
    return mapping.get(value, 0.45)


@dataclass(frozen=True, slots=True)
class RotorLimitRecord:
    wtg_number: int
    limit_value: float
    event_time: datetime
    source_text: str


def active_rotor_limits(
    rows: Iterable[tuple[datetime, int, object]],
    *,
    end_time: datetime,
) -> dict[int, RotorLimitRecord]:
    """Resolve active rotor limits at ``end_time`` from chronological log rows."""

    active: dict[int, RotorLimitRecord] = {}
    for event_time, wtg_number, source in sorted(rows, key=lambda row: row[0]):
        if event_time >= end_time:
            continue
        text = str(source or "")
        lowered = text.lower()
        number = int(wtg_number)
        if "снято" in lowered and "огранич" in lowered:
            active.pop(number, None)
            continue
        if (
            "установлено ограничение" in lowered
            and "оборот" in lowered
            and (limit_value := extract_rotor_limit(lowered)) is not None
        ):
            active[number] = RotorLimitRecord(
                wtg_number=number,
                limit_value=limit_value,
                event_time=event_time,
                source_text=text,
            )
    return active


def absolute_a1_references(formula: str) -> str:
    """Make ordinary A1 references absolute before sorting selected rows."""

    source = str(formula or "")
    if not source.startswith("="):
        return source

    def replace(match: re.Match[str]) -> str:
        col = match.group("col").lstrip("$")
        row = match.group("row").lstrip("$")
        # Do not rewrite function-like names such as LOG10(...).
        suffix = source[match.end() :]
        if suffix.lstrip().startswith("("):
            return match.group(0)
        return f"${col}${row}"

    return _CELL_REF_RE.sub(replace, source)


def sort_key_for_time(value: object) -> tuple[int, float | str]:
    """Stable sort key for Calc values from a time column."""

    if value is None or value == "":
        return (2, "")
    if isinstance(value, (int, float)):
        return (0, float(value))
    text = str(value).strip()
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if match:
        hour, minute, second = (int(part or 0) for part in match.groups())
        return (0, hour * 3600 + minute * 60 + second)
    return (1, text.casefold())


def inspection_shift(now: datetime) -> tuple[str, str]:
    """Return legacy day/night shift code and caption."""

    minutes = now.hour * 60 + now.minute
    if 8 * 60 <= minutes < 20 * 60:
        return "Д", "с 08:00 до 20:00"
    return "Н", "с 20:00 до 08:00"


def inspection_message(
    now: datetime,
    assignments: Sequence[tuple[str, str, str | None]],
) -> str:
    """Format the operator message for the KTP inspection schedule."""

    shift, caption = inspection_shift(now)
    weekday_names = (
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
    )
    lines = [
        f"Сегодня ({now:%d.%m.%Y}, {weekday_names[now.weekday()]}, "
        f"смена {shift} {caption}) назначены:"
    ]
    for mk_number, ktp_number, note in assignments:
        line = f"М.К. {mk_number} > КТП {{{ktp_number}}}"
        if note:
            line += f" ({note})"
        lines.append(line)
    return "\n".join(lines)
