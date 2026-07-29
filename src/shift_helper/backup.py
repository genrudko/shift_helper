"""Verified rolling backups for the primary Shift-Helper SQLite database."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock

DEFAULT_BACKUP_RETENTION = 20
BACKUP_MANIFEST_SCHEMA_VERSION = 2
_BACKUP_LOCK = Lock()


@dataclass(frozen=True, slots=True)
class BackupVerification:
    path: Path
    sha256: str
    size_bytes: int
    application_schema_version: str
    event_count: int
    audit_count: int
    operation_count: int
    presentation_count: int


@dataclass(frozen=True, slots=True)
class DatabaseBackupResult:
    path: Path
    manifest_path: Path
    generated_at: datetime
    reason: str
    verification: BackupVerification


class DatabaseBackupError(RuntimeError):
    """Raised when a database snapshot cannot be created or verified."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scalar(connection: sqlite3.Connection, statement: str) -> object:
    row = connection.execute(statement).fetchone()
    if row is None:
        raise DatabaseBackupError(
            f"Проверка резервной копии не вернула результат: {statement}"
        )
    return row[0]


def verify_database_backup(path: Path) -> BackupVerification:
    """Open a snapshot independently and prove that it is restorable SQLite data."""

    path = path.resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise DatabaseBackupError("Файл резервной копии отсутствует или пуст.")

    try:
        connection = sqlite3.connect(path, timeout=5)
        connection.execute("PRAGMA query_only = ON")
        quick_check = _scalar(connection, "PRAGMA quick_check")
        if quick_check != "ok":
            raise DatabaseBackupError(f"SQLite quick_check: {quick_check}")

        required_tables = {
            "events",
            "event_audit",
            "event_operation",
            "journal_presentation",
            "app_metadata",
        }
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing_tables = required_tables - tables
        if missing_tables:
            missing = ", ".join(sorted(missing_tables))
            raise DatabaseBackupError(
                f"В резервной копии отсутствуют таблицы: {missing}."
            )

        schema_row = connection.execute(
            "SELECT value FROM app_metadata WHERE key = 'schema_version'"
        ).fetchone()
        if schema_row is None or not isinstance(schema_row[0], str):
            raise DatabaseBackupError(
                "В резервной копии отсутствует версия схемы приложения."
            )

        event_count = int(_scalar(connection, "SELECT COUNT(*) FROM events"))
        audit_count = int(_scalar(connection, "SELECT COUNT(*) FROM event_audit"))
        operation_count = int(
            _scalar(connection, "SELECT COUNT(*) FROM event_operation")
        )
        presentation_count = int(
            _scalar(connection, "SELECT COUNT(*) FROM journal_presentation")
        )
    except sqlite3.DatabaseError as exc:
        raise DatabaseBackupError(
            f"Резервная копия не открывается как SQLite: {exc}"
        ) from exc
    finally:
        if "connection" in locals():
            connection.close()

    return BackupVerification(
        path=path,
        sha256=_sha256(path),
        size_bytes=path.stat().st_size,
        application_schema_version=schema_row[0],
        event_count=event_count,
        audit_count=audit_count,
        operation_count=operation_count,
        presentation_count=presentation_count,
    )


def _rotate_backups(backups_directory: Path, retention: int) -> None:
    if retention < 1:
        raise ValueError("Количество хранимых резервных копий должно быть не меньше одной.")

    backups = sorted(
        backups_directory.glob("shift_helper-*.sqlite3"),
        key=lambda candidate: candidate.name,
        reverse=True,
    )
    for obsolete in backups[retention:]:
        manifest = obsolete.with_suffix(".json")
        obsolete.unlink(missing_ok=True)
        manifest.unlink(missing_ok=True)


def create_database_backup(
    database_path: Path,
    backups_directory: Path,
    *,
    reason: str,
    retention: int = DEFAULT_BACKUP_RETENTION,
) -> DatabaseBackupResult:
    """Create, verify and publish one consistent SQLite Online Backup snapshot."""

    database_path = database_path.resolve()
    backups_directory = backups_directory.resolve()
    if not database_path.is_file():
        raise DatabaseBackupError("Основная база данных отсутствует.")

    backups_directory.mkdir(parents=True, exist_ok=True)
    safe_reason = "".join(
        character if character.isalnum() else "-" for character in reason
    )
    safe_reason = safe_reason.strip("-")[:32] or "snapshot"
    generated_at = datetime.now()
    stamp = generated_at.strftime("%Y%m%dT%H%M%S%f")
    target = backups_directory / f"shift_helper-{stamp}-{safe_reason}.sqlite3"
    pending = backups_directory / f".{target.name}.pending"
    manifest = target.with_suffix(".json")
    pending_manifest = backups_directory / f".{manifest.name}.pending"

    with _BACKUP_LOCK:
        pending.unlink(missing_ok=True)
        pending_manifest.unlink(missing_ok=True)
        try:
            source = sqlite3.connect(database_path, timeout=5)
            destination = sqlite3.connect(pending, timeout=5)
            try:
                source.backup(destination)
                destination.commit()
            finally:
                destination.close()
                source.close()

            verification = verify_database_backup(pending)
            os.replace(pending, target)
            verification = BackupVerification(
                path=target,
                sha256=verification.sha256,
                size_bytes=verification.size_bytes,
                application_schema_version=verification.application_schema_version,
                event_count=verification.event_count,
                audit_count=verification.audit_count,
                operation_count=verification.operation_count,
                presentation_count=verification.presentation_count,
            )
            manifest_payload = {
                "manifestSchemaVersion": BACKUP_MANIFEST_SCHEMA_VERSION,
                "generatedAt": generated_at.isoformat(timespec="microseconds"),
                "reason": reason,
                "databaseFile": target.name,
                "sha256": verification.sha256,
                "sizeBytes": verification.size_bytes,
                "applicationSchemaVersion": verification.application_schema_version,
                "eventCount": verification.event_count,
                "auditCount": verification.audit_count,
                "operationCount": verification.operation_count,
                "presentationCount": verification.presentation_count,
            }
            pending_manifest.write_text(
                json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(pending_manifest, manifest)
            _rotate_backups(backups_directory, retention)
        except Exception as exc:
            pending.unlink(missing_ok=True)
            pending_manifest.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            manifest.unlink(missing_ok=True)
            if isinstance(exc, DatabaseBackupError):
                raise
            raise DatabaseBackupError(
                f"Не удалось создать резервную копию: {exc}"
            ) from exc

    return DatabaseBackupResult(
        path=target,
        manifest_path=manifest,
        generated_at=generated_at,
        reason=reason,
        verification=verification,
    )


def prepare_verified_restore(
    backup_path: Path,
    destination_path: Path,
) -> BackupVerification:
    """Prepare a verified restore candidate; the application must be stopped to activate it."""

    verification = verify_database_backup(backup_path)
    destination_path = destination_path.resolve()
    candidate = destination_path.with_suffix(
        destination_path.suffix + ".restore.pending"
    )
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.unlink(missing_ok=True)
    shutil.copy2(backup_path, candidate)
    candidate_verification = verify_database_backup(candidate)
    if candidate_verification.sha256 != verification.sha256:
        candidate.unlink(missing_ok=True)
        raise DatabaseBackupError(
            "Контрольная сумма кандидата восстановления не совпала."
        )
    return candidate_verification
