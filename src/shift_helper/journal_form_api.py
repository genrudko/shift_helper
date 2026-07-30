"""Approved ЖС-form API for the Univer journal runtime.

The v2 API remains available for compatibility tests. The working UI uses this
contract because it exposes the original journal columns and reversible row
removal without leaking technical fields into the sheet.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import uuid4

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .audit_context import (
    bind_audit_context,
    current_audit_actor,
    current_audit_client_ip,
    reset_audit_context,
)
from .domain import (
    EVENT_TYPE_KEYS,
    EventValidationError,
    calculate_repair_power_mw,
    event_values_from_form,
    parse_local_datetime,
    parse_rotor_limit,
)
from .events import _v2_create_form_values
from .models import Event

journal_form_blueprint = Blueprint(
    "journal_form",
    __name__,
    url_prefix="/events/api/v3",
)

MAX_BATCH_OPERATIONS = 200
_DELETED_STATUS = "deleted"
_NULLABLE_TEXT_FIELDS = {
    "reason": "reason",
    "actions": "actions",
    "performer": "performer",
    "errorCodes": "error_codes",
}
_TEXT_FIELDS = {
    "assetLabel": "asset_label",
    "description": "description",
    **_NULLABLE_TEXT_FIELDS,
}


def _database_engine() -> Engine:
    return current_app.extensions["shift_helper_database_engine"]


def _api_error(
    code: str,
    message: str,
    *,
    status: int,
    **details: object,
) -> tuple[Response, int]:
    return jsonify({"error": {"code": code, "message": message, **details}}), status


def _positive_integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _parse_datetime(value: object, *, label: str) -> datetime:
    if not isinstance(value, str):
        raise EventValidationError(f"Поле «{label}» должно содержать дату и время.")
    return parse_local_datetime(value, field_label=label)


def _format_actor(actor: str | None) -> str:
    if not actor or actor in {"system", "migration"}:
        return "—"
    if actor == "local":
        return "Локальное рабочее место"
    if actor.startswith("lan:"):
        parts = actor.split(":")
        if len(parts) >= 3 and parts[1]:
            return parts[1]
    return actor


def _event_author(session: Session, event_id: int) -> str:
    actor = session.scalar(
        text(
            """
            SELECT actor
            FROM event_audit
            WHERE event_id = :event_id
              AND action IN ('create', 'baseline')
            ORDER BY CASE action WHEN 'create' THEN 0 ELSE 1 END, id ASC
            LIMIT 1
            """
        ),
        {"event_id": event_id},
    )
    return _format_actor(str(actor) if actor is not None else None)


def _downtime_minutes(event: Event) -> int | None:
    if event.end_at is None:
        return None
    return max(0, int((event.end_at - event.start_at).total_seconds() // 60))


def _event_snapshot(session: Session, event: Event) -> dict[str, object]:
    return {
        "id": event.id,
        "revision": event.revision,
        "startAt": event.start_at.isoformat(timespec="minutes"),
        "endAt": event.end_at.isoformat(timespec="minutes") if event.end_at else None,
        "assetLabel": event.asset_label,
        "eventType": event.event_type,
        "description": event.description,
        "reason": event.reason,
        "actions": event.actions,
        "performer": event.performer,
        "errorCodes": event.error_codes,
        "rotorLimit": str(event.rotor_limit) if event.rotor_limit is not None else None,
        "repairPowerMw": (
            str(event.repair_power_mw) if event.repair_power_mw is not None else None
        ),
        "status": event.status,
        "includeInReport": event.include_in_report,
        "enteredBy": _event_author(session, event.id),
        "downtimeMinutes": _downtime_minutes(event),
        # The original workbook loss formula has not yet been recovered with
        # enough certainty to reproduce it. Keep the approved column visible,
        # but do not invent a business value.
        "losses": None,
    }


@contextmanager
def _tracked_operation(kind: str, *, reversible: bool) -> Iterator[None]:
    tokens = bind_audit_context(
        current_audit_actor(),
        current_audit_client_ip(),
        operation_id=f"{kind}:{uuid4().hex}",
        operation_kind=kind,
        operation_reversible=reversible,
        operation_track=True,
    )
    try:
        yield
    finally:
        reset_audit_context(tokens)


def _prepare_patch(event: Event, changes: Mapping[str, Any]) -> dict[str, object]:
    values: dict[str, object] = {}

    for api_field, raw_value in changes.items():
        model_field = _TEXT_FIELDS.get(api_field)
        if model_field is not None:
            if raw_value is None and api_field in _NULLABLE_TEXT_FIELDS:
                values[model_field] = None
            elif isinstance(raw_value, str):
                values[model_field] = (
                    raw_value
                    if api_field in {"assetLabel", "description"}
                    else raw_value.strip() or None
                )
            else:
                raise EventValidationError(f"Поле «{api_field}» должно содержать текст.")
            continue

        if api_field == "startAt":
            values["start_at"] = _parse_datetime(raw_value, label="Дата и время останова")
            continue

        if api_field == "endAt":
            if raw_value is None or raw_value == "":
                values["end_at"] = None
                values["status"] = "open"
            else:
                values["end_at"] = _parse_datetime(raw_value, label="Дата и время пуска")
                values["status"] = "closed"
            continue

        if api_field == "eventType":
            if not isinstance(raw_value, str) or raw_value not in EVENT_TYPE_KEYS:
                raise EventValidationError("Передан недопустимый внутренний тип события.")
            values["event_type"] = raw_value
            continue

        if api_field == "includeInReport":
            if not isinstance(raw_value, bool):
                raise EventValidationError("Признак рапорта должен быть логическим значением.")
            values["include_in_report"] = raw_value
            continue

        if api_field == "rotorLimit":
            if raw_value is None:
                rotor_limit = None
            elif isinstance(raw_value, str):
                rotor_limit = parse_rotor_limit(raw_value)
            else:
                raise EventValidationError("Ограничение по оборотам должно быть текстом.")
            values["rotor_limit"] = rotor_limit
            values["repair_power_mw"] = calculate_repair_power_mw(rotor_limit)
            continue

        raise EventValidationError(f"Поле «{api_field}» нельзя изменять в журнале.")

    resulting_start = values.get("start_at", event.start_at)
    resulting_end = values.get("end_at", event.end_at)
    if isinstance(resulting_start, datetime) and isinstance(resulting_end, datetime):
        if resulting_end < resulting_start:
            raise EventValidationError("Дата и время пуска не могут быть раньше останова.")

    values["updated_at"] = datetime.now()
    values["revision"] = Event.revision + 1
    return values


def _create_values(payload_values: Mapping[str, Any]) -> dict[str, object]:
    normalized = event_values_from_form(_v2_create_form_values(payload_values))
    raw_end = payload_values.get("endAt")
    if raw_end not in {None, ""}:
        end_at = _parse_datetime(raw_end, label="Дата и время пуска")
        start_at = normalized["start_at"]
        if isinstance(start_at, datetime) and end_at < start_at:
            raise EventValidationError("Дата и время пуска не могут быть раньше останова.")
        normalized["end_at"] = end_at
        normalized["status"] = "closed"
    return normalized


@journal_form_blueprint.get("/snapshot")
def snapshot() -> Response:
    statement = (
        select(Event)
        .where(Event.status != _DELETED_STATUS)
        .order_by(Event.start_at.asc(), Event.id.asc())
    )
    with Session(_database_engine()) as session:
        records = [_event_snapshot(session, event) for event in session.scalars(statement)]
    return jsonify(
        {
            "schemaVersion": 2,
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "records": records,
        }
    )


@journal_form_blueprint.post("/records")
def create_record() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _api_error("invalid_json", "Ожидался JSON-объект.", status=400)
    client_id = payload.get("clientId")
    raw_values = payload.get("values")
    if not isinstance(client_id, str) or not client_id.strip() or len(client_id) > 128:
        return _api_error("invalid_client_id", "Некорректный идентификатор строки.", status=400)
    if not isinstance(raw_values, dict):
        return _api_error("invalid_values", "Не переданы значения новой строки.", status=400)
    try:
        normalized = _create_values(raw_values)
    except EventValidationError as exc:
        return _api_error("validation_error", str(exc), status=422)

    with _tracked_operation("create", reversible=False):
        with Session(_database_engine()) as session:
            event = Event(**normalized)
            session.add(event)
            session.commit()
            session.refresh(event)
            record = _event_snapshot(session, event)
    return jsonify({"schemaVersion": 2, "clientId": client_id, "record": record}), 201


@journal_form_blueprint.patch("/records/<int:event_id>")
def patch_record(event_id: int) -> tuple[Response, int] | Response:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _api_error("invalid_json", "Ожидался JSON-объект.", status=400)
    expected_revision = _positive_integer(payload.get("revision"))
    changes = payload.get("changes")
    if expected_revision is None:
        return _api_error("invalid_revision", "Некорректная ревизия записи.", status=400)
    if not isinstance(changes, dict) or not changes:
        return _api_error("invalid_changes", "Не переданы изменения записи.", status=400)

    with _tracked_operation("patch", reversible=True):
        with Session(_database_engine()) as session:
            event = session.get(Event, event_id)
            if event is None or event.status == _DELETED_STATUS:
                return _api_error("not_found", "Запись журнала не найдена.", status=404)
            if event.revision != expected_revision:
                return _api_error(
                    "revision_conflict",
                    "Запись уже изменена в другом окне.",
                    status=409,
                    current=_event_snapshot(session, event),
                )
            try:
                update_values = _prepare_patch(event, changes)
            except EventValidationError as exc:
                return _api_error("validation_error", str(exc), status=422)
            result = session.execute(
                update(Event)
                .where(Event.id == event_id, Event.revision == expected_revision)
                .values(**update_values)
            )
            if result.rowcount != 1:
                session.rollback()
                return _api_error("revision_conflict", "Запись конкурентно изменена.", status=409)
            session.commit()
            updated = session.get(Event, event_id)
            if updated is None:
                return _api_error("not_found", "Запись журнала не найдена.", status=404)
            record = _event_snapshot(session, updated)
    return jsonify({"schemaVersion": 2, "record": record})


@journal_form_blueprint.post("/records/batch")
def patch_batch() -> tuple[Response, int] | Response:
    payload = request.get_json(silent=True)
    operations = payload.get("operations") if isinstance(payload, dict) else None
    if not isinstance(operations, list) or not operations:
        return _api_error("invalid_operations", "Не переданы пакетные изменения.", status=400)
    if len(operations) > MAX_BATCH_OPERATIONS:
        return _api_error("batch_too_large", "Выбрано слишком много строк.", status=413)

    prepared: list[tuple[int, int, dict[str, object]]] = []
    seen: set[int] = set()
    with _tracked_operation("batch", reversible=True):
        with Session(_database_engine()) as session:
            for index, operation in enumerate(operations):
                if not isinstance(operation, dict):
                    return _api_error("invalid_operation", "Некорректная операция.", status=400)
                event_id = _positive_integer(operation.get("recordId"))
                revision = _positive_integer(operation.get("revision"))
                changes = operation.get("changes")
                invalid_operation = (
                    event_id is None
                    or revision is None
                    or not isinstance(changes, dict)
                    or not changes
                )
                if invalid_operation:
                    return _api_error(
                        "invalid_operation",
                        "Некорректная пакетная операция.",
                        status=400,
                        operationIndex=index,
                    )
                if event_id in seen:
                    return _api_error("duplicate_record", "Строка указана дважды.", status=400)
                seen.add(event_id)
                event = session.get(Event, event_id)
                if event is None or event.status == _DELETED_STATUS:
                    return _api_error("not_found", "Запись журнала не найдена.", status=404)
                if event.revision != revision:
                    return _api_error(
                        "revision_conflict",
                        "Одна из строк уже изменена.",
                        status=409,
                        recordId=event_id,
                        current=_event_snapshot(session, event),
                    )
                try:
                    values = _prepare_patch(event, changes)
                except EventValidationError as exc:
                    return _api_error(
                        "validation_error",
                        str(exc),
                        status=422,
                        operationIndex=index,
                        recordId=event_id,
                    )
                prepared.append((event_id, revision, values))

            for event_id, revision, values in prepared:
                result = session.execute(
                    update(Event)
                    .where(Event.id == event_id, Event.revision == revision)
                    .values(**values)
                )
                if result.rowcount != 1:
                    session.rollback()
                    return _api_error(
                        "revision_conflict",
                        "Пакетная операция отменена из-за конкурентного изменения.",
                        status=409,
                        recordId=event_id,
                    )
            session.commit()
            records = []
            for event_id, _revision, _values in prepared:
                event = session.get(Event, event_id)
                if event is not None:
                    records.append(_event_snapshot(session, event))
    return jsonify({"schemaVersion": 2, "records": records})


@journal_form_blueprint.post("/records/delete")
def delete_rows() -> tuple[Response, int] | Response:
    payload = request.get_json(silent=True)
    operations = payload.get("operations") if isinstance(payload, dict) else None
    if not isinstance(operations, list) or not operations:
        return _api_error("invalid_operations", "Не выбраны строки для удаления.", status=400)
    if len(operations) > MAX_BATCH_OPERATIONS:
        return _api_error("batch_too_large", "Выбрано слишком много строк.", status=413)

    prepared: list[tuple[int, int]] = []
    seen: set[int] = set()
    with _tracked_operation("batch", reversible=True):
        with Session(_database_engine()) as session:
            for index, operation in enumerate(operations):
                if not isinstance(operation, dict):
                    return _api_error(
                        "invalid_operation",
                        "Некорректная операция удаления.",
                        status=400,
                    )
                event_id = _positive_integer(operation.get("recordId"))
                revision = _positive_integer(operation.get("revision"))
                if event_id is None or revision is None:
                    return _api_error(
                        "invalid_operation",
                        "Некорректная операция удаления.",
                        status=400,
                        operationIndex=index,
                    )
                if event_id in seen:
                    return _api_error("duplicate_record", "Строка указана дважды.", status=400)
                seen.add(event_id)
                event = session.get(Event, event_id)
                if event is None or event.status == _DELETED_STATUS:
                    return _api_error("not_found", "Запись журнала не найдена.", status=404)
                if event.revision != revision:
                    return _api_error(
                        "revision_conflict",
                        "Одна из строк уже изменена.",
                        status=409,
                        recordId=event_id,
                        current=_event_snapshot(session, event),
                    )
                prepared.append((event_id, revision))

            for event_id, revision in prepared:
                result = session.execute(
                    update(Event)
                    .where(Event.id == event_id, Event.revision == revision)
                    .values(
                        status=_DELETED_STATUS,
                        updated_at=datetime.now(),
                        revision=Event.revision + 1,
                    )
                )
                if result.rowcount != 1:
                    session.rollback()
                    return _api_error(
                        "revision_conflict",
                        "Удаление отменено из-за конкурентного изменения.",
                        status=409,
                        recordId=event_id,
                    )
            session.commit()
    return jsonify(
        {
            "schemaVersion": 2,
            "deletedRecordIds": [event_id for event_id, _revision in prepared],
        }
    )
