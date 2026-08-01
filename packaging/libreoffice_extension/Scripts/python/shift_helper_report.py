"""Calc-native operator workflow for the accepted morning-report slice."""

from __future__ import annotations

import os
import shutil
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import uno

from shift_helper.core.selection import select_emergency_events
from shift_helper.uno_adapter.report_generation import (
    EXPECTED_REPORT_HEADERS,
    JOURNAL_SHEET,
    REPORT_SHEET,
    default_report_filename,
    parse_report_date,
    read_uno_journal,
    update_report_title,
)

XSCRIPTCONTEXT: Any = globals().get("XSCRIPTCONTEXT")
_VERSION = "0.3.2.dev0"
_HEADER_ROW = 2
_FIRST_DATA_ROW = 3
_DATE_TIME_FORMAT = "DD.MM.YYYY HH:MM"


def _context():
    if XSCRIPTCONTEXT is None:
        raise RuntimeError("Команда запущена вне LibreOffice.")
    return XSCRIPTCONTEXT.getComponentContext()


def _desktop():
    return XSCRIPTCONTEXT.getDesktop()


def _document():
    if XSCRIPTCONTEXT is None:
        raise RuntimeError("Команда запущена вне LibreOffice.")
    document = XSCRIPTCONTEXT.getDocument()
    if document is None or not document.supportsService(
        "com.sun.star.sheet.SpreadsheetDocument"
    ):
        raise RuntimeError("Откройте книгу LibreOffice Calc.")
    return document


def _manager():
    context = _context()
    return context.getServiceManager(), context


def _message(text: str, *, error: bool = False) -> None:
    manager, context = _manager()
    toolkit = manager.createInstanceWithContext("com.sun.star.awt.Toolkit", context)
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
        "Shift-Helper",
        text.replace("\n", "\r\n"),
    )
    box.execute()


def _property(name: str, value: object):
    item = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    item.Name = name
    item.Value = value
    return item


def _dialog_model_control(model, service: str, name: str, **properties):
    control = model.createInstance(service)
    control.Name = name
    for key, value in properties.items():
        setattr(control, key, value)
    model.insertByName(name, control)
    return control


def _ask_report_date(default: date) -> date | None:
    manager, context = _manager()
    model = manager.createInstanceWithContext(
        "com.sun.star.awt.UnoControlDialogModel", context
    )
    model.PositionX = 100
    model.PositionY = 80
    model.Width = 190
    model.Height = 76
    model.Title = "Shift-Helper — дата рапорта"

    _dialog_model_control(
        model,
        "com.sun.star.awt.UnoControlFixedTextModel",
        "Prompt",
        PositionX=10,
        PositionY=9,
        Width=170,
        Height=12,
        Label="Дата окончания окна 07:00–07:00:",
    )
    _dialog_model_control(
        model,
        "com.sun.star.awt.UnoControlEditModel",
        "ReportDate",
        PositionX=10,
        PositionY=25,
        Width=170,
        Height=14,
        Text=default.strftime("%d.%m.%Y"),
    )
    ok_type = uno.getConstantByName("com.sun.star.awt.PushButtonType.OK")
    cancel_type = uno.getConstantByName("com.sun.star.awt.PushButtonType.CANCEL")
    _dialog_model_control(
        model,
        "com.sun.star.awt.UnoControlButtonModel",
        "OK",
        PositionX=45,
        PositionY=51,
        Width=45,
        Height=14,
        Label="ОК",
        PushButtonType=ok_type,
        DefaultButton=True,
    )
    _dialog_model_control(
        model,
        "com.sun.star.awt.UnoControlButtonModel",
        "Cancel",
        PositionX=100,
        PositionY=51,
        Width=45,
        Height=14,
        Label="Отмена",
        PushButtonType=cancel_type,
    )

    dialog = manager.createInstanceWithContext(
        "com.sun.star.awt.UnoControlDialog", context
    )
    dialog.setModel(model)
    toolkit = manager.createInstanceWithContext("com.sun.star.awt.Toolkit", context)
    parent = _document().getCurrentController().getFrame().getContainerWindow()
    dialog.createPeer(toolkit, parent)
    try:
        result = int(dialog.execute())
        if result == 0:
            return None
        raw = str(dialog.getControl("ReportDate").getText())
    finally:
        dialog.dispose()
    return parse_report_date(raw)


