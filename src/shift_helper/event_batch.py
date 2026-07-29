"""Transactional batch mutation API for Univer multi-cell operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .domain import EventValidationError, event_values_from_form
from .events import V2_PATCH_FIELDS, _event_snapshot, _v2_patch_form_values
from .models import Event

event_batch_blueprint = Blueprint(
    "event_batch",
    __name__,
    url_prefix="/events/api/v2",
)
MAX_BATCH_OPERATIONS = 200


def _database_engine() -> Engine:
    return current_app.extensions["shift_helper_database_engine"]


def _error(
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


@event_batch_blueprint.post("/records/batch")
def patch_records_batch() -> tuple[Response, int] | Response:
    """Validate and persist all record patches in one SQLite transaction."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("invalid_json", "Ожидался JSON-объект.", status=400)

    operations = payload.get("operations")
    if not isinstance(operations, list) or not operations:
        return _error("invalid_operations", "Не переданы пакетные изменения.", status=400)
    if len(operations) > MAX_BATCH_OPERATIONS:
        return _error(
            "batch_too_large",
            f"За одну операцию допускается не более {MAX_BATCH_OPERATIONS} строк.",
            status=413,
        )

    prepared: list[tuple[int, int, int, dict[str, object]]] = []
    record_ids: set[int] = set()

    with Session(_database_engine()) as session:
        for operation_index, operation in enumerate(operations):
            if not isinstance(operation, dict):
                return _error(
                    "invalid_operation",
                    "Каждая пакетная операция должна быть JSON-объектом.",
                    status=400,
                    operationIndex=operation_index,
                )

            event_id = _positive_integer(operation.get("recordId"))
            expected_revision = _positive_integer(operation.get("revision"))
            changes = operation.get("changes")
            if event_id is None:
                return _error(
                    "invalid_record_id",
                    "Укажите корректный идентификатор записи.",
                    status=400,
                    operationIndex=operation_index,
                )
            if expected_revision is None:
                return _error(
                    "invalid_revision",
                    "Укажите корректную ревизию записи.",
                    status=400,
                    operationIndex=operation_index,
                    recordId=event_id,
                )
            if not isinstance(changes, dict) or not changes:
                return _error(
                    "invalid_changes",
                    "Не переданы изменения записи.",
                    status=400,
                    operationIndex=operation_index,
                    recordId=event_id,
                )
            if event_id in record_ids:
                return _error(
                    "duplicate_record",
                    "Одна запись не должна повторяться в пакетной операции.",
                    status=400,
                    operationIndex=operation_index,
                    recordId=event_id,
                )
            record_ids.add(event_id)

            event = session.get(Event, event_id)
            if event is None:
                return _error(
                    "not_found",
                    "Запись журнала не найдена.",
                    status=404,
                    operationIndex=operation_index,
                    recordId=event_id,
                )
            if event.revision != expected_revision:
                return _error(
                    "revision_conflict",
                    "Одна из строк уже изменена. Пакетная операция отменена полностью.",
                    status=409,
                    operationIndex=operation_index,
                    recordId=event_id,
                    current=_event_snapshot(event),
                )

            try:
                normalized = event_values_from_form(_v2_patch_form_values(event, changes))
            except EventValidationError as exc:
                return _error(
                    "validation_error",
                    str(exc),
                    status=422,
                    operationIndex=operation_index,
                    recordId=event_id,
                )

            update_values: dict[str, object] = {
                V2_PATCH_FIELDS[api_field]: normalized[V2_PATCH_FIELDS[api_field]]
                for api_field in changes
                if api_field in V2_PATCH_FIELDS
            }
            if "rotorLimit" in changes:
                update_values["repair_power_mw"] = normalized["repair_power_mw"]
            update_values["updated_at"] = datetime.now()
            update_values["revision"] = Event.revision + 1
            prepared.append(
                (operation_index, event_id, expected_revision, update_values)
            )

        for operation_index, event_id, expected_revision, update_values in prepared:
            result = session.execute(
                update(Event)
                .where(Event.id == event_id, Event.revision == expected_revision)
                .values(**update_values)
            )
            if result.rowcount != 1:
                session.rollback()
                session.expire_all()
                current = session.get(Event, event_id)
                details: dict[str, object] = {
                    "operationIndex": operation_index,
                    "recordId": event_id,
                }
                if current is not None:
                    details["current"] = _event_snapshot(current)
                return _error(
                    "revision_conflict",
                    "Одна из строк уже изменена. Пакетная операция отменена полностью.",
                    status=409,
                    **details,
                )

        session.commit()
        updated_records = []
        for _operation_index, event_id, _revision, _values in prepared:
            event = session.get(Event, event_id)
            if event is None:
                return _error(
                    "not_found",
                    "Запись журнала не найдена после пакетной операции.",
                    status=404,
                    recordId=event_id,
                )
            updated_records.append(_event_snapshot(event))

    return jsonify({"schemaVersion": 1, "records": updated_records})
