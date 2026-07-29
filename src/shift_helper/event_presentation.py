"""Presentation-only persistence for the Univer event journal workbook."""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import text
from sqlalchemy.engine import Engine

PRESENTATION_KEY = "event-journal-v2"
PRESENTATION_SCHEMA_VERSION = 1
PRESENTATION_APPLICATION_SCHEMA_VERSION = "5"
MAX_PRESENTATION_BYTES = 1_000_000
MAX_WORKBOOK_STYLES = 5_000
MAX_COLUMNS = 100
MAX_ROWS = 5_000
MAX_STYLED_CELLS = 50_000
_FORBIDDEN_STYLE_KEYS = {
    "cellData",
    "f",
    "formula",
    "id",
    "mergeData",
    "p",
    "revision",
    "si",
    "v",
    "value",
}

event_presentation_blueprint = Blueprint(
    "event_presentation",
    __name__,
    url_prefix="/events/api/v2",
)


class PresentationValidationError(ValueError):
    """Raised when the client attempts to persist data outside the UI projection."""


def _database_engine() -> Engine:
    return current_app.extensions["shift_helper_database_engine"]


def initialize_event_presentation(engine: Engine) -> None:
    """Install the additive presentation schema after the core database schema."""

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS journal_presentation (
                    key TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL CHECK (revision >= 1),
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
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
            {"schema_version": PRESENTATION_APPLICATION_SCHEMA_VERSION},
        )


def _empty_presentation() -> dict[str, object]:
    return {
        "schemaVersion": PRESENTATION_SCHEMA_VERSION,
        "workbookStyles": {},
        "sheet": {
            "zoomRatio": 1,
            "freeze": {
                "startRow": 1,
                "startColumn": 1,
                "ySplit": 1,
                "xSplit": 1,
            },
            "columnData": {},
            "rowData": {},
            "cellStyles": {},
        },
    }


def _error(
    code: str,
    message: str,
    *,
    status: int,
    **details: object,
) -> tuple[Response, int]:
    return jsonify({"error": {"code": code, "message": message, **details}}), status


def _validate_json_style(value: Any, *, depth: int = 0) -> None:
    if depth > 12:
        raise PresentationValidationError(
            "Стиль содержит слишком глубокую структуру."
        )
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PresentationValidationError(
                "Стиль содержит некорректное число."
            )
        return
    if isinstance(value, list):
        if len(value) > 256:
            raise PresentationValidationError(
                "Стиль содержит слишком большой список."
            )
        for item in value:
            _validate_json_style(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > 128:
            raise PresentationValidationError(
                "Стиль содержит слишком много свойств."
            )
        for key, item in value.items():
            if not isinstance(key, str):
                raise PresentationValidationError(
                    "Ключи стиля должны быть строками."
                )
            if key in _FORBIDDEN_STYLE_KEYS:
                raise PresentationValidationError(
                    "Presentation-state не должен содержать значения "
                    "ячеек или формулы."
                )
            _validate_json_style(item, depth=depth + 1)
        return
    raise PresentationValidationError(
        "Стиль содержит неподдерживаемое значение."
    )


def _numeric_index(value: str, *, maximum: int, label: str) -> int:
    if not value.isdigit():
        raise PresentationValidationError(f"Некорректный индекс {label}.")
    index = int(value)
    if index < 0 or index >= maximum:
        raise PresentationValidationError(
            f"Индекс {label} выходит за допустимый диапазон."
        )
    return index


def _validate_dimension_map(
    value: Any,
    *,
    maximum: int,
    size_key: str,
    label: str,
) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict) or len(value) > maximum:
        raise PresentationValidationError(f"Некорректная геометрия {label}.")
    normalized: dict[str, dict[str, object]] = {}
    for raw_index, raw_settings in value.items():
        if not isinstance(raw_index, str):
            raise PresentationValidationError(f"Некорректный индекс {label}.")
        index = _numeric_index(raw_index, maximum=maximum, label=label)
        if not isinstance(raw_settings, dict):
            raise PresentationValidationError(
                f"Некорректные параметры {label}."
            )
        unknown = set(raw_settings) - {size_key, "hd"}
        if unknown:
            raise PresentationValidationError(f"Неизвестные параметры {label}.")
        settings: dict[str, object] = {}
        if size_key in raw_settings:
            size = raw_settings[size_key]
            if not isinstance(size, (int, float)) or isinstance(size, bool):
                raise PresentationValidationError(f"Некорректный размер {label}.")
            if not math.isfinite(float(size)) or not 0 <= float(size) <= 2_000:
                raise PresentationValidationError(
                    f"Размер {label} вне допустимого диапазона."
                )
            settings[size_key] = float(size)
        if "hd" in raw_settings:
            hidden = raw_settings["hd"]
            if hidden not in (0, 1, False, True):
                raise PresentationValidationError(
                    f"Некорректный признак скрытия {label}."
                )
            settings["hd"] = 1 if bool(hidden) else 0
        normalized[str(index)] = settings
    return normalized