def _picker_template(description: int, title: str):
    manager, context = _manager()
    picker = manager.createInstanceWithContext(
        "com.sun.star.ui.dialogs.FilePicker", context
    )
    picker.initialize((description,))
    picker.setTitle(title)
    picker.appendFilter("Книги Excel (*.xlsx)", "*.xlsx")
    picker.setCurrentFilter("Книги Excel (*.xlsx)")
    return picker


def _pick_template() -> Path | None:
    description = uno.getConstantByName(
        "com.sun.star.ui.dialogs.TemplateDescription.FILEOPEN_SIMPLE"
    )
    picker = _picker_template(description, "Выберите шаблон утреннего рапорта")
    ok = uno.getConstantByName("com.sun.star.ui.dialogs.ExecutableDialogResults.OK")
    try:
        if int(picker.execute()) != int(ok):
            return None
        files = tuple(picker.getFiles())
    finally:
        picker.dispose()
    if not files:
        return None
    return Path(uno.fileUrlToSystemPath(files[0])).resolve()


def _pick_output(template: Path, report_date: date) -> Path | None:
    description = uno.getConstantByName(
        "com.sun.star.ui.dialogs.TemplateDescription.FILESAVE_AUTOEXTENSION"
    )
    picker = _picker_template(description, "Сохранить сформированный рапорт")
    try:
        try:
            picker.setDisplayDirectory(uno.systemPathToFileUrl(str(template.parent)))
            picker.setDefaultName(default_report_filename(report_date))
        except Exception:
            pass
        ok = uno.getConstantByName("com.sun.star.ui.dialogs.ExecutableDialogResults.OK")
        if int(picker.execute()) != int(ok):
            return None
        files = tuple(picker.getFiles())
    finally:
        picker.dispose()
    if not files:
        return None
    output = Path(uno.fileUrlToSystemPath(files[0])).resolve()
    if output.suffix.casefold() != ".xlsx":
        output = output.with_suffix(".xlsx")
    return output


def _cell_kind(cell) -> str:
    value = cell.getType()
    return str(getattr(value, "value", value)).upper()


def _is_formula(cell) -> bool:
    return "FORMULA" in _cell_kind(cell) or str(cell.getFormula()).startswith("=")


def _null_date(document) -> date:
    value = document.getNumberFormatSettings().getPropertyValue("NullDate")
    return date(int(value.Year), int(value.Month), int(value.Day))


def _cell_date(cell, null_date: date) -> object:
    text = str(cell.getString()).strip()
    if not text:
        return None
    if _is_formula(cell) or "VALUE" not in _cell_kind(cell):
        return text
    return null_date + timedelta(days=int(cell.getValue()))


