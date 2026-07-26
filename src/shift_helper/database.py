"""SQLite initialization for the local Shift-Helper datastore."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from .models import Base

APPLICATION_SCHEMA_VERSION = "2"


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
