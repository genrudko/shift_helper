"""SQLite initialization for the local Shift-Helper datastore."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine

from .audit_context import (
    current_audit_actor,
    current_audit_client_ip,
    current_operation_id,
    current_operation_kind,
    current_operation_reversible,
    current_operation_track,
)
from .models import Base

APPLICATION_SCHEMA_VERSION = "6"


def create_database_engine(database_path: Path) -> Engine:
    """Create a SQLite engine configured for a local desktop-style workload."""
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        future=True,
        connect_args={"timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection: object, _connection_record: object) -> None:
        connection = dbapi_connection  # type: ignore[assignment]
        connection.create_function("shift_helper_actor", 0, current_audit_actor)
        connection.create_function("shift_helper_client_ip", 0, current_audit_client_ip)
        connection.create_function("shift_helper_operation_id", 0, current_operation_id)
        connection.create_function("shift_helper_operation_kind", 0, current_operation_kind)
        connection.create_function(
            "shift_helper_operation_reversible",
            0,
            current_operation_reversible,
        )
        connection.create_function("shift_helper_operation_track", 0, current_operation_track)
        cursor = connection.cursor()
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


def _table_columns(connection: Connection, table_name: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(text(f"PRAGMA table_info({table_name})"))
    }


def _initialize_event_operations(connection: Connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS event_operation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL,
                reversible INTEGER NOT NULL CHECK (reversible IN (0, 1)),
                actor TEXT,
                client_ip TEXT,
                created_at TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'applied' CHECK (
                    state IN ('applied', 'undone', 'discarded')
                ),
                discarded_at TEXT
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_event_operation_state_id
            ON event_operation (state, id)
            """
        )
    )


def _initialize_event_audit(connection: Connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS event_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                operation_id TEXT,
                action TEXT NOT NULL CHECK (
                    action IN ('baseline', 'create', 'update', 'close')
                ),
                old_revision INTEGER,
                new_revision INTEGER NOT NULL,
                changed_at TEXT NOT NULL,
                actor TEXT,
                client_ip TEXT,
                before_json TEXT,
                after_json TEXT NOT NULL
            )
            """
        )
    )
    columns = _table_columns(connection, "event_audit")
    if "actor" not in columns:
        connection.execute(text("ALTER TABLE event_audit ADD COLUMN actor TEXT"))
    if "client_ip" not in columns:
        connection.execute(text("ALTER TABLE event_audit ADD COLUMN client_ip TEXT"))
    if "operation_id" not in columns:
        connection.execute(text("ALTER TABLE event_audit ADD COLUMN operation_id TEXT"))

    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_event_audit_event_id_id
            ON event_audit (event_id, id)
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_event_audit_operation_id_id
            ON event_audit (operation_id, id)
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
                UPDATE event_operation
                SET state = 'discarded', discarded_at = CURRENT_TIMESTAMP
                WHERE state = 'undone' AND shift_helper_operation_track() = 1;

                INSERT OR IGNORE INTO event_operation (
                    operation_id,
                    kind,
                    reversible,
                    actor,
                    client_ip,
                    created_at,
                    state
                )
                SELECT
                    shift_helper_operation_id(),
                    shift_helper_operation_kind(),
                    shift_helper_operation_reversible(),
                    shift_helper_actor(),
                    shift_helper_client_ip(),
                    COALESCE(NEW.updated_at, CURRENT_TIMESTAMP),
                    'applied'
                WHERE shift_helper_operation_track() = 1
                  AND shift_helper_operation_id() IS NOT NULL;

                INSERT INTO event_audit (
                    event_id,
                    operation_id,
                    action,
                    old_revision,
                    new_revision,
                    changed_at,
                    actor,
                    client_ip,
                    before_json,
                    after_json
                ) VALUES (
                    NEW.id,
                    shift_helper_operation_id(),
                    'create',
                    NULL,
                    NEW.revision,
                    COALESCE(NEW.updated_at, CURRENT_TIMESTAMP),
                    shift_helper_actor(),
                    shift_helper_client_ip(),
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
                UPDATE event_operation
                SET state = 'discarded', discarded_at = CURRENT_TIMESTAMP
                WHERE state = 'undone' AND shift_helper_operation_track() = 1;

                INSERT OR IGNORE INTO event_operation (
                    operation_id,
                    kind,
                    reversible,
                    actor,
                    client_ip,
                    created_at,
                    state
                )
                SELECT
                    shift_helper_operation_id(),
                    shift_helper_operation_kind(),
                    shift_helper_operation_reversible(),
                    shift_helper_actor(),
                    shift_helper_client_ip(),
                    COALESCE(NEW.updated_at, CURRENT_TIMESTAMP),
                    'applied'
                WHERE shift_helper_operation_track() = 1
                  AND shift_helper_operation_id() IS NOT NULL;

                INSERT INTO event_audit (
                    event_id,
                    operation_id,
                    action,
                    old_revision,
                    new_revision,
                    changed_at,
                    actor,
                    client_ip,
                    before_json,
                    after_json
                ) VALUES (
                    NEW.id,
                    shift_helper_operation_id(),
                    CASE
                        WHEN OLD.status <> 'closed' AND NEW.status = 'closed' THEN 'close'
                        ELSE 'update'
                    END,
                    OLD.revision,
                    NEW.revision,
                    COALESCE(NEW.updated_at, CURRENT_TIMESTAMP),
                    shift_helper_actor(),
                    shift_helper_client_ip(),
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
                operation_id,
                action,
                old_revision,
                new_revision,
                changed_at,
                actor,
                client_ip,
                before_json,
                after_json
            )
            SELECT
                events.id,
                NULL,
                'baseline',
                NULL,
                events.revision,
                COALESCE(events.updated_at, CURRENT_TIMESTAMP),
                'migration',
                NULL,
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
        _initialize_event_operations(connection)
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
