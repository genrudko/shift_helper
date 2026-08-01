"""LibreOffice Calc macros for the first Shift-Helper UNO integration slice."""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, time, timedelta
from typing import Any

import uno

XSCRIPTCONTEXT: Any = globals().get("XSCRIPTCONTEXT")

_SCRIPT_DIR = os.path.dirname(__file__)
_PYTHONPATH = os.path.join(_SCRIPT_DIR, "pythonpath")
if _PYTHONPATH not in sys.path:
    sys.path.insert(0, _PYTHONPATH)

from shift_helper.uno_adapter.calc_selection import (  # noqa: E402
    CalcSelectionError,
    SelectionPlan,
    plan_date_selection,
    plan_time_selection,
    validate_vertical_selection,
)

_EXTENSION_VERSION = "0.3.0.dev0"
_JOURNAL_SHEET = "ЖС"
_DATE_FORMAT = "DD.MM.YYYY"
_TIME_FORMAT = "HH:MM"


def _document():
    if XSCRIPTCONTEXT is None:
        raise CalcSelectionError("Макрос запущен вне LibreOffice.")
    document = XSCRIPTCONTEXT.getDocument()
    if document is None or not document.supportsService(
        "com.sun.star.sheet.SpreadsheetDocument"
    ):
        raise CalcSelectionError("Откройте книгу LibreOffice Calc.")
    return document


def _message(title: str, text: str, *, error: bool = False) -> None:
    if XSCRIPTCONTEXT is None:
        raise RuntimeError(text)
    context = XSCRIPTCONTEXT.getComponentContext()
    service_manager = context.getServiceManager()
    toolkit = service_manager.createInstanceWithContext("com.sun.star.awt.Toolkit", context)
    parent = _document().getCurrentController().getFrame().getContainerWindow()
    box_type = uno.Enum(
        "com.sun.star.awt.MessageBoxType",
        "ERRORBOX" if error else "INFOBOX",
    )
    buttons = uno.getConstantByName("com.sun.star.awt.MessageBoxButtons.BUTTONS_OK")
    box = toolkit.createMessageBox(
        parent,
        box_type,
        buttons,
        title,
        text.replace("\n", "\r\n"),
    )
    box.execute()


def _active_sheet(document):
    sheet = document.getCurrentController().getActiveSheet()
    if sheet.getName() != _JOURNAL_SHEET:
        raise CalcSelectionError(f"Откройте лист «{_JOURNAL_SHEET}».")
    return sheet


def _selection_address(document):
    selection = document.getCurrentController().getSelection()
    get_range = getattr(selection, "getRangeAddress", None)
    if callable(get_range):
        return get_range()

    get_ranges = getattr(selection, "getRangeAddresses", None)
    if callable(get_ranges):
        addresses = tuple(get_ranges())
        if len(addresses) == 1:
            return addresses[0]
    raise CalcSelectionError("Выделите один непрерывный диапазон ячеек.")


def _content_type(cell) -> str:
    value = cell.getType()
    enum_value = getattr(value, "value", None)
    return str(enum_value if enum_value is not None else value).upper()


def _is_formula(cell) -> bool:
    return "FORMULA" in _content_type(cell) or cell.getFormula().startswith("=")


def _cell_raw(cell) -> object:
    if _is_formula(cell):
        return cell.getString()
    if "VALUE" in _content_type(cell):
        return cell.getString()
    text = cell.getString().strip()
    return text if text else None


def _null_date(document) -> date:
    settings = document.getNumberFormatSettings()
    value = settings.getPropertyValue("NullDate")
    return date(int(value.Year), int(value.Month), int(value.Day))


def _numeric_date(cell, *, null_date: date) -> date | None:
    if _is_formula(cell):
        return None
    if "VALUE" not in _content_type(cell):
        return None
    text = cell.getString().strip()
    if not text:
        return None
    return null_date + timedelta(days=int(cell.getValue()))


