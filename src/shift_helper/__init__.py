"""Shift-Helper package.

The active product entry point is the workbook-oriented command-line core.  The
legacy Flask application remains importable during the pivot only so the
pre-pivot regression suite can keep proving that no unrelated behaviour was
silently damaged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def create_app(*, testing: bool = False, data_root: Path | None = None) -> Any:
    """Load the frozen pre-pivot Flask application lazily for compatibility tests."""

    from .app import create_app as legacy_create_app

    return legacy_create_app(testing=testing, data_root=data_root)


__all__ = ["create_app"]
