"""Collision-free hidden storage for exact report-form workbooks."""

from __future__ import annotations

from datetime import date, datetime
from types import ModuleType
from typing import Any

STATUS_NAME_COL = 9  # J
STATUS_VALUE_COL = 10  # K
META_KEY_COL = 12  # M
META_VALUE_COL = 13  # N
STATUSES = ("Работа", "Останов", "Авария", "Ремонт")


def _collect_statuses(prep) -> dict[str, str]:
    values: dict[str, str] = {}
    for name_col, value_col in ((6, 7), (STATUS_NAME_COL, STATUS_VALUE_COL)):
        for row in range(1, 90):
            name = str(prep.getCellByPosition(name_col, row).getString()).strip()
            status = str(prep.getCellByPosition(value_col, row).getString()).strip()
            if name.startswith("ВЭУ-") and status in STATUSES:
                values[name] = status
    return values


def _collect_meta(prep, keys: tuple[str, ...]) -> dict[str, object]:
    values: dict[str, object] = {}
    for key_col, value_col in ((9, 10), (META_KEY_COL, META_VALUE_COL)):
        for row in range(1, 40):
            key = str(prep.getCellByPosition(key_col, row).getString()).strip()
            if key in keys:
                cell = prep.getCellByPosition(value_col, row)
                text = str(cell.getString()).strip()
                values[key] = text if text else float(cell.getValue())
    return values


def _ensure_service(module: ModuleType, runtime: Any, document) -> None:
    prep = document.getSheets().getByName(runtime.INPUT_PREP)
    statuses = _collect_statuses(prep)
    meta = _collect_meta(prep, tuple(module.META))

    prep.getCellByPosition(STATUS_NAME_COL, 0).setString("ВЭУ")
    prep.getCellByPosition(STATUS_VALUE_COL, 0).setString("Статус ВЭУ")
    for number in range(1, 85):
        name = f"ВЭУ-{number}"
        prep.getCellByPosition(STATUS_NAME_COL, number).setString(name)
        prep.getCellByPosition(STATUS_VALUE_COL, number).setString(
            statuses.get(name, "Работа")
        )

    prep.getCellByPosition(META_KEY_COL, 0).setString("Служебный параметр")
    prep.getCellByPosition(META_VALUE_COL, 0).setString("Значение")
    for row, key in enumerate(module.META, start=1):
        prep.getCellByPosition(META_KEY_COL, row).setString(key)
        value = meta.get(key)
        if value not in (None, ""):
            runtime._write_value(
                prep.getCellByPosition(META_VALUE_COL, row),
                value,
                document,
                "DD.MM.YYYY" if isinstance(value, (date, datetime)) else None,
            )

    for column in (
        STATUS_NAME_COL,
        STATUS_VALUE_COL,
        META_KEY_COL,
        META_VALUE_COL,
    ):
        try:
            prep.getColumns().getByIndex(column).IsVisible = False
        except Exception:
            pass


def _meta(module: ModuleType, runtime: Any, document, key: str, value=...):
    _ensure_service(module, runtime, document)
    prep = document.getSheets().getByName(runtime.INPUT_PREP)
    row = tuple(module.META).index(key) + 1
    cell = prep.getCellByPosition(META_VALUE_COL, row)
    if value is ...:
        return runtime._cell_value(cell, document)
    runtime._write_value(
        cell,
        value,
        document,
        "DD.MM.YYYY" if isinstance(value, (date, datetime)) else None,
    )


def _status_map(module: ModuleType, runtime: Any, document) -> dict[str, str]:
    _ensure_service(module, runtime, document)
    prep = document.getSheets().getByName(runtime.INPUT_PREP)
    return {
        str(prep.getCellByPosition(STATUS_NAME_COL, row).getString()).strip():
        str(prep.getCellByPosition(STATUS_VALUE_COL, row).getString()).strip()
        for row in range(1, 85)
    }


def install_exact_storage_contract(module: ModuleType) -> None:
    """Patch exact-form helpers before they are installed into the runtime."""

    if getattr(module, "_EXACT_STORAGE_CONTRACT_004_APPLIED", False):
        return

    module._ensure_service = lambda runtime, document: _ensure_service(
        module, runtime, document
    )
    module._meta = lambda runtime, document, key, value=...: _meta(
        module, runtime, document, key, value
    )
    module._status_map = lambda runtime, document: _status_map(
        module, runtime, document
    )

    original_apply = module._apply_formulas

    def apply_formulas(runtime, document) -> None:
        original_apply(runtime, document)
        main = document.getSheets().getByName(runtime.INPUT_MAIN)
        for row, status in zip(
            range(4, 8),
            ("Останов", "Работа", "Авария", "Ремонт"),
            strict=True,
        ):
            main.getCellRangeByName(f"F{row}").setFormula(
                "=COUNTIF('Подготовка рапорта'.K2:K85;"
                f'"{status}")'
            )
        try:
            document.calculateAll()
        except Exception:
            pass

    module._apply_formulas = apply_formulas
    module._EXACT_STORAGE_CONTRACT_004_APPLIED = True
