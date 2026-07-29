from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from shift_helper import create_app
from shift_helper.database import create_database_engine, initialize_database
from shift_helper.models import Base, Event


def _event_form() -> dict[str, str]:
    return {
        "start_at": "2026-07-29T15:10",
        "asset_label": "ВЭУ №21",
        "event_type": "other",
        "description": "Исходная запись аудита",
        "reason": "Проверка",
        "actions": "Наблюдение",
        "performer": "Петров П.П.",
        "error_codes": "",
        "rotor_limit": "",
        "include_in_report": "on",
    }


def test_event_audit_tracks_create_update_and_close(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    created = client.post("/events/new", data=_event_form())
    assert created.status_code == 302

    patched = client.patch(
        "/events/api/v2/records/1",
        json={
            "revision": 1,
            "changes": {
                "description": "Изменённая запись аудита",
                "includeInReport": False,
            },
        },
    )
    assert patched.status_code == 200

    closed = client.post("/events/api/v2/records/1/close", json={"revision": 2})
    assert closed.status_code == 200

    response = client.get("/events/api/v2/records/1/history")
    assert response.status_code == 200
    body = response.get_json()
    assert body["schemaVersion"] == 1
    assert body["recordId"] == 1

    entries = body["entries"]
    assert [entry["action"] for entry in entries] == ["create", "update", "close"]
    assert [entry["newRevision"] for entry in entries] == [1, 2, 3]
    assert [entry["actor"] for entry in entries] == ["local", "local", "local"]
    assert [entry["clientIp"] for entry in entries] == [
        "127.0.0.1",
        "127.0.0.1",
        "127.0.0.1",
    ]
    assert entries[0]["oldRevision"] is None
    assert entries[0]["before"] is None
    assert entries[0]["after"]["description"] == "Исходная запись аудита"
    assert entries[1]["oldRevision"] == 1
    assert entries[1]["before"]["description"] == "Исходная запись аудита"
    assert entries[1]["after"]["description"] == "Изменённая запись аудита"
    assert entries[1]["before"]["includeInReport"] == 1
    assert entries[1]["after"]["includeInReport"] == 0
    assert entries[2]["oldRevision"] == 2
    assert entries[2]["before"]["status"] == "open"
    assert entries[2]["after"]["status"] == "closed"
    assert entries[2]["after"]["endAt"] is not None

    missing = client.get("/events/api/v2/records/999/history")
    assert missing.status_code == 404
    assert missing.get_json()["error"]["code"] == "not_found"


def test_event_audit_is_append_only(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    client.post("/events/new", data=_event_form())
    engine = app.extensions["shift_helper_database_engine"]

    with pytest.raises(DBAPIError, match="event_audit is immutable"):
        with engine.begin() as connection:
            connection.execute(text("UPDATE event_audit SET action = 'baseline' WHERE id = 1"))

    with pytest.raises(DBAPIError, match="event_audit is immutable"):
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM event_audit WHERE id = 1"))

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM event_audit")) == 1


def test_schema_migration_creates_baseline_for_existing_events(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    legacy_engine = create_database_engine(database_path)
    Base.metadata.create_all(legacy_engine)

    with Session(legacy_engine) as session:
        session.add(
            Event(
                start_at=datetime(2026, 7, 28, 9, 30),
                asset_label="ВЭУ №3",
                event_type="other",
                description="Запись до включения аудита",
            )
        )
        session.commit()
    legacy_engine.dispose()

    migrated_engine = initialize_database(database_path)
    with migrated_engine.connect() as connection:
        assert connection.scalar(
            text("SELECT value FROM app_metadata WHERE key = 'schema_version'")
        ) == "4"
        row = connection.execute(
            text(
                """
                SELECT
                    action,
                    old_revision,
                    new_revision,
                    actor,
                    client_ip,
                    before_json,
                    after_json
                FROM event_audit
                WHERE event_id = 1
                """
            )
        ).mappings().one()
        assert row["action"] == "baseline"
        assert row["old_revision"] is None
        assert row["new_revision"] == 1
        assert row["actor"] == "migration"
        assert row["client_ip"] is None
        assert row["before_json"] is None
        assert "Запись до включения аудита" in row["after_json"]

    with Session(migrated_engine) as session:
        event = session.scalar(select(Event))
        assert event is not None
        event.description = "Изменение после миграции"
        event.revision += 1
        session.commit()

    with migrated_engine.connect() as connection:
        rows = list(
            connection.execute(
                text(
                    """
                    SELECT action, actor, client_ip
                    FROM event_audit
                    WHERE event_id = 1
                    ORDER BY id
                    """
                )
            ).mappings()
        )
        assert [row["action"] for row in rows] == ["baseline", "update"]
        assert rows[1]["actor"] == "system"
        assert rows[1]["client_ip"] is None
