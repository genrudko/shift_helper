import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import text

from shift_helper import create_app
from shift_helper.backup import (
    DatabaseBackupError,
    create_database_backup,
    prepare_verified_restore,
    verify_database_backup,
)


def _event_form() -> dict[str, str]:
    return {
        "start_at": "2026-07-29T17:30",
        "asset_label": "ВЭУ №25",
        "event_type": "other",
        "description": "Проверка резервного копирования",
        "reason": "",
        "actions": "",
        "performer": "",
        "error_codes": "",
        "rotor_limit": "",
        "include_in_report": "on",
    }


def _presentation() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "workbookStyles": {"backup-style": {"bl": 1}},
        "sheet": {
            "zoomRatio": 1.1,
            "freeze": {
                "startRow": 1,
                "startColumn": 1,
                "ySplit": 1,
                "xSplit": 1,
            },
            "columnData": {"5": {"w": 340.0, "hd": 0}},
            "rowData": {},
            "cellStyles": {"1": {"5": "backup-style"}},
        },
    }


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_application_creates_verified_startup_and_mutation_backups(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    backups = tmp_path / "backups"

    startup_backups = sorted(backups.glob("shift_helper-*.sqlite3"))
    assert len(startup_backups) == 1
    startup = verify_database_backup(startup_backups[0])
    assert startup.event_count == 0
    assert startup.audit_count == 0
    assert startup.operation_count == 0
    assert startup.presentation_count == 0
    assert startup.application_schema_version == "6"

    response = client.post("/events/new", data=_event_form())
    assert response.status_code == 302
    assert response.headers["X-Shift-Helper-Backup"] == "ok"

    all_backups = sorted(backups.glob("shift_helper-*.sqlite3"))
    assert len(all_backups) == 2
    latest = verify_database_backup(all_backups[-1])
    assert latest.event_count == 1
    assert latest.audit_count == 1
    assert latest.operation_count == 1
    assert latest.presentation_count == 0

    manifest_path = all_backups[-1].with_suffix(".json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifestSchemaVersion"] == 2
    assert manifest["reason"] == "event-mutation"
    assert manifest["databaseFile"] == all_backups[-1].name
    assert manifest["sha256"] == latest.sha256 == _file_sha256(all_backups[-1])
    assert manifest["sizeBytes"] == latest.size_bytes
    assert manifest["applicationSchemaVersion"] == "6"
    assert manifest["eventCount"] == 1
    assert manifest["auditCount"] == 1
    assert manifest["operationCount"] == 1
    assert manifest["presentationCount"] == 0

    health = client.get("/health").get_json()["databaseBackup"]
    assert health["status"] == "ok"
    assert health["path"] == str(all_backups[-1])
    assert health["manifestPath"] == str(manifest_path)
    assert health["sha256"] == latest.sha256
    assert health["eventCount"] == 1
    assert health["auditCount"] == 1
    assert health["operationCount"] == 1
    assert health["presentationCount"] == 0
    assert health["lastError"] is None


def test_backup_preserves_history_and_presentation_state(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    saved_presentation = client.put(
        "/events/api/v2/presentation",
        json={"revision": 0, "presentation": _presentation()},
    )
    assert saved_presentation.status_code == 200

    client.post("/events/new", data=_event_form())
    patched = client.patch(
        "/events/api/v2/records/1",
        json={"revision": 1, "changes": {"description": "Изменённое событие"}},
    )
    assert patched.status_code == 200

    paths = app.extensions["shift_helper_runtime_paths"]
    latest_path = sorted(paths.backups.glob("shift_helper-*.sqlite3"))[-1]
    verification = verify_database_backup(latest_path)
    assert verification.event_count == 1
    assert verification.audit_count == 2
    assert verification.operation_count == 2
    assert verification.presentation_count == 1

    restore_target = tmp_path / "restore" / "shift_helper.sqlite3"
    restored = prepare_verified_restore(latest_path, restore_target)
    assert restored.operation_count == 2
    assert restored.presentation_count == 1


def test_backup_rotation_keeps_only_verified_pairs(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    paths = app.extensions["shift_helper_runtime_paths"]

    for index in range(4):
        create_database_backup(
            paths.database,
            paths.backups,
            reason=f"rotation-{index}",
            retention=2,
        )

    backups = sorted(paths.backups.glob("shift_helper-*.sqlite3"))
    manifests = sorted(paths.backups.glob("shift_helper-*.json"))
    assert len(backups) == 2
    assert len(manifests) == 2
    assert {path.stem for path in backups} == {path.stem for path in manifests}
    for backup in backups:
        verification = verify_database_backup(backup)
        assert verification.application_schema_version == "6"
        assert verification.operation_count == 0
        assert verification.presentation_count == 0


def test_prepare_restore_candidate_is_independently_verified(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    client.post("/events/new", data=_event_form())
    paths = app.extensions["shift_helper_runtime_paths"]
    backup = sorted(paths.backups.glob("shift_helper-*.sqlite3"))[-1]

    destination = tmp_path / "restore-target" / "shift_helper.sqlite3"
    restored = prepare_verified_restore(backup, destination)
    candidate = destination.with_suffix(".sqlite3.restore.pending")

    assert candidate.is_file()
    assert restored.path == candidate.resolve()
    assert restored.sha256 == _file_sha256(backup)
    assert restored.event_count == 1
    assert restored.audit_count == 1
    assert restored.operation_count == 1
    assert restored.presentation_count == 0

    connection = app.extensions["shift_helper_database_engine"].connect()
    try:
        assert connection.scalar(text("SELECT COUNT(*) FROM events")) == 1
    finally:
        connection.close()


def test_corrupt_backup_is_rejected(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"not a sqlite database")

    with pytest.raises(DatabaseBackupError, match="SQLite"):
        verify_database_backup(corrupt)
