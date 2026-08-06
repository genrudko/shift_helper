"""One-time migration from legacy input grids to exact report-form sheets."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

import uno

_STATUSES = ("Работа", "Останов", "Авария", "Ремонт")
_MANUAL_MAIN_KEYS = (
    "Средняя нагрузка за предыдущие сутки, МВт",
    "Текущая нагрузка на 07:00, МВт",
    "Выработка за предыдущие сутки, кВт*ч",
    "Выработка с начала месяца, кВт*ч",
    "Собственные нужды за сутки, кВт*ч",
    "Собственные нужды с начала месяца, кВт*ч",
    "Температура наружного воздуха, °C",
    "Скорость ветра, м/с",
    "Направление ветра",
    "Напряжение U 35 кВ, кВ",
    "Напряжение U 110/220/330 кВ, кВ",
    "Мощность Q 35 кВ, МВАр",
    "Мощность Q 110/220/330 кВ, МВАр",
)


def _value(runtime: Any, sheet, column: int, row: int, document):
    return runtime._cell_value(sheet.getCellByPosition(column, row), document)


def _present(value: object) -> bool:
    return value not in (None, "")


def _legacy_rows(
    runtime: Any,
    document,
    sheet_name: str,
    header: str,
    columns: int,
) -> list[list[object]] | None:
    sheets = document.getSheets()
    if not sheets.hasByName(sheet_name):
        return None
    sheet = sheets.getByName(sheet_name)
    if str(sheet.getCellByPosition(0, 0).getString()).strip() != header:
        return None
    rows: list[list[object]] = []
    for row in range(1, runtime._last_used_row(sheet) + 1):
        values = [_value(runtime, sheet, column, row, document) for column in range(columns)]
        if any(_present(value) for value in values):
            rows.append(values)
    return rows


def _legacy_main(runtime: Any, document) -> dict[str, object] | None:
    sheets = document.getSheets()
    if not sheets.hasByName(runtime.INPUT_MAIN):
        return None
    sheet = sheets.getByName(runtime.INPUT_MAIN)
    known = set(getattr(runtime, "_MAIN_KEYS", ()))
    values: dict[str, object] = {}
    for row in range(1, max(runtime._last_used_row(sheet), 24) + 1):
        key = str(sheet.getCellByPosition(0, row).getString()).strip()
        if key in known:
            values[key] = _value(runtime, sheet, 1, row, document)
    if len(values) < 3:
        return None
    values["_plans"] = {
        month: float(value)
        for month in range(1, 13)
        if isinstance((value := _value(runtime, sheet, 4, month, document)), (int, float))
    }
    values["_facts"] = {
        month: float(value)
        for month in range(1, 13)
        if isinstance((value := _value(runtime, sheet, 5, month, document)), (int, float))
    }
    return values


def _legacy_state(runtime: Any, document) -> list[list[object]] | None:
    sheets = document.getSheets()
    if not sheets.hasByName(runtime.INPUT_STATE):
        return None
    sheet = sheets.getByName(runtime.INPUT_STATE)
    if str(sheet.getCellByPosition(2, 0).getString()).strip() != "ВЭУ":
        return None
    rows: list[list[object]] = []
    for row in range(1, runtime._last_used_row(sheet) + 1):
        values = [_value(runtime, sheet, column, row, document) for column in range(11)]
        if str(values[2] or "").strip().startswith("ВЭУ-"):
            rows.append(values)
    return rows


def _snapshot(runtime: Any, document) -> dict[str, object]:
    return {
        "main": _legacy_main(runtime, document),
        "commands": _legacy_rows(
            runtime, document, runtime.INPUT_COMMANDS, "ГТП", 6
        ),
        "violations": _legacy_rows(
            runtime, document, runtime.INPUT_VIOLATIONS, "Категория", 6
        ),
        "state": _legacy_state(runtime, document),
        "works": _legacy_rows(
            runtime, document, runtime.INPUT_WORKS, "Вид заявки", 11
        ),
        "defects": _legacy_rows(
            runtime, document, runtime.INPUT_DEFECTS, "№", 10
        ),
    }


def _clear(range_) -> None:
    range_.clearContents(1023)


def _copy_row_style(sheet, template_row: int, row: int, last_column: int) -> None:
    if row <= template_row:
        return
    source = sheet.getCellRangeByPosition(
        0, template_row, last_column, template_row
    ).getRangeAddress()
    destination = uno.createUnoStruct("com.sun.star.table.CellAddress")
    destination.Sheet = source.Sheet
    destination.Column = 0
    destination.Row = row
    sheet.copyRange(destination, source)
    _clear(sheet.getCellRangeByPosition(0, row, last_column, row))


def _write_row(
    runtime: Any,
    document,
    sheet,
    row: int,
    start_column: int,
    values: Iterable[object],
) -> None:
    for offset, value in enumerate(values):
        runtime._write_value(
            sheet.getCellByPosition(start_column + offset, row),
            value,
            document,
            "DD.MM.YYYY HH:MM",
        )


def _reset_main(module, runtime: Any, document, snapshot: dict[str, object] | None) -> None:
    sheet = document.getSheets().getByName(runtime.INPUT_MAIN)
    for key in _MANUAL_MAIN_KEYS:
        _clear(module._cell(sheet, module.MAIN[key]))
    _clear(sheet.getCellRangeByPosition(8, 4, 9, 15))
    if not snapshot:
        return
    for key in _MANUAL_MAIN_KEYS:
        value = snapshot.get(key)
        if _present(value):
            module._set_main(runtime, sheet, key, value, document)
    for key in ("Дата рапорта", "ФИО НСС"):
        value = snapshot.get(key)
        if _present(value):
            module._set_main(runtime, sheet, key, value, document)
    for month, value in dict(snapshot.get("_plans", {})).items():
        runtime._write_value(sheet.getCellByPosition(8, int(month) + 3), value)
    for month, value in dict(snapshot.get("_facts", {})).items():
        runtime._write_value(sheet.getCellByPosition(9, int(month) + 3), value)


def _reset_simple(
    runtime: Any,
    document,
    sheet_name: str,
    rows: list[list[object]] | None,
    *,
    data_start: int,
    template_end: int,
    last_column: int,
    start_column: int = 1,
) -> None:
    sheet = document.getSheets().getByName(sheet_name)
    end = max(runtime._last_used_row(sheet), template_end, data_start)
    _clear(sheet.getCellRangeByPosition(start_column, data_start, last_column, end))
    for index, values in enumerate(rows or []):
        row = data_start + index
        _copy_row_style(sheet, template_end, row, last_column)
        _write_row(runtime, document, sheet, row, start_column, values)


def _reset_violations(runtime: Any, document, rows: list[list[object]] | None) -> None:
    sheet = document.getSheets().getByName(runtime.INPUT_VIOLATIONS)
    positions = {
        "ОТиПБ": iter((3, 4)),
        "Экология": iter((7, 8)),
        "Объектовая безопасность": iter((11, 12)),
    }
    for first, last in ((3, 4), (7, 8), (11, 12)):
        _clear(sheet.getCellRangeByPosition(1, first, 5, last))
    for values in rows or []:
        category = str(values[0] or "").strip()
        target = positions.get(category)
        if target is None:
            continue
        try:
            row = next(target)
        except StopIteration:
            continue
        _write_row(runtime, document, sheet, row, 1, values[1:6])


def _status(module, values: list[object]) -> str:
    explicit = str(values[7] or "").strip()
    if explicit == "Авария":
        return explicit
    inferred = module._infer(values[8], values[6], values[5])
    return inferred if inferred in _STATUSES else "Работа"


def _reset_state(module, runtime: Any, document, rows: list[list[object]] | None) -> None:
    sheets = document.getSheets()
    sheet = sheets.getByName(runtime.INPUT_STATE)
    target: dict[str, int] = {}
    for row in range(3, max(runtime._last_used_row(sheet), 97) + 1):
        name = str(sheet.getCellByPosition(3, row).getString()).strip()
        if name.startswith("ВЭУ-"):
            target[name] = row
            runtime._write_value(sheet.getCellByPosition(4, row), 2.5)
            runtime._write_value(sheet.getCellByPosition(5, row), 2.5)
            runtime._write_value(sheet.getCellByPosition(6, row), 0.0)
            _clear(sheet.getCellRangeByPosition(8, row, 10, row))
    prep = sheets.getByName(runtime.INPUT_PREP)
    for number in range(1, 85):
        prep.getCellByPosition(9, number).setString(f"ВЭУ-{number}")
        prep.getCellByPosition(10, number).setString("Работа")
    for values in rows or []:
        name = str(values[2] or "").strip()
        row = target.get(name)
        if row is None:
            continue
        for column, value in zip((4, 5, 6), values[3:6], strict=True):
            runtime._write_value(sheet.getCellByPosition(column, row), value)
        _write_row(runtime, document, sheet, row, 8, values[8:11])
        match = re.fullmatch(r"ВЭУ-(\d+)", name)
        if match:
            number = int(match.group(1))
            prep.getCellByPosition(9, number).setString(name)
            prep.getCellByPosition(10, number).setString(_status(module, values))


def _reset_works(runtime: Any, document, rows: list[list[object]] | None) -> None:
    sheet = document.getSheets().getByName(runtime.INPUT_WORKS)
    end = max(runtime._last_used_row(sheet), 13)
    _clear(sheet.getCellRangeByPosition(1, 3, 11, end))
    for index, values in enumerate(rows or []):
        row = 3 + index
        _copy_row_style(sheet, 13, row, 11)
        _write_row(runtime, document, sheet, row, 1, values[:5])
        _write_row(runtime, document, sheet, row, 7, values[6:11])
        sheet.getCellByPosition(6, row).setFormula(
            f'=IF(COUNTA(E{row + 1}:F{row + 1})=0;"";'
            f'MAX(E{row + 1}-F{row + 1};0))'
        )


def _restore(module, runtime: Any, document, snapshot: dict[str, object]) -> None:
    if snapshot["main"] is not None:
        _reset_main(module, runtime, document, snapshot["main"])
    if snapshot["commands"] is not None:
        _reset_simple(
            runtime,
            document,
            runtime.INPUT_COMMANDS,
            snapshot["commands"],
            data_start=3,
            template_end=5,
            last_column=6,
        )
    if snapshot["violations"] is not None:
        _reset_violations(runtime, document, snapshot["violations"])
    if snapshot["state"] is not None:
        _reset_state(module, runtime, document, snapshot["state"])
    if snapshot["works"] is not None:
        _reset_works(runtime, document, snapshot["works"])
    if snapshot["defects"] is not None:
        _reset_simple(
            runtime,
            document,
            runtime.INPUT_DEFECTS,
            snapshot["defects"],
            data_start=3,
            template_end=17,
            last_column=10,
        )
    module._apply_formulas(runtime, document)


def install_exact_migration_contract(module, runtime: Any) -> None:
    """Wrap exact preparation with lossless migration of legacy input sheets."""

    if getattr(runtime, "_EXACT_MIGRATION_CONTRACT_005_APPLIED", False):
        return
    original = runtime.prepare_report_input_sheets

    def prepare(_args=None) -> None:
        document = runtime._document()
        snapshot = _snapshot(runtime, document)
        needs_migration = any(value is not None for value in snapshot.values())
        original(_args)
        if needs_migration:
            _restore(module, runtime, document, snapshot)
            runtime._message(
                "Точные формы рапорта подготовлены. Данные старых листов "
                "перенесены без выбора внешнего шаблона."
            )

    runtime.prepare_report_input_sheets = prepare
    runtime._EXACT_MIGRATION_CONTRACT_005_APPLIED = True