def _numeric_time(cell) -> time | None:
    if _is_formula(cell):
        return None
    if "VALUE" not in _content_type(cell):
        return None
    text = cell.getString().strip()
    if not text:
        return None
    fraction = cell.getValue() % 1.0
    total_minutes = int(round(fraction * 24 * 60)) % (24 * 60)
    return time(total_minutes // 60, total_minutes % 60)


def _format_key(document, cell, code: str) -> int:
    formats = document.getNumberFormats()
    locale = cell.getPropertyValue("CharLocale")
    key = formats.queryKey(code, locale, True)
    if key == -1:
        key = formats.addNew(code, locale)
    return key


def _write_date(document, cell, value: date, *, null_date: date) -> None:
    cell.setValue(float((value - null_date).days))
    cell.setPropertyValue("NumberFormat", _format_key(document, cell, _DATE_FORMAT))


def _write_time(document, cell, value: time) -> None:
    seconds = value.hour * 3600 + value.minute * 60 + value.second
    cell.setValue(seconds / 86400.0)
    cell.setPropertyValue("NumberFormat", _format_key(document, cell, _TIME_FORMAT))


def _column_name(column: int) -> str:
    result = ""
    number = column + 1
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _issue_lines(plan: SelectionPlan) -> list[str]:
    lines: list[str] = []
    for issue in plan.issues[:10]:
        marker = "Ошибка" if issue.severity == "error" else "Предупреждение"
        lines.append(f"{marker} {_column_name(issue.column)}{issue.row + 1}: {issue.message}")
    if len(plan.issues) > 10:
        lines.append(f"…и ещё {len(plan.issues) - 10}.")
    return lines


def _apply_plan(document, sheet, plan: SelectionPlan) -> None:
    if not plan.writes:
        return

    null_date = _null_date(document)
    undo_manager = None
    document.lockControllers()
    try:
        try:
            undo_manager = document.getUndoManager()
            undo_manager.enterUndoContext("Shift-Helper: быстрый ввод")
        except Exception:
            undo_manager = None

        for write in plan.writes:
            cell = sheet.getCellByPosition(write.column, write.row)
            if write.kind == "date":
                _write_date(document, cell, write.value, null_date=null_date)
            else:
                _write_time(document, cell, write.value)
    finally:
        if undo_manager is not None:
            try:
                undo_manager.leaveUndoContext()
            except Exception:
                pass
        document.unlockControllers()


def _show_result(plan: SelectionPlan) -> None:
    lines = [
        f"Изменено ячеек: {plan.changed_cells}",
        f"Ошибок: {len(plan.errors)}",
        f"Предупреждений: {len(plan.warnings)}",
    ]
    details = _issue_lines(plan)
    if details:
        lines.extend(("", *details))
    _message("Shift-Helper", "\n".join(lines), error=bool(plan.errors))


def show_status(_args=None) -> None:
    try:
        document = _document()
        sheet = document.getCurrentController().getActiveSheet()
        address = _selection_address(document)
        selection = (
            f"{_column_name(address.StartColumn)}{address.StartRow + 1}:"
            f"{_column_name(address.EndColumn)}{address.EndRow + 1}"
        )
        _message(
            "Shift-Helper",
            "\n".join(
                (
                    f"Версия расширения: {_EXTENSION_VERSION}",
                    f"Лист: {sheet.getName()}",
                    f"Выделение: {selection}",
                    "Дата: B или I",
                    "Время: C или J",
                )
            ),
        )
    except Exception as exc:
        _message("Shift-Helper", str(exc), error=True)


def normalize_selected_dates(_args=None) -> None:
    try:
        document = _document()
        sheet = _active_sheet(document)
        address = _selection_address(document)
        validate_vertical_selection(
            start_row=address.StartRow,
            end_row=address.EndRow,
            start_column=address.StartColumn,
            end_column=address.EndColumn,
        )

        null_date = _null_date(document)
        previous = None
        if address.StartRow > 1:
            previous = _numeric_date(
                sheet.getCellByPosition(address.StartColumn, address.StartRow - 1),
                null_date=null_date,
            )
        raw_values = [
            _cell_raw(sheet.getCellByPosition(address.StartColumn, row))
            for row in range(address.StartRow, address.EndRow + 1)
        ]
        plan = plan_date_selection(
            start_row=address.StartRow,
            column=address.StartColumn,
            raw_values=raw_values,
            previous_above=previous,
            today=date.today(),
        )
        _apply_plan(document, sheet, plan)
        _show_result(plan)
    except CalcSelectionError as exc:
        _message("Shift-Helper", str(exc), error=True)
    except Exception as exc:
        _message("Shift-Helper", f"Сбой UNO-адаптера: {exc}", error=True)


def normalize_selected_times(_args=None) -> None:
    try:
        document = _document()
        sheet = _active_sheet(document)
        address = _selection_address(document)
        validate_vertical_selection(
            start_row=address.StartRow,
            end_row=address.EndRow,
            start_column=address.StartColumn,
            end_column=address.EndColumn,
        )

        previous = None
        if address.StartRow > 1:
            previous = _numeric_time(
                sheet.getCellByPosition(address.StartColumn, address.StartRow - 1)
            )

        paired_column = 1 if address.StartColumn == 2 else 8
        null_date = _null_date(document)
        raw_values = []
        paired_dates = []
        for row in range(address.StartRow, address.EndRow + 1):
            raw_values.append(_cell_raw(sheet.getCellByPosition(address.StartColumn, row)))
            paired_dates.append(
                _numeric_date(
                    sheet.getCellByPosition(paired_column, row),
                    null_date=null_date,
                )
            )

        plan = plan_time_selection(
            start_row=address.StartRow,
            column=address.StartColumn,
            raw_values=raw_values,
            previous_above=previous,
            paired_dates=paired_dates,
            now=datetime.now(),
        )
        _apply_plan(document, sheet, plan)
        _show_result(plan)
    except CalcSelectionError as exc:
        _message("Shift-Helper", str(exc), error=True)
    except Exception as exc:
        _message("Shift-Helper", f"Сбой UNO-адаптера: {exc}", error=True)


g_exportedScripts = (
    show_status,
    normalize_selected_dates,
    normalize_selected_times,
)