def _cell_time(cell) -> object:
    text = str(cell.getString()).strip()
    if not text:
        return None
    if _is_formula(cell) or "VALUE" not in _cell_kind(cell):
        return text
    minutes = int(round((float(cell.getValue()) % 1.0) * 24 * 60)) % (24 * 60)
    return time(minutes // 60, minutes % 60)


def _cell_raw(cell) -> object:
    if "VALUE" in _cell_kind(cell) and not _is_formula(cell):
        value = float(cell.getValue())
        return int(value) if value.is_integer() else value
    return str(cell.getString())


def _journal_rows(document, sheet, end_row: int):
    null_date = _null_date(document)
    indexes = {"B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "I": 8, "J": 9}
    for row in range(1, end_row + 1):
        cells = {
            column: sheet.getCellByPosition(index, row)
            for column, index in indexes.items()
        }
        yield row + 1, {
            "B": _cell_date(cells["B"], null_date),
            "C": _cell_time(cells["C"]),
            "D": _cell_raw(cells["D"]),
            "E": str(cells["E"].getString()),
            "F": str(cells["F"].getString()),
            "I": _cell_date(cells["I"], null_date),
            "J": _cell_time(cells["J"]),
        }


def _read_journal(document):
    sheets = document.getSheets()
    if not sheets.hasByName(JOURNAL_SHEET):
        raise RuntimeError(f"В открытой книге отсутствует лист «{JOURNAL_SHEET}».")
    sheet = sheets.getByName(JOURNAL_SHEET)
    indexes = {"B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "I": 8, "J": 9}
    headers = {
        column: str(sheet.getCellByPosition(index, 0).getString())
        for column, index in indexes.items()
    }
    cursor = sheet.createCursor()
    cursor.gotoEndOfUsedArea(True)
    end_row = int(cursor.getRangeAddress().EndRow)
    return read_uno_journal(
        headers=headers,
        rows=_journal_rows(document, sheet, end_row),
    )


def _document_path(document) -> Path | None:
    url = str(document.getURL() or "")
    if not url or not url.lower().startswith("file:"):
        return None
    return Path(uno.fileUrlToSystemPath(url)).resolve()


def _open_hidden(path: Path, *, read_only: bool = False):
    properties = (
        _property("Hidden", True),
        _property("ReadOnly", read_only),
        _property("AsTemplate", False),
        _property("MacroExecutionMode", 0),
        _property("UpdateDocMode", 0),
    )
    component = _desktop().loadComponentFromURL(
        uno.systemPathToFileUrl(str(path)),
        "_blank",
        0,
        properties,
    )
    if component is None or not component.supportsService(
        "com.sun.star.sheet.SpreadsheetDocument"
    ):
        raise RuntimeError(f"LibreOffice не смог открыть книгу: {path}.")
    return component


def _close_component(component) -> None:
    try:
        component.close(True)
    except Exception:
        component.dispose()


def _used_end_row(sheet) -> int:
    cursor = sheet.createCursor()
    cursor.gotoEndOfUsedArea(True)
    return int(cursor.getRangeAddress().EndRow)


def _verify_report_sheet(component):
    sheets = component.getSheets()
    if not sheets.hasByName(REPORT_SHEET):
        raise RuntimeError(f"В шаблоне отсутствует лист «{REPORT_SHEET}».")
    sheet = sheets.getByName(REPORT_SHEET)
    actual = tuple(
        str(sheet.getCellByPosition(column, _HEADER_ROW).getString()).strip()
        for column in range(1, 6)
    )
    if actual != EXPECTED_REPORT_HEADERS:
        raise RuntimeError(
            f"Лист «{REPORT_SHEET}» не соответствует утверждённой карте полей: {actual!r}."
        )
    return sheet


def _format_key(document, cell, code: str) -> int:
    formats = document.getNumberFormats()
    locale = cell.getPropertyValue("CharLocale")
    key = formats.queryKey(code, locale, True)
    return formats.addNew(code, locale) if key == -1 else key


def _datetime_serial(value: datetime, null_date: date) -> float:
    origin = datetime.combine(null_date, time.min)
    return (value - origin).total_seconds() / 86400.0


def _clear_existing(sheet) -> None:
    end_row = max(_used_end_row(sheet), _FIRST_DATA_ROW)
    flags = sum(
        int(uno.getConstantByName(f"com.sun.star.sheet.CellFlags.{name}"))
        for name in ("VALUE", "DATETIME", "STRING", "FORMULA")
    )
    sheet.getCellRangeByPosition(1, _FIRST_DATA_ROW, 5, end_row).clearContents(flags)


def _prepare_report_rows(sheet, count: int) -> None:
    needed_end = _FIRST_DATA_ROW + max(count, 1) - 1
    row_count = int(sheet.getRows().getCount())
    if needed_end >= row_count:
        sheet.getRows().insertByIndex(row_count, needed_end - row_count + 1)
    prototype = sheet.getCellRangeByPosition(1, _FIRST_DATA_ROW, 5, _FIRST_DATA_ROW)
    source_address = prototype.getRangeAddress()
    prototype_height = sheet.getRows().getByIndex(_FIRST_DATA_ROW).Height
    for row in range(_FIRST_DATA_ROW + 1, needed_end + 1):
        destination = sheet.getCellByPosition(1, row).getCellAddress()
        sheet.copyRange(destination, source_address)
        sheet.getRows().getByIndex(row).Height = prototype_height


def _write_report(component, sheet, report_date: date, events) -> None:
    title_cell = sheet.getCellByPosition(1, 0)
    title_cell.setString(update_report_title(str(title_cell.getString()), report_date))
    _clear_existing(sheet)
    _prepare_report_rows(sheet, len(events))
    null_date = _null_date(component)
    for offset, event in enumerate(events):
        row = _FIRST_DATA_ROW + offset
        sheet.getCellByPosition(1, row).setString(event.dispatch_name)
        started = sheet.getCellByPosition(2, row)
        started.setValue(_datetime_serial(event.started_at, null_date))
        started.setPropertyValue(
            "NumberFormat", _format_key(component, started, _DATE_TIME_FORMAT)
        )
        sheet.getCellByPosition(3, row).setString(event.reason)
        sheet.getCellByPosition(4, row).setString(event.description)
        ended = sheet.getCellByPosition(5, row)
        if event.ended_at is None:
            ended.setString("")
        else:
            ended.setValue(_datetime_serial(event.ended_at, null_date))
            ended.setPropertyValue(
                "NumberFormat", _format_key(component, ended, _DATE_TIME_FORMAT)
            )


def _verify_saved(path: Path, expected_rows: int) -> None:
    verifier = _open_hidden(path, read_only=True)
    try:
        sheet = _verify_report_sheet(verifier)
        populated = sum(
            1
            for row in range(_FIRST_DATA_ROW, _FIRST_DATA_ROW + expected_rows)
            if str(sheet.getCellByPosition(1, row).getString()).strip()
        )
        if populated != expected_rows:
            raise RuntimeError(
                f"Проверка результата ожидала {expected_rows} строк, найдено {populated}."
            )
    finally:
        _close_component(verifier)


def _build_report(
    *,
    journal_document,
    template: Path,
    output: Path,
    report_date: date,
    events,
) -> None:
    journal_path = _document_path(journal_document)
    if output == template:
        raise RuntimeError("Результат не должен перезаписывать шаблон рапорта.")
    if journal_path is not None and output == journal_path:
        raise RuntimeError("Результат не должен перезаписывать журнал событий.")
    output.parent.mkdir(parents=True, exist_ok=True)
    pending = output.with_name(f".{output.stem}.shift-helper.pending.xlsx")
    pending.unlink(missing_ok=True)
    shutil.copy2(template, pending)

    report = None
    try:
        report = _open_hidden(pending)
        sheet = _verify_report_sheet(report)
        _write_report(report, sheet, report_date, events)
        report.store()
        _close_component(report)
        report = None
        _verify_saved(pending, len(events))
        os.replace(pending, output)
    except Exception:
        if report is not None:
            _close_component(report)
        pending.unlink(missing_ok=True)
        raise


def generate_emergency_report(_args=None) -> None:
    try:
        document = _document()
        report_date = _ask_report_date(date.today())
        if report_date is None:
            return
        template = _pick_template()
        if template is None:
            return
        output = _pick_output(template, report_date)
        if output is None:
            return

        journal = _read_journal(document)
        if journal.blocking_structure_errors:
            messages = "\n".join(
                issue.message for issue in journal.blocking_structure_errors[:10]
            )
            raise RuntimeError(
                "Структура листа ЖС не соответствует контракту:\n" + messages
            )
        selection = select_emergency_events(journal.events, report_date)
        modified_before = bool(document.isModified())
        _build_report(
            journal_document=document,
            template=template,
            output=output,
            report_date=report_date,
            events=selection.selected_events,
        )
        if bool(document.isModified()) != modified_before:
            raise RuntimeError("Исходный журнал изменился во время формирования рапорта.")
        _message(
            f"Рапорт сформирован.\n"
            f"Отобрано строк: {len(selection.selected_events)}.\n"
            f"Пропущено некорректных строк: {len(journal.ignored_rows)}.\n"
            f"Файл: {output}"
        )
    except Exception as exc:
        _message(f"Не удалось сформировать рапорт: {exc}", error=True)


g_exportedScripts = (generate_emergency_report,)
