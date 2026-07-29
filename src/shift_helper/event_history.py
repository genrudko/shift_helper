"""Read-only audit API for operational event records."""

from __future__ import annotations

import json

from flask import Blueprint, Response, current_app, jsonify
from sqlalchemy import text
from sqlalchemy.engine import Engine

event_history_blueprint = Blueprint(
    "event_history",
    __name__,
    url_prefix="/events/api/v2",
)


def _database_engine() -> Engine:
    return current_app.extensions["shift_helper_database_engine"]


@event_history_blueprint.get("/records/<int:event_id>/history")
def event_history(event_id: int) -> tuple[Response, int] | Response:
    """Return immutable audit entries for one event in revision order."""

    engine = _database_engine()
    with engine.connect() as connection:
        exists = connection.scalar(
            text("SELECT id FROM events WHERE id = :event_id"),
            {"event_id": event_id},
        )
        if exists is None:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "not_found",
                            "message": "Запись журнала не найдена.",
                        }
                    }
                ),
                404,
            )

        rows = connection.execute(
            text(
                """
                SELECT
                    id,
                    action,
                    old_revision,
                    new_revision,
                    changed_at,
                    before_json,
                    after_json
                FROM event_audit
                WHERE event_id = :event_id
                ORDER BY id ASC
                """
            ),
            {"event_id": event_id},
        ).mappings()

        entries = [
            {
                "id": row["id"],
                "action": row["action"],
                "oldRevision": row["old_revision"],
                "newRevision": row["new_revision"],
                "changedAt": row["changed_at"],
                "before": json.loads(row["before_json"]) if row["before_json"] else None,
                "after": json.loads(row["after_json"]),
            }
            for row in rows
        ]

    return jsonify(
        {
            "schemaVersion": 1,
            "recordId": event_id,
            "entries": entries,
        }
    )
