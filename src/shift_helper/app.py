"""Flask application factory for Shift-Helper."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template

from .database import initialize_database
from .events import events_blueprint
from .paths import build_runtime_paths, ensure_runtime_directories


def create_app(*, testing: bool = False, data_root: Path | None = None) -> Flask:
    """Create and configure the local Shift-Helper web application."""
    app = Flask(__name__)
    app.config.update(
        TESTING=testing,
        SECRET_KEY="shift-helper-local-session",
    )

    runtime_paths = build_runtime_paths(data_root)
    ensure_runtime_directories(runtime_paths)
    engine = initialize_database(runtime_paths.database)

    app.extensions["shift_helper_runtime_paths"] = runtime_paths
    app.extensions["shift_helper_database_engine"] = engine
    app.register_blueprint(events_blueprint)

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
            }
        )

    return app
