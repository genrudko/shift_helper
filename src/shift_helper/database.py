"""SQLite initialization for the local Shift-Helper datastore."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine

from .models import Base

APPLICATION_SCHEMA_VERSION = "3"


def create_database_engine(database_path: Path) -> Engine:
    """Create a SQLite engine configured for a local desktop-style workload."""
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        future=True,
        connect_args={"timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA busy_timeout = 5000")
        finally:
            cursor.close()

    return engine


def _event_json(alias: str) -> str:
    return f"""
        json_object(
            'id', {alias}.id,
            'revision', {alias}.revision,
            'startAt', {alias}.start_at,
            'endAt', {alias}.end_at,
            'assetLabel', {alias}.asset_label,
            'eventType', {alias}.event_type,
            'description', {alias}.description,
            'reason', {alias}.reason,
            'actions', {alias}.actions,
            'performer', {alias}.performer,
            'errorCodes', {alias}.error_codes,
            'rotorLimit', {alias}.rotor_limit,
            'repairPowerMw', {alias}.repair_power_mw,
            'status', {alias}.status,
            'includeInReport', {alias}.include_in_report,
            'createdAt', {alias}.created_at,
            'updatedAt', {alias}.updated_at
        )
    """


def _initialize_event_audit(connection: Connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS event_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                action TEXT NOT NULL CHECK (
                    action IN ('baseline', 'create', 'update', 'close')
                ),
                old_revision INTEGER,
                new_revision INTEGER NOT NULL,
                changed_at TEXT NOT NULL,
                before_json TEXT,
                after_json TEXT NOT NULL
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_event_audit_event_id_id
            ON event_audit (event_id, id)
            """
        )
    )

    for trigger_name in (
        "trg_events_audit_insert",
        "trg_events_audit_update",
        "trg_event_audit_immutable_update",
        "trg_event_audit_immutable_delete",
    ):
        connection.execute(text(f"DROP TRIGGER IF EXISTS {trigger_name}"))

    connection.execute(
        text(
            f"""
            CREATE TRIGGER trg_events_audit_insert
            AFTER INSERT ON events
            BEGIN
                INSERT INTO event_audit (
                    event_id,
                    action,
                    old_revision,
                    new_revision,
                    changed_at,
                    before_json,
                    after_json
                ) VALUES (
                    NEW.id,
                    'create',
                    NULL,
                    NEW.revision,
                    COALESCE(NEW.updated_at, CURRENT_TIMESTAMP),
                    NULL,
                    {_event_json('NEW')}
                );
            END
            """
        )
    )
    connection.execute(
        text(
            f"""
            CREATE TRIGGER trg_events_audit_update
            AFTER UPDATE ON events
            BEGIN
                INSERT INTO event_audit (
                    event_id,
                    action,
                    old_revision,
                    new_revision,
                    changed_at,
                    before_json,
                    after_json
                ) VALUES (
                    NEW.id,
                    CASE
                        WHEN OLD.status <> 'closed' AND NEW.status = 'closed' THEN 'close'
                        ELSE 'update'
                    END,
                    OLD.revision,
                    NEW.revision,
                    COALESCE(NEW.updated_at, CURRENT_TIMESTAMP),
                    {_event_json('OLD')},
                    {_event_json('NEW')}
                );
            END
            """
        )
    )

    connection.execute(
        text(
            f"""
            INSERT INTO event_audit (
                event_id,
                action,
                old_revision,
                new_revision,
                changed_at,
                before_json,
                after_json
            )
            SELECT
                events.id,
                'baseline',
                NULL,
                events.revision,
                COALESCE(events.updated_at, CURRENT_TIMESTAMP),
                NULL,
                {_event_json('events')}
            FROM events
            WHERE NOT EXISTS (
                SELECT 1
                FROM event_audit
                WHERE event_audit.event_id = events.id
            )
            """
        )
    )

    connection.execute(
        text(
            """
            CREATE TRIGGER trg_event_audit_immutable_update
            BEFORE UPDATE ON event_audit
            BEGIN
                SELECT RAISE(ABORT, 'event_audit is immutable');
            END
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TRIGGER trg_event_audit_immutable_delete
            BEFORE DELETE ON event_audit
            BEGIN
                SELECT RAISE(ABORT, 'event_audit is immutable');
            END
            """
        )
    )


def initialize_database(database_path: Path) -> Engine:
    """Create the database and current application schema when absent."""
    engine = create_database_engine(database_path)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA journal_mode = WAL"))

    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS app_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
        )
        _initialize_event_audit(connection)
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
    return engine
