"""Flask application factory for Shift-Helper."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from .backup import DatabaseBackupError, create_database_backup
from .database import initialize_database
from .event_batch import event_batch_blueprint
from .event_history import event_history_blueprint
from .event_mirror import EventMirrorWriteError, refresh_event_journal_mirror
from .events import events_blueprint
from .paths import build_runtime_paths, ensure_runtime_directories
from .security import configure_lan_security, load_or_create_session_secret


def create_app(
    *,
    testing: bool = False,
    data_root: Path | None = None,
    lan_mode: bool = False,
    lan_token: str | None = None,
) -> Flask:
    """Create and configure the local Shift-Helper web application."""

    runtime_paths = build_runtime_paths(data_root)
    ensure_runtime_directories(runtime_paths)

    app = Flask(__name__)
    app.config.update(
        TESTING=testing,
        SECRET_KEY=load_or_create_session_secret(runtime_paths.root),
        SESSION_COOKIE_NAME="shift_helper_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
    )
    configure_lan_security(app, enabled=lan_mode, token=lan_token)
    engine = initialize_database(runtime_paths.database)

    mirror_state: dict[str, Any] = {
        "status": "pending",
        "path": None,
        "pendingPath": None,
        "generatedAt": None,
        "recordCount": 0,
        "lastError": None,
    }
    backup_state: dict[str, Any] = {
        "status": "pending",
        "path": None,
        "manifestPath": None,
        "generatedAt": None,
        "sha256": None,
        "eventCount": 0,
        "auditCount": 0,
        "lastError": None,
    }

    app.extensions["shift_helper_runtime_paths"] = runtime_paths
    app.extensions["shift_helper_database_engine"] = engine
    app.extensions["shift_helper_event_mirror"] = mirror_state
    app.extensions["shift_helper_database_backup"] = backup_state
    app.register_blueprint(events_blueprint)
    app.register_blueprint(event_history_blueprint)
    app.register_blueprint(event_batch_blueprint)

    def refresh_event_mirror() -> None:
        try:
            result = refresh_event_journal_mirror(engine, runtime_paths.exports)
        except EventMirrorWriteError as exc:
            app.logger.warning("Event journal mirror is pending: %s", exc)
            mirror_state.update(
                status="error",
                path=str(exc.target),
                pendingPath=str(exc.pending),
                lastError=str(exc),
            )
        except Exception as exc:  # pragma: no cover - defensive runtime reporting
            app.logger.exception("Unexpected event journal mirror failure")
            mirror_state.update(status="error", lastError=str(exc))
        else:
            mirror_state.update(
                status="ok",
                path=str(result.path),
                pendingPath=None,
                generatedAt=result.generated_at.isoformat(timespec="seconds"),
                recordCount=result.record_count,
                lastError=None,
            )

    def create_verified_backup(reason: str) -> None:
        try:
            result = create_database_backup(
                runtime_paths.database,
                runtime_paths.backups,
                reason=reason,
            )
        except DatabaseBackupError as exc:
            app.logger.error("Database backup failed: %s", exc)
            backup_state.update(status="error", lastError=str(exc))
        except Exception as exc:  # pragma: no cover - defensive runtime reporting
            app.logger.exception("Unexpected database backup failure")
            backup_state.update(status="error", lastError=str(exc))
        else:
            backup_state.update(
                status="ok",
                path=str(result.path),
                manifestPath=str(result.manifest_path),
                generatedAt=result.generated_at.isoformat(timespec="microseconds"),
                sha256=result.verification.sha256,
                eventCount=result.verification.event_count,
                auditCount=result.verification.audit_count,
                lastError=None,
            )

    refresh_event_mirror()
    create_verified_backup("startup")

    @app.after_request
    def synchronize_derived_data(response):
        mutating_event_request = (
            request.path.startswith("/events")
            and request.method in {"POST", "PATCH", "PUT", "DELETE"}
            and response.status_code < 400
        )
        if mutating_event_request:
            refresh_event_mirror()
            create_verified_backup("event-mutation")
        response.headers["X-Shift-Helper-Event-Mirror"] = mirror_state["status"]
        response.headers["X-Shift-Helper-Backup"] = backup_state["status"]
        return response

    @app.get("/")
    def index() -> str:
        return render_template(
            "index.html",
            database_path=runtime_paths.database,
            data_root=runtime_paths.root,
        )

    @app.get("/health")
    def health():
        return jsonify(
            {
                "application": "Shift-Helper",
                "status": "ok",
                "database": str(runtime_paths.database),
                "lanMode": app.extensions["shift_helper_lan"],
                "eventMirror": mirror_state,
                "databaseBackup": backup_state,
            }
        )

    return app