def _validate_freeze(value: Any) -> dict[str, int]:
    required = {"startRow", "startColumn", "ySplit", "xSplit"}
    if not isinstance(value, dict) or set(value) != required:
        raise PresentationValidationError(
            "Некорректная конфигурация закрепления "
            "областей."
        )
    result: dict[str, int] = {}
    for key in required:
        item = value[key]
        if (
            isinstance(item, bool)
            or not isinstance(item, int)
            or not 0 <= item <= MAX_ROWS
        ):
            raise PresentationValidationError(
                "Некорректная конфигурация закрепления "
                "областей."
            )
        result[key] = item
    return result


def _validate_cell_styles(value: Any) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict) or len(value) > MAX_ROWS:
        raise PresentationValidationError(
            "Некорректная карта оформления ячеек."
        )
    normalized: dict[str, dict[str, object]] = {}
    styled_cell_count = 0
    for raw_row, raw_columns in value.items():
        if not isinstance(raw_row, str):
            raise PresentationValidationError(
                "Некорректный индекс строки оформления."
            )
        row = _numeric_index(raw_row, maximum=MAX_ROWS, label="строки оформления")
        if not isinstance(raw_columns, dict) or len(raw_columns) > MAX_COLUMNS:
            raise PresentationValidationError(
                "Некорректная карта оформления строки."
            )
        columns: dict[str, object] = {}
        for raw_column, style in raw_columns.items():
            if not isinstance(raw_column, str):
                raise PresentationValidationError(
                    "Некорректный индекс колонки оформления."
                )
            column = _numeric_index(
                raw_column,
                maximum=MAX_COLUMNS,
                label="колонки оформления",
            )
            if not isinstance(style, (str, dict)):
                raise PresentationValidationError(
                    "Некорректный стиль ячейки."
                )
            _validate_json_style(style)
            columns[str(column)] = style
            styled_cell_count += 1
            if styled_cell_count > MAX_STYLED_CELLS:
                raise PresentationValidationError(
                    "Слишком много оформленных ячеек."
                )
        if columns:
            normalized[str(row)] = columns
    return normalized


def validate_presentation(value: Any) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PresentationValidationError("Ожидался объект presentation-state.")
    if set(value) != {"schemaVersion", "workbookStyles", "sheet"}:
        raise PresentationValidationError(
            "Некорректная структура presentation-state."
        )
    if value["schemaVersion"] != PRESENTATION_SCHEMA_VERSION:
        raise PresentationValidationError(
            "Неподдерживаемая версия presentation-state."
        )

    workbook_styles = value["workbookStyles"]
    if (
        not isinstance(workbook_styles, dict)
        or len(workbook_styles) > MAX_WORKBOOK_STYLES
    ):
        raise PresentationValidationError(
            "Некорректная таблица стилей книги."
        )
    for style_id, style in workbook_styles.items():
        if not isinstance(style_id, str) or not style_id or len(style_id) > 200:
            raise PresentationValidationError(
                "Некорректный идентификатор стиля."
            )
        _validate_json_style(style)

    sheet = value["sheet"]
    expected_sheet_keys = {
        "zoomRatio",
        "freeze",
        "columnData",
        "rowData",
        "cellStyles",
    }
    if not isinstance(sheet, dict) or set(sheet) != expected_sheet_keys:
        raise PresentationValidationError(
            "Некорректная структура оформления листа."
        )
    zoom = sheet["zoomRatio"]
    if isinstance(zoom, bool) or not isinstance(zoom, (int, float)):
        raise PresentationValidationError("Некорректный масштаб листа.")
    zoom_value = float(zoom)
    if not math.isfinite(zoom_value) or not 0.1 <= zoom_value <= 4:
        raise PresentationValidationError(
            "Масштаб листа должен быть от 10% до 400%."
        )

    normalized = {
        "schemaVersion": PRESENTATION_SCHEMA_VERSION,
        "workbookStyles": workbook_styles,
        "sheet": {
            "zoomRatio": zoom_value,
            "freeze": _validate_freeze(sheet["freeze"]),
            "columnData": _validate_dimension_map(
                sheet["columnData"],
                maximum=MAX_COLUMNS,
                size_key="w",
                label="колонок",
            ),
            "rowData": _validate_dimension_map(
                sheet["rowData"],
                maximum=MAX_ROWS,
                size_key="h",
                label="строк",
            ),
            "cellStyles": _validate_cell_styles(sheet["cellStyles"]),
        },
    }
    encoded = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_PRESENTATION_BYTES:
        raise PresentationValidationError(
            "Presentation-state превышает допустимый размер."
        )
    return normalized


