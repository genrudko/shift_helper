"""Cross-platform runtime paths for user-owned Shift-Helper data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    root: Path
    database: Path
    exports: Path
    backups: Path
    imports: Path
    logs: Path


def build_runtime_paths(data_root: Path | None = None) -> RuntimePaths:
    """Return all writable runtime paths without requiring administrator rights."""
    root = Path(data_root) if data_root is not None else user_data_path(
        appname="Shift-Helper",
        appauthor="genrudko",
        roaming=False,
        ensure_exists=False,
    )
    root = root.expanduser().resolve()
    return RuntimePaths(
        root=root,
        database=root / "data" / "shift_helper.sqlite3",
        exports=root / "exports",
        backups=root / "backups",
        imports=root / "imports",
        logs=root / "logs",
    )


def ensure_runtime_directories(paths: RuntimePaths) -> None:
    """Create user-owned writable directories required by the application."""
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    paths.exports.mkdir(parents=True, exist_ok=True)
    paths.backups.mkdir(parents=True, exist_ok=True)
    paths.imports.mkdir(parents=True, exist_ok=True)
    paths.logs.mkdir(parents=True, exist_ok=True)
