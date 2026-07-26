"""Domain rules shared by the Shift-Helper event journal."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping

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


def parse_local_datetime(value: str, *, field_label: str) -> datetime:
    """Parse an HTML datetime-local value."""
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise EventValidationError(f"Поле «{field_label}» заполнено неверно.") from exc


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
    """Validate and normalize form values for creating or updating an event."""
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


def event_values_for_form(event: object) -> dict[str, str]:
    """Convert a persisted event into values suitable for an HTML form."""
    rotor_limit = getattr(event, "rotor_limit", None)
    return {
        "start_at": getattr(event, "start_at").strftime("%Y-%m-%dT%H:%M"),
        "asset_label": getattr(event, "asset_label"),
        "event_type": getattr(event, "event_type"),
        "description": getattr(event, "description"),
        "reason": getattr(event, "reason") or "",
        "actions": getattr(event, "actions") or "",
        "performer": getattr(event, "performer") or "",
        "error_codes": getattr(event, "error_codes") or "",
        "rotor_limit": "" if rotor_limit is None else str(rotor_limit),
        "include_in_report": "on" if getattr(event, "include_in_report") else "",
    }