def _row_state(row: Any) -> dict[str, object]:
    return {
        "schemaVersion": PRESENTATION_SCHEMA_VERSION,
        "revision": int(row["revision"]),
        "updatedAt": row["updated_at"],
        "presentation": json.loads(row["payload_json"]),
    }


def _current_state(connection: Any) -> dict[str, object]:
    row = connection.execute(
        text(
            """
            SELECT revision, payload_json, updated_at
            FROM journal_presentation
            WHERE key = :key
            """
        ),
        {"key": PRESENTATION_KEY},
    ).mappings().one_or_none()
    if row is None:
        return {
            "schemaVersion": PRESENTATION_SCHEMA_VERSION,
            "revision": 0,
            "updatedAt": None,
            "presentation": _empty_presentation(),
        }
    return _row_state(row)


@event_presentation_blueprint.get("/presentation")
def get_presentation() -> Response:
    with _database_engine().connect() as connection:
        return jsonify(_current_state(connection))


@event_presentation_blueprint.put("/presentation")
def put_presentation() -> tuple[Response, int] | Response:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("invalid_json", "Ожидался JSON-объект.", status=400)
    revision = payload.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        return _error(
            "invalid_revision",
            "Укажите корректную ревизию оформления.",
            status=400,
        )
    try:
        presentation = validate_presentation(payload.get("presentation"))
    except PresentationValidationError as exc:
        return _error("validation_error", str(exc), status=422)

    serialized = json.dumps(
        presentation,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    updated_at = datetime.now().isoformat(timespec="microseconds")
    engine = _database_engine()
    with engine.begin() as connection:
        current = _current_state(connection)
        current_revision = int(current["revision"])
        if current_revision != revision:
            return _error(
                "revision_conflict",
                "Оформление уже изменено на другом "
                "рабочем месте.",
                status=409,
                current=current,
            )
        current_serialized = json.dumps(
            current["presentation"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if current_serialized == serialized:
            return jsonify(current)

        next_revision = revision + 1
        if revision == 0:
            result = connection.execute(
                text(
                    """
                    INSERT INTO journal_presentation (
                        key, revision, payload_json, updated_at
                    ) VALUES (
                        :key, :revision, :payload_json, :updated_at
                    )
                    ON CONFLICT(key) DO NOTHING
                    """
                ),
                {
                    "key": PRESENTATION_KEY,
                    "revision": next_revision,
                    "payload_json": serialized,
                    "updated_at": updated_at,
                },
            )
        else:
            result = connection.execute(
                text(
                    """
                    UPDATE journal_presentation
                    SET revision = :next_revision,
                        payload_json = :payload_json,
                        updated_at = :updated_at
                    WHERE key = :key AND revision = :revision
                    """
                ),
                {
                    "key": PRESENTATION_KEY,
                    "revision": revision,
                    "next_revision": next_revision,
                    "payload_json": serialized,
                    "updated_at": updated_at,
                },
            )
        if result.rowcount != 1:
            return _error(
                "revision_conflict",
                "Оформление уже изменено на другом "
                "рабочем месте.",
                status=409,
                current=_current_state(connection),
            )

    return jsonify(
        {
            "schemaVersion": PRESENTATION_SCHEMA_VERSION,
            "revision": next_revision,
            "updatedAt": updated_at,
            "presentation": presentation,
        }
    )
