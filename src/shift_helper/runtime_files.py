"""Safe download endpoints for generated exports and verified backups."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from flask import Blueprint, Response, current_app, jsonify, send_file

runtime_files_blueprint = Blueprint("runtime_files", __name__)


def _trusted_file(path_value: object, parent: Path) -> Path | None:
    if not isinstance(path_value, str) or not path_value:
        return None
    try:
        candidate = Path(path_value).resolve(strict=True)
        trusted_parent = parent.resolve(strict=True)
    except OSError:
        return None
    if candidate.parent != trusted_parent or not candidate.is_file():
        return None
    return candidate


def _runtime_state() -> tuple[dict[str, Any], dict[str, Any], Any]:
    return (
        current_app.extensions["shift_helper_event_mirror"],
        current_app.extensions["shift_helper_database_backup"],
        current_app.extensions["shift_helper_runtime_paths"],
    )


def _unavailable(message: str) -> tuple[Response, int]:
    return (
        jsonify(
            {
                "error": {
                    "code": "runtime_file_unavailable",
                    "message": message,
                }
            }
        ),
        503,
    )


@runtime_files_blueprint.get("/events/api/v2/runtime-status")
def runtime_status() -> Response:
    mirror_state, backup_state, runtime_paths = _runtime_state()
    mirror_path = _trusted_file(mirror_state.get("path"), runtime_paths.exports)
    backup_path = _trusted_file(backup_state.get("path"), runtime_paths.backups)
    manifest_path = _trusted_file(
        backup_state.get("manifestPath"),
        runtime_paths.backups,
    )
    return jsonify(
        {
            "schemaVersion": 1,
            "eventMirror": {
                "status": mirror_state.get("status"),
                "generatedAt": mirror_state.get("generatedAt"),
                "recordCount": mirror_state.get("recordCount", 0),
                "lastError": mirror_state.get("lastError"),
                "downloadAvailable": mirror_path is not None,
                "downloadUrl": "/events/export.xlsx" if mirror_path else None,
            },
            "databaseBackup": {
                "status": backup_state.get("status"),
                "generatedAt": backup_state.get("generatedAt"),
                "eventCount": backup_state.get("eventCount", 0),
                "auditCount": backup_state.get("auditCount", 0),
                "sha256": backup_state.get("sha256"),
                "lastError": backup_state.get("lastError"),
                "downloadAvailable": backup_path is not None and manifest_path is not None,
                "downloadUrl": (
                    "/backups/latest.zip"
                    if backup_path is not None and manifest_path is not None
                    else None
                ),
            },
        }
    )


@runtime_files_blueprint.get("/events/export.xlsx")
def download_event_mirror() -> Response | tuple[Response, int]:
    mirror_state, _backup_state, runtime_paths = _runtime_state()
    mirror_path = _trusted_file(mirror_state.get("path"), runtime_paths.exports)
    if mirror_state.get("status") != "ok" or mirror_path is None:
        return _unavailable(
            "Excel-копия журнала пока недоступна. Проверьте состояние экспорта."
        )
    return send_file(
        mirror_path,
        as_attachment=True,
        download_name="Журнал событий.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        conditional=True,
    )


@runtime_files_blueprint.get("/backups/latest.zip")
def download_latest_backup() -> Response | tuple[Response, int]:
    _mirror_state, backup_state, runtime_paths = _runtime_state()
    backup_path = _trusted_file(backup_state.get("path"), runtime_paths.backups)
    manifest_path = _trusted_file(
        backup_state.get("manifestPath"),
        runtime_paths.backups,
    )
    if (
        backup_state.get("status") != "ok"
        or backup_path is None
        or manifest_path is None
    ):
        return _unavailable(
            "Проверенная резервная копия пока недоступна."
        )

    archive = BytesIO()
    with ZipFile(archive, mode="w", compression=ZIP_DEFLATED) as bundle:
        bundle.write(backup_path, arcname=backup_path.name)
        bundle.write(manifest_path, arcname=manifest_path.name)
    archive.seek(0)

    generated_at = str(backup_state.get("generatedAt") or "latest")
    safe_stamp = "".join(character for character in generated_at if character.isdigit())[:20]
    filename = f"Shift-Helper-backup-{safe_stamp or 'latest'}.zip"
    return send_file(
        archive,
        as_attachment=True,
        download_name=filename,
        mimetype="application/zip",
        max_age=0,
    )
