"""Persistent conflict-safe undo and redo for reversible event operations."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .database import APPLICATION_SCHEMA_VERSION
from .events import _event_snapshot
from .models import Event

event_operations_blueprint = Blueprint(
    "event_operations",
    __name__,
    url_prefix="/events/api/v2/operations",
)

_OPERATION_LABELS = {
    "create": "Создание записи",
    "patch": "Изменение записи",
    "edit": "Изменение записи",
    "batch": "Пакетное изменение",
    "close": "Завершение события",
}


def _database_engine() -> Engine:
    return current_app.extensions["shift_helper_database_engine"]


def finalize_event_operation_schema(engine: Engine) -> None:
    """Restore the authoritative schema version after additive initializers."""

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO app_metadata (key, value)
                VALUES ('schema_version', :schema_version)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """
            ),
            {"schema_version": APPLICATION_SCHEMA_VERSION},
        )


def _api_error(
    code: str,
    message: str,
    *,
    status: int,
    **details: object,
) -> tuple[Response, int]:
    return jsonify({"error": {"code": code, "message": message, **details}}), status


def _operation_row(
    session: Session,
    state: str,
    *,
    ascending: bool,
) -> dict[str, Any] | None:
    direction = "ASC" if ascending else "DESC"
    row = session.execute(
        text(
            f"""
            SELECT
                id,
                operation_id,
                kind,
                reversible,
                actor,
                client_ip,
                created_at,
                state
            FROM event_operation
            WHERE state = :state
            ORDER BY id {direction}
            LIMIT 1
            """
        ),
        {"state": state},
    ).mappings().one_or_none()
    return dict(row) if row is not None else None


def _operation_records(session: Session, operation_id: str) -> list[int]:
    return [
        int(event_id)
        for event_id in session.scalars(
            text(
                """
                SELECT DISTINCT event_id
                FROM event_audit
                WHERE operation_id = :operation_id
                ORDER BY event_id
                """
            ),
            {"operation_id": operation_id},
        )
    ]


def _operation_summary(
    session: Session,
    row: dict[str, Any] | None,
) -> dict[str, object] | None:
    if row is None:
        return None
    operation_id = str(row["operation_id"])
    record_ids = _operation_records(session, operation_id)
    return {
        "operationId": operation_id,
        "kind": row["kind"],
        "label": _OPERATION_LABELS.get(str(row["kind"]), str(row["kind"])),
        "reversible": bool(row["reversible"]),
        "actor": row["actor"],
        "clientIp": row["client_ip"],
        "createdAt": row["created_at"],
        "recordIds": record_ids,
        "recordCount": len(record_ids),
    }


def _state_payload(session: Session) -> dict[str, object]:
    undo_row = _operation_row(session, "applied", ascending=False)
    redo_row = _operation_row(session, "undone", ascending=True)
    undo_summary = _operation_summary(session, undo_row)
    redo_summary = _operation_summary(session, redo_row)

    if undo_summary is None:
        undo_reason = "Нет операций для отмены."
    elif not undo_summary["reversible"]:
        undo_reason = (
            f"Операция «{undo_summary['label']}» является необратимым барьером."
        )
    else:
        undo_reason = None

    return {
        "schemaVersion": 1,
        "canUndo": bool(undo_summary and undo_summary["reversible"]),
        "canRedo": redo_summary is not None,
        "undo": undo_summary,
        "redo": redo_summary,
        "undoReason": undo_reason,
    }


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))


def _parse_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _normalized_semantic(snapshot: dict[str, object]) -> dict[str, object]:
    return {
        "startAt": _parse_datetime(snapshot.get("startAt")),
        "endAt": _parse_datetime(snapshot.get("endAt")),
        "assetLabel": snapshot.get("assetLabel"),
        "eventType": snapshot.get("eventType"),
        "description": snapshot.get("description"),
        "reason": snapshot.get("reason"),
        "actions": snapshot.get("actions"),
        "performer": snapshot.get("performer"),
        "errorCodes": snapshot.get("errorCodes"),
        "rotorLimit": _parse_decimal(snapshot.get("rotorLimit")),
        "repairPowerMw": _parse_decimal(snapshot.get("repairPowerMw")),
        "status": snapshot.get("status"),
        "includeInReport": bool(snapshot.get("includeInReport")),
    }


def _event_semantic(event: Event) -> dict[str, object]:
    return _normalized_semantic(_event_snapshot(event))


def _snapshot_values(snapshot: dict[str, object]) -> dict[str, object]:
    normalized = _normalized_semantic(snapshot)
    return {
        "start_at": normalized["startAt"],
        "end_at": normalized["endAt"],
        "asset_label": normalized["assetLabel"],
        "event_type": normalized["eventType"],
        "description": normalized["description"],
        "reason": normalized["reason"],
        "actions": normalized["actions"],
        "performer": normalized["performer"],
        "error_codes": normalized["errorCodes"],
        "rotor_limit": normalized["rotorLimit"],
        "repair_power_mw": normalized["repairPowerMw"],
        "status": normalized["status"],
        "include_in_report": normalized["includeInReport"],
        "updated_at": datetime.now(),
        "revision": Event.revision + 1,
    }


