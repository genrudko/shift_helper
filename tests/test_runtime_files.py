from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from shift_helper import create_app


def _event_form() -> dict[str, str]:
    return {
        "start_at": "2026-07-29T19:10",
        "asset_label": "ВЭУ №42",
        "event_type": "other",
        "description": "Проверка доступных файлов",
        "reason": "",
        "actions": "",
        "performer": "",
        "error_codes": "",
        "rotor_limit": "",
        "include_in_report": "on",
    }


def test_runtime_status_and_downloads_expose_only_generated_files(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    status_response = client.get("/events/api/v2/runtime-status")
    assert status_response.status_code == 200
    status = status_response.get_json()
    assert status["schemaVersion"] == 1
    assert status["eventMirror"] == {
        "status": "ok",
        "generatedAt": status["eventMirror"]["generatedAt"],
        "recordCount": 0,
        "lastError": None,
        "downloadAvailable": True,
        "downloadUrl": "/events/export.xlsx",
    }
    assert status["databaseBackup"]["status"] == "ok"
    assert status["databaseBackup"]["eventCount"] == 0
    assert status["databaseBackup"]["auditCount"] == 0
    assert status["databaseBackup"]["downloadAvailable"] is True
    assert status["databaseBackup"]["downloadUrl"] == "/backups/latest.zip"
    assert str(tmp_path) not in str(status)

    spreadsheet = client.get("/events/export.xlsx")
    assert spreadsheet.status_code == 200
    assert spreadsheet.data.startswith(b"PK")
    assert spreadsheet.mimetype == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    disposition = spreadsheet.headers["Content-Disposition"]
    assert disposition.startswith("attachment;")
    assert ".xlsx" in disposition

    backup = client.get("/backups/latest.zip")
    assert backup.status_code == 200
    assert backup.data.startswith(b"PK")
    assert backup.mimetype == "application/zip"
    with ZipFile(BytesIO(backup.data)) as archive:
        names = archive.namelist()
        assert len(names) == 2
        assert any(name.endswith(".sqlite3") for name in names)
        assert any(name.endswith(".json") for name in names)


def test_runtime_status_tracks_successful_event_mutation(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    created = client.post("/events/new", data=_event_form())
    assert created.status_code == 302

    status = client.get("/events/api/v2/runtime-status").get_json()
    assert status["eventMirror"]["recordCount"] == 1
    assert status["databaseBackup"]["eventCount"] == 1
    assert status["databaseBackup"]["auditCount"] == 1
    assert status["eventMirror"]["downloadAvailable"] is True
    assert status["databaseBackup"]["downloadAvailable"] is True


def test_missing_or_untrusted_runtime_files_fail_closed(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    paths = app.extensions["shift_helper_runtime_paths"]
    mirror_state = app.extensions["shift_helper_event_mirror"]
    backup_state = app.extensions["shift_helper_database_backup"]

    mirror_path = Path(mirror_state["path"])
    mirror_path.unlink()
    status = client.get("/events/api/v2/runtime-status").get_json()
    assert status["eventMirror"]["downloadAvailable"] is False
    unavailable_mirror = client.get("/events/export.xlsx")
    assert unavailable_mirror.status_code == 503
    assert unavailable_mirror.get_json()["error"]["code"] == "runtime_file_unavailable"

    manifest_path = Path(backup_state["manifestPath"])
    manifest_path.unlink()
    status = client.get("/events/api/v2/runtime-status").get_json()
    assert status["databaseBackup"]["downloadAvailable"] is False
    unavailable_backup = client.get("/backups/latest.zip")
    assert unavailable_backup.status_code == 503

    outside = tmp_path / "outside.xlsx"
    outside.write_bytes(b"not trusted")
    mirror_state.update(status="ok", path=str(outside))
    assert client.get("/events/export.xlsx").status_code == 503

    outside_backup = tmp_path / "outside.sqlite3"
    outside_manifest = tmp_path / "outside.json"
    outside_backup.write_bytes(b"not trusted")
    outside_manifest.write_text("{}", encoding="utf-8")
    backup_state.update(
        status="ok",
        path=str(outside_backup),
        manifestPath=str(outside_manifest),
    )
    assert client.get("/backups/latest.zip").status_code == 503
    assert paths.exports not in (outside.parent, outside_backup.parent)
