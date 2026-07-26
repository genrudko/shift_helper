"""Domain rules shared by the Shift-Helper event journal."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from .models import Event

EVENT_TYPE_CHOICES: tuple[tuple[str, str], ...] = (
    ("emergency_stop", "Аварийный останов"),
    ("work_stop", "Останов для работ"),
    ("power_limit", "Ограничение выдачи мощности"),
    ("rotor_limit", "Ограничение по оборотам"),
    ("dispatch_command", "Диспетчерская команда"),
    ("startup", "Пуск"),
    ("restoration", "Восстановление режима"),
    ("other", "Другое"),
)
EVENT_TYPE_KEYS = {key for key, _label in EVENT_TYPE_CHOICES}


class EventValidationError(ValueError):
    """Raised when an event form contains invalid operational data."""


def _text(values: Mapping[str, object], key: str) -> str:
    value = values.get(key, "")
    return "" if value is None else str(value).strip()


def parse_local_datetime(value: str, *, field_label: str) -> datetime:
    """Parse an HTML datetime-local value."""
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise EventValidationError(f"Поле «{field_label}» заполнено неверно.") from exc


def parse_journal_date(
    value: str,
    *,
    field_label: str,
    required: bool,
    current: datetime | None = None,
) -> date | None:
    """Parse compact operator-facing dates used by the inline journal."""
    cleaned = value.strip()
    if not cleaned:
        if required:
            raise EventValidationError(f"Заполните поле «{field_label}».")
        return None

    now = current or datetime.now()
    if cleaned == "!":
        return now.date()

    digit_value = "".join(character for character in cleaned if character.isdigit())
    candidates: list[tuple[str, str]] = [
        (cleaned, "%d.%m.%Y"),
        (cleaned, "%Y-%m-%d"),
        (cleaned, "%d.%m.%y"),
    ]
    if len(digit_value) == 4:
        candidates.append((f"{digit_value}{now.year}", "%d%m%Y"))
    elif len(digit_value) == 6:
        candidates.append((digit_value, "%d%m%y"))
    elif len(digit_value) == 8:
        candidates.append((digit_value, "%d%m%Y"))

    for candidate, pattern in candidates:
        try:
            return datetime.strptime(candidate, pattern).date()
        except ValueError:
            continue
    raise EventValidationError(f"Поле «{field_label}» заполнено неверно.")


def parse_journal_time(
    value: str,
    *,
    field_label: str,
    required: bool,
    current: datetime | None = None,
) -> time | None:
    """Parse compact operator-facing times used by the inline journal."""
    cleaned = value.strip()
    if not cleaned:
        if required:
            raise EventValidationError(f"Заполните поле «{field_label}».")
        return None

    now = current or datetime.now()
    if cleaned == "!":
        return now.time().replace(second=0, microsecond=0)

    digits = "".join(character for character in cleaned if character.isdigit())
    if cleaned.isdigit() and len(digits) in {3, 4}:
        cleaned = digits.zfill(4)
        cleaned = f"{cleaned[:2]}:{cleaned[2:]}"

    try:
        return datetime.strptime(cleaned, "%H:%M").time()
    except ValueError as exc:
        raise EventValidationError(f"Поле «{field_label}» заполнено неверно.") from exc


def parse_optional_decimal(value: str, *, field_label: str) -> Decimal | None:
    """Parse an optional decimal accepting comma and dot separators."""
    cleaned = value.strip().replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned).quantize(Decimal("0.001"))
    except InvalidOperation as exc:
        raise EventValidationError(f"Поле «{field_label}» должно быть числом.") from exc


def parse_rotor_limit(value: str) -> Decimal | None:
    """Parse a decimal rotor limit accepting both comma and dot separators."""
    cleaned = value.strip().replace(",", ".")
    if not cleaned:
        return None

    try:
        limit = Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise EventValidationError("Ограничение по оборотам должно быть числом.") from exc

    if limit <= Decimal("0") or limit > Decimal("1"):
        raise EventValidationError("Ограничение по оборотам должно быть больше 0 и не больше 1.")
    return limit


def calculate_repair_power_mw(rotor_limit: Decimal | None) -> Decimal | None:
    """Return the approved repair-power value for a rotor-speed limitation."""
    if rotor_limit is None:
        return None

    limit = rotor_limit.quantize(Decimal("0.01"))
    if limit >= Decimal("0.95"):
        return Decimal("0.00")
    if limit == Decimal("0.90"):
        return Decimal("0.55")
    if limit == Decimal("0.85"):
        return Decimal("0.75")
    if limit == Decimal("0.80"):
        return Decimal("1.00")
    if limit == Decimal("0.75"):
        return Decimal("1.20")
    if limit == Decimal("0.70"):
        return Decimal("1.40")
    if limit < Decimal("0.70"):
        return Decimal("2.50")
    return Decimal("0.45")


def event_values_from_form(form: Mapping[str, str]) -> dict[str, object]:
    """Validate and normalize the legacy full-page event form."""
    asset_label = form.get("asset_label", "").strip()
    description = form.get("description", "").strip()
    event_type = form.get("event_type", "").strip()

    if not asset_label:
        raise EventValidationError("Укажите оборудование или ВЭУ.")
    if not description:
        raise EventValidationError("Укажите описание события.")
    if event_type not in EVENT_TYPE_KEYS:
        raise EventValidationError("Выберите допустимый тип события.")

    rotor_limit = parse_rotor_limit(form.get("rotor_limit", ""))
    return {
        "start_at": parse_local_datetime(
            form.get("start_at", ""),
            field_label="Дата и время начала",
        ),
        "asset_label": asset_label,
        "event_type": event_type,
        "description": description,
        "reason": form.get("reason", "").strip() or None,
        "actions": form.get("actions", "").strip() or None,
        "performer": form.get("performer", "").strip() or None,
        "error_codes": form.get("error_codes", "").strip() or None,
        "rotor_limit": rotor_limit,
        "repair_power_mw": calculate_repair_power_mw(rotor_limit),
        "include_in_report": form.get("include_in_report") == "on",
    }


def event_values_from_row(
    values: Mapping[str, object],
    *,
    existing_event: Event | None = None,
    current: datetime | None = None,
) -> dict[str, object]:
    """Validate and normalize one Excel-like inline journal row."""
    now = current or datetime.now()
    start_date = parse_journal_date(
        _text(values, "start_date"),
        field_label="Дата останова",
        required=True,
        current=now,
    )
    start_time = parse_journal_time(
        _text(values, "start_time"),
        field_label="Время останова",
        required=True,
        current=now,
    )
    assert start_date is not None
    assert start_time is not None
    start_at = datetime.combine(start_date, start_time)

    asset_label = _text(values, "asset_label")
    description = _text(values, "description")
    if not asset_label:
        raise EventValidationError("Заполните поле «№ ВЭУ / оборудование».")
    if not description:
        raise EventValidationError("Заполните поле «Описание события».")

    end_date_text = _text(values, "end_date")
    end_time_text = _text(values, "end_time")
    if bool(end_date_text) != bool(end_time_text):
        raise EventValidationError("Дата и время пуска должны быть заполнены вместе.")

    end_at: datetime | None = None
    if end_date_text and end_time_text:
        end_date = parse_journal_date(
            end_date_text,
            field_label="Дата пуска",
            required=True,
            current=now,
        )
        end_time = parse_journal_time(
            end_time_text,
            field_label="Время пуска",
            required=True,
            current=now,
        )
        assert end_date is not None
        assert end_time is not None
        end_at = datetime.combine(end_date, end_time)
        if end_at < start_at:
            raise EventValidationError("Дата и время пуска не могут быть раньше останова.")

    return {
        "start_at": start_at,
        "asset_label": asset_label,
        "event_type": existing_event.event_type if existing_event else "other",
        "description": description,
        "reason": _text(values, "reason") or None,
        "actions": _text(values, "actions") or None,
        "performer": _text(values, "performer") or None,
        "author": _text(values, "author") or None,
        "losses_mwh": parse_optional_decimal(
            _text(values, "losses_mwh"),
            field_label="Потери",
        ),
        "end_at": end_at,
        "status": "closed" if end_at else "open",
        "include_in_report": (
            existing_event.include_in_report if existing_event else True
        ),
    }


def format_downtime(start_at: datetime, end_at: datetime | None) -> str:
    """Format event downtime compactly for the journal table."""
    if end_at is None:
        return ""
    total_minutes = int((end_at - start_at).total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours} ч {minutes} мин"
    if hours:
        return f"{hours} ч"
    return f"{minutes} мин"


def event_to_row(event: Event) -> dict[str, object]:
    """Serialize a persisted event for the inline table."""
    return {
        "id": event.id,
        "start_date": event.start_at.strftime("%d.%m.%Y"),
        "start_time": event.start_at.strftime("%H:%M"),
        "asset_label": event.asset_label,
        "description": event.description,
        "reason": event.reason or "",
        "actions": event.actions or "",
        "performer": event.performer or "",
        "end_date": event.end_at.strftime("%d.%m.%Y") if event.end_at else "",
        "end_time": event.end_at.strftime("%H:%M") if event.end_at else "",
        "downtime": format_downtime(event.start_at, event.end_at),
        "author": event.author or "",
        "losses_mwh": "" if event.losses_mwh is None else str(event.losses_mwh),
        "status": event.status,
        "revision": event.revision,
    }


def event_values_for_form(event: Event) -> dict[str, str]:
    """Convert a persisted event into values suitable for an HTML form."""
    return {
        "start_at": event.start_at.strftime("%Y-%m-%dT%H:%M"),
        "asset_label": event.asset_label,
        "event_type": event.event_type,
        "description": event.description,
        "reason": event.reason or "",
        "actions": event.actions or "",
        "performer": event.performer or "",
        "error_codes": event.error_codes or "",
        "rotor_limit": "" if event.rotor_limit is None else str(event.rotor_limit),
        "include_in_report": "on" if event.include_in_report else "",
    }