def _operation_snapshots(
    session: Session,
    operation_id: str,
) -> dict[int, tuple[dict[str, object], dict[str, object]]]:
    rows = session.execute(
        text(
            """
            SELECT event_id, before_json, after_json
            FROM event_audit
            WHERE operation_id = :operation_id
            ORDER BY id ASC
            """
        ),
        {"operation_id": operation_id},
    ).mappings()
    grouped: dict[int, list[dict[str, dict[str, object]]]] = defaultdict(list)
    for row in rows:
        if row["before_json"] is None:
            continue
        grouped[int(row["event_id"])].append(
            {
                "before": json.loads(row["before_json"]),
                "after": json.loads(row["after_json"]),
            }
        )
    return {
        event_id: (entries[0]["before"], entries[-1]["after"])
        for event_id, entries in grouped.items()
        if entries
    }


def _requested_operation_id() -> str | None:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None
    operation_id = payload.get("operationId")
    if (
        not isinstance(operation_id, str)
        or not operation_id.strip()
        or len(operation_id) > 128
    ):
        return None
    return operation_id


def _transition_operation(*, direction: str) -> tuple[Response, int] | Response:
    requested_id = _requested_operation_id()
    if requested_id is None:
        return _api_error(
            "invalid_operation_id",
            "Укажите корректный идентификатор операции.",
            status=400,
        )

    source_state = "applied" if direction == "undo" else "undone"
    target_state = "undone" if direction == "undo" else "applied"
    ascending = direction == "redo"

    with Session(_database_engine()) as session:
        candidate = _operation_row(session, source_state, ascending=ascending)
        if candidate is None or candidate["operation_id"] != requested_id:
            return _api_error(
                "operation_conflict",
                "История операций уже изменилась. Обновите состояние отмены.",
                status=409,
                state=_state_payload(session),
            )
        if not bool(candidate["reversible"]):
            return _api_error(
                "operation_not_reversible",
                "Эту операцию нельзя отменить.",
                status=422,
                state=_state_payload(session),
            )

        snapshots = _operation_snapshots(session, requested_id)
        if not snapshots:
            return _api_error(
                "operation_payload_missing",
                "Для операции отсутствует обратимое состояние.",
                status=422,
            )

        updated_ids: list[int] = []
        for event_id, (before, after) in snapshots.items():
            expected = after if direction == "undo" else before
            target = before if direction == "undo" else after
            event = session.scalar(select(Event).where(Event.id == event_id))
            if event is None:
                session.rollback()
                return _api_error(
                    "operation_conflict",
                    "Одна из записей операции больше не существует.",
                    status=409,
                    recordId=event_id,
                )
            if _event_semantic(event) != _normalized_semantic(expected):
                session.rollback()
                return _api_error(
                    "operation_conflict",
                    "Запись изменилась после выбранной операции. Отмена не выполнена.",
                    status=409,
                    recordId=event_id,
                    current=_event_snapshot(event),
                )

            current_revision = event.revision
            result = session.execute(
                update(Event)
                .where(Event.id == event_id, Event.revision == current_revision)
                .values(**_snapshot_values(target))
            )
            if result.rowcount != 1:
                session.rollback()
                return _api_error(
                    "operation_conflict",
                    "Запись конкурентно изменена. Операция отменена полностью.",
                    status=409,
                    recordId=event_id,
                )
            updated_ids.append(event_id)

        operation_update = session.execute(
            text(
                """
                UPDATE event_operation
                SET state = :target_state
                WHERE operation_id = :operation_id AND state = :source_state
                """
            ),
            {
                "target_state": target_state,
                "operation_id": requested_id,
                "source_state": source_state,
            },
        )
        if operation_update.rowcount != 1:
            session.rollback()
            return _api_error(
                "operation_conflict",
                "История операций конкурентно изменена.",
                status=409,
            )

        session.commit()
        records = []
        for event_id in updated_ids:
            event = session.get(Event, event_id)
            if event is not None:
                records.append(_event_snapshot(event))
        return jsonify(
            {
                "schemaVersion": 1,
                "direction": direction,
                "operationId": requested_id,
                "records": records,
                "state": _state_payload(session),
            }
        )


@event_operations_blueprint.get("/state")
def operation_state() -> Response:
    with Session(_database_engine()) as session:
        return jsonify(_state_payload(session))


@event_operations_blueprint.post("/undo")
def undo_operation() -> tuple[Response, int] | Response:
    return _transition_operation(direction="undo")


@event_operations_blueprint.post("/redo")
def redo_operation() -> tuple[Response, int] | Response:
    return _transition_operation(direction="redo")
