"""Acceptance repairs for exact report forms, calculations and Outlook settings."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import uno
import unohelper
from com.sun.star.awt import XActionListener

INPUT_OUTAGES = "Ввод - Аварийные отключения"
STATUS_COLUMN = 11  # L on exact WTG state sheet.
META_KEY_COLUMN = 12  # M on preparation sheet.
META_VALUE_COLUMN = 13  # N on preparation sheet.
STATUSES = ("Работа", "Останов", "Авария", "Ремонт")
GENERATION_SETTINGS = (
    ("Outlook: почтовый ящик", "НСС Кочубеевская ВЭС"),
    ("Outlook: папка", "Входящие"),
    ("Outlook: маска вложения", "Генерация КВЭС за вчера_{date}.xlsx"),
    ("Outlook: тема содержит", ""),
    ("Outlook: отправитель содержит", ""),
    ("Outlook: глубина поиска, дней", 7.0),
    ("Outlook: ручной выбор при отсутствии", 1.0),
)
OUTAGE_FORM = (
    "Аварийные отключения ЛЭП",
    INPUT_OUTAGES,
    "B3",
    "Диспетчерское наименование ЛЭП, ВЭУ и оборудования",
)


def _cell(sheet, address: str):
    return sheet.getCellRangeByName(address)


def _legacy_statuses(prep) -> dict[str, str]:
    result: dict[str, str] = {}
    for name_col, value_col in ((6, 7), (9, 10)):
        for row in range(1, 90):
            name = str(prep.getCellByPosition(name_col, row).getString()).strip()
            status = str(prep.getCellByPosition(value_col, row).getString()).strip()
            if name.startswith("ВЭУ-") and status in STATUSES:
                result[name] = status
    return result


def _clear_legacy_statuses(prep) -> None:
    for name_col, value_col in ((6, 7), (9, 10)):
        for row in range(1, 90):
            name_cell = prep.getCellByPosition(name_col, row)
            value_cell = prep.getCellByPosition(value_col, row)
            name = str(name_cell.getString()).strip()
            value = str(value_cell.getString()).strip()
            if name.startswith("ВЭУ-") and value in STATUSES:
                name_cell.setString("")
                value_cell.setString("")
    for col in (6, 7, 9, 10):
        try:
            prep.getColumns().getByIndex(col).IsVisible = True
        except Exception:
            pass


def _meta_keys(module) -> tuple[str, ...]:
    base = tuple(module.META)
    extra = tuple(key for key, _default in GENERATION_SETTINGS)
    keys = tuple(dict.fromkeys((*base, *extra)))
    module.META = keys
    return keys


def _infer_status(module, state, row: int) -> str:
    reason = str(state.getCellByPosition(8, row).getString()).strip()
    p_repair = state.getCellByPosition(6, row).getValue()
    p_avail = state.getCellByPosition(7, row).getValue()
    inferred = module._infer(reason, p_avail, p_repair)
    return inferred if inferred in STATUSES else "Работа"


def _ensure_status_column(module, runtime, document) -> None:
    sheets = document.getSheets()
    if not sheets.hasByName(runtime.INPUT_STATE):
        return
    state = sheets.getByName(runtime.INPUT_STATE)
    prep = sheets.getByName(runtime.INPUT_PREP)
    previous = _legacy_statuses(prep)

    try:
        state.getColumns().getByIndex(STATUS_COLUMN).Width = 3000
    except Exception:
        pass
    header = state.getCellByPosition(STATUS_COLUMN, 2)
    if str(header.getString()).strip() != "Статус ВЭУ":
        try:
            source = state.getCellRangeByPosition(
                10, 2, 10, max(runtime._last_used_row(state), 97)
            )
            destination = uno.createUnoStruct("com.sun.star.table.CellAddress")
            destination.Sheet = source.getRangeAddress().Sheet
            destination.Column = STATUS_COLUMN
            destination.Row = 2
            state.copyRange(destination, source.getRangeAddress())
            state.getCellRangeByPosition(
                STATUS_COLUMN,
                3,
                STATUS_COLUMN,
                max(runtime._last_used_row(state), 97),
            ).clearContents(1023)
        except Exception:
            pass
    header.setString("Статус ВЭУ")
    try:
        header.setPropertyValue("CharWeight", 150.0)
        header.setPropertyValue(
            "HoriJustify",
            uno.Enum("com.sun.star.table.CellHoriJustify", "CENTER"),
        )
        header.setPropertyValue(
            "VertJustify",
            uno.Enum("com.sun.star.table.CellVertJustify", "CENTER"),
        )
    except Exception:
        pass

    for row in range(3, max(runtime._last_used_row(state), 97) + 1):
        name = str(state.getCellByPosition(3, row).getString()).strip()
        status_cell = state.getCellByPosition(STATUS_COLUMN, row)
        if not name.startswith("ВЭУ-"):
            status_cell.setString("")
            continue
        current = str(status_cell.getString()).strip()
        if current not in STATUSES:
            current = previous.get(name) or _infer_status(module, state, row)
            status_cell.setString(current)
    try:
        state.getCellRangeByPosition(
            STATUS_COLUMN, 2, STATUS_COLUMN, max(runtime._last_used_row(state), 97)
        ).setPropertyValue("IsTextWrapped", True)
    except Exception:
        pass
    _clear_legacy_statuses(prep)


def _ensure_service(module, runtime, document) -> None:
    prep = document.getSheets().getByName(runtime.INPUT_PREP)
    keys = _meta_keys(module)
    existing: dict[str, object] = {}
    for key_col, value_col in ((9, 10), (META_KEY_COLUMN, META_VALUE_COLUMN)):
        for row in range(1, 50):
            key = str(prep.getCellByPosition(key_col, row).getString()).strip()
            if key in keys:
                existing[key] = runtime._cell_value(
                    prep.getCellByPosition(value_col, row), document
                )

    defaults = dict(GENERATION_SETTINGS)
    for row, key in enumerate(keys, start=1):
        prep.getCellByPosition(META_KEY_COLUMN, row).setString(key)
        current = runtime._cell_value(
            prep.getCellByPosition(META_VALUE_COLUMN, row), document
        )
        if current in (None, ""):
            default = defaults.get(key, existing.get(key))
            if default not in (None, ""):
                runtime._write_value(
                    prep.getCellByPosition(META_VALUE_COLUMN, row),
                    default,
                    document,
                )
    for column in (META_KEY_COLUMN, META_VALUE_COLUMN):
        try:
            prep.getColumns().getByIndex(column).IsVisible = False
        except Exception:
            pass

    _ensure_status_column(module, runtime, document)


def _meta(module, runtime, document, key: str, value=...):
    _ensure_service(module, runtime, document)
    keys = _meta_keys(module)
    if key not in keys:
        raise RuntimeError(f"Неизвестный служебный параметр: {key}.")
    row = keys.index(key) + 1
    cell = document.getSheets().getByName(runtime.INPUT_PREP).getCellByPosition(
        META_VALUE_COLUMN, row
    )
    if value is ...:
        return runtime._cell_value(cell, document)
    runtime._write_value(
        cell,
        value,
        document,
        "DD.MM.YYYY" if isinstance(value, (date, datetime)) else None,
    )


def _status_map(module, runtime, document) -> dict[str, str]:
    _ensure_service(module, runtime, document)
    state = document.getSheets().getByName(runtime.INPUT_STATE)
    result: dict[str, str] = {}
    for row in range(3, max(runtime._last_used_row(state), 97) + 1):
        name = str(state.getCellByPosition(3, row).getString()).strip()
        status = str(state.getCellByPosition(STATUS_COLUMN, row).getString()).strip()
        if name.startswith("ВЭУ-") and status in STATUSES:
            result[name] = status
    return result


def _apply_formulas(module, runtime, document, original) -> None:
    original(runtime, document)
    _ensure_service(module, runtime, document)
    sheets = document.getSheets()
    main = sheets.getByName(runtime.INPUT_MAIN)
    # Average active load = previous-day generation / 24h, converted from kWh to MW.
    _cell(main, "C6").setFormula('=IFERROR(C10/24000;0)')
    # Remaining mean power uses the full monthly plan and all hours from 00:00
    # of the report date through the end of the month, matching the approved report.
    _cell(main, "C15").setFormula(
        '=IFERROR(IF(C13>=0;-1;'
        "(INDEX(I5:I16;MONTH('Подготовка рапорта'.B3))-C11)/"
        "((DAY(EOMONTH('Подготовка рапорта'.B3;0))-"
        "DAY('Подготовка рапорта'.B3)+1)*24));0)"
    )
    for row, status in zip(
        range(4, 8),
        ("Останов", "Работа", "Авария", "Ремонт"),
        strict=True,
    ):
        _cell(main, f"F{row}").setFormula(
            f'=COUNTIF(\'Ввод - Состояние ВЭУ\'.L4:L98;"{status}")'
        )
    try:
        runtime._set_number_format(document, _cell(main, "C6"), "0.00")
        runtime._set_number_format(document, _cell(main, "C15"), "0.0")
    except Exception:
        pass
    try:
        document.calculateAll()
    except Exception:
        pass


def _ensure_outage_form(module, runtime, document) -> None:
    source_name, target_name, address, marker = OUTAGE_FORM
    if module._exact(document, target_name, address, marker):
        return
    source = runtime._open_hidden(module._template(runtime), read_only=True)
    try:
        module._import_form(document, source, source_name, target_name)
    finally:
        runtime._close(source)


def _refresh_outages(runtime, document) -> int:
    sheets = document.getSheets()
    if not sheets.hasByName(INPUT_OUTAGES):
        return 0
    sheet = sheets.getByName(INPUT_OUTAGES)
    report_date, _offset = runtime._prep_settings(document)
    journal = runtime._read_journal(document)
    if journal.blocking_structure_errors:
        return 0
    selection = runtime.select_emergency_events(journal.events, report_date)
    runtime._clear_data(sheet, 3, 1, 5)
    rows = [
        (
            event.dispatch_name,
            event.started_at,
            event.reason,
            event.description,
            event.ended_at,
        )
        for event in selection.selected_events
    ]
    runtime._write_matrix_rows(
        sheet,
        3,
        1,
        rows,
        document,
        date_cols=(1, 4),
        time_offset_hours=0.0,
    )
    runtime._title(sheet, report_date)
    return len(rows)


def _date_dialog(runtime, document) -> date | None:
    report_date, _offset = runtime._prep_settings(document)
    context = runtime.XSCRIPTCONTEXT.getComponentContext()
    manager = context.getServiceManager()
    model = manager.createInstanceWithContext(
        "com.sun.star.awt.UnoControlDialogModel", context
    )
    model.Width = 190
    model.Height = 88
    model.Title = "Дата утреннего рапорта"

    label = model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
    label.Name = "Label"
    label.PositionX = 12
    label.PositionY = 12
    label.Width = 160
    label.Height = 12
    label.Label = "Выберите дату рапорта:"
    model.insertByName("Label", label)

    field = model.createInstance("com.sun.star.awt.UnoControlDateFieldModel")
    field.Name = "Date"
    field.PositionX = 12
    field.PositionY = 28
    field.Width = 164
    field.Height = 18
    field.Dropdown = True
    field.Date = int(report_date.strftime("%Y%m%d"))
    model.insertByName("Date", field)

    ok = model.createInstance("com.sun.star.awt.UnoControlButtonModel")
    ok.Name = "OK"
    ok.PositionX = 64
    ok.PositionY = 58
    ok.Width = 52
    ok.Height = 18
    ok.Label = "Выбрать"
    ok.PushButtonType = 1
    model.insertByName("OK", ok)

    cancel = model.createInstance("com.sun.star.awt.UnoControlButtonModel")
    cancel.Name = "Cancel"
    cancel.PositionX = 122
    cancel.PositionY = 58
    cancel.Width = 54
    cancel.Height = 18
    cancel.Label = "Отмена"
    cancel.PushButtonType = 2
    model.insertByName("Cancel", cancel)

    dialog = manager.createInstanceWithContext(
        "com.sun.star.awt.UnoControlDialog", context
    )
    dialog.setModel(model)
    toolkit = manager.createInstanceWithContext("com.sun.star.awt.Toolkit", context)
    parent = document.getCurrentController().getFrame().getContainerWindow()
    dialog.createPeer(toolkit, parent)
    try:
        if int(dialog.execute()) != 1:
            return None
        raw = int(dialog.getControl("Date").getModel().Date)
    finally:
        dialog.dispose()
    text = f"{raw:08d}"
    return date(int(text[:4]), int(text[4:6]), int(text[6:8]))


def show_report_date_calendar(runtime, _args=None) -> None:
    try:
        document = runtime._document()
        if not document.getSheets().hasByName(runtime.INPUT_PREP):
            runtime.prepare_report_input_sheets()
        selected = _date_dialog(runtime, document)
        if selected is None:
            return
        prep = document.getSheets().getByName(runtime.INPUT_PREP)
        runtime._write_value(
            prep.getCellByPosition(1, 2), selected, document, "DD.MM.YYYY"
        )
        runtime._refresh_prep_window(document, prep, selected)
        runtime._EXACT_REPORT_MODULE._apply_formulas(runtime, document)
        _refresh_outages(runtime, document)
    except Exception as exc:
        runtime._message(f"Не удалось выбрать дату рапорта: {exc}", error=True)


class _CalendarButtonListener(unohelper.Base, XActionListener):
    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def actionPerformed(self, _event):  # noqa: N802
        show_report_date_calendar(self.runtime)

    def disposing(self, _event):
        return None


def _install_calendar_button(runtime, document) -> None:
    from shift_helper.core.operator_tools import _workspace_install_calendar_button

    # The existing installer leaves a service: URL as a persistent fallback.
    # When the live control is available we add a direct listener and only then
    # switch it to PUSH, avoiding the broken URL dispatch seen in Calc.
    _workspace_install_calendar_button(runtime, document)
    sheet = document.getSheets().getByName(runtime.INPUT_PREP)
    draw_page = sheet.getDrawPage()
    forms = draw_page.getForms()
    if not forms.hasByName("ShiftHelperControls"):
        return
    form = forms.getByName("ShiftHelperControls")
    if not form.hasByName("ShiftHelperReportDateCalendar"):
        return
    model = form.getByName("ShiftHelperReportDateCalendar")
    try:
        control = document.getCurrentController().getControl(model)
        previous = getattr(runtime, "_EXACT_CALENDAR_LISTENER", None)
        if previous is not None:
            try:
                control.removeActionListener(previous)
            except Exception:
                pass
        listener = _CalendarButtonListener(runtime)
        control.addActionListener(listener)
        runtime._EXACT_CALENDAR_LISTENER = listener
        model.setPropertyValue(
            "ButtonType", uno.Enum("com.sun.star.form.FormButtonType", "PUSH")
        )
    except Exception:
        # Keep the URL button installed by _workspace_install_calendar_button.
        pass


class _SettingsButtonListener(unohelper.Base, XActionListener):
    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def actionPerformed(self, _event):  # noqa: N802
        show_generation_import_settings(self.runtime)

    def disposing(self, _event):
        return None


def _install_generation_settings_button(runtime, document) -> None:
    sheet = document.getSheets().getByName(runtime.INPUT_PREP)
    draw_page = sheet.getDrawPage()
    forms = draw_page.getForms()
    form_name = "ShiftHelperControls"
    if forms.hasByName(form_name):
        form = forms.getByName(form_name)
    else:
        form = document.createInstance("com.sun.star.form.component.Form")
        form.setPropertyValue("Name", form_name)
        forms.insertByName(form_name, form)

    button_name = "ShiftHelperGenerationSettings"
    if form.hasByName(button_name):
        model = form.getByName(button_name)
    else:
        model = document.createInstance("com.sun.star.form.component.CommandButton")
        model.setPropertyValue("Name", button_name)
        form.insertByName(button_name, model)
    model.setPropertyValue("Label", "Настройки Outlook…")
    # URL mode persists with the workbook and remains a fallback after reopen.
    try:
        model.setPropertyValue(
            "ButtonType", uno.Enum("com.sun.star.form.FormButtonType", "URL")
        )
        model.setPropertyValue(
            "TargetURL",
            "service:ru.kves.shifthelper.calc.controls?generationsettings",
        )
        model.setPropertyValue("TargetFrame", "_self")
    except Exception:
        pass
    try:
        model.setPropertyValue(
            "HelpText", "Настроить поиск письма и вложения с генерацией"
        )
    except Exception:
        pass

    shape = None
    for index in range(draw_page.getCount()):
        candidate = draw_page.getByIndex(index)
        try:
            control = candidate.getControl()
            if str(control.getPropertyValue("Name")) == button_name:
                shape = candidate
                break
        except Exception:
            continue
    if shape is None:
        shape = document.createInstance("com.sun.star.drawing.ControlShape")
        shape.setControl(model)
        draw_page.add(shape)

    anchor = sheet.getCellByPosition(2, 9)
    point = uno.createUnoStruct("com.sun.star.awt.Point")
    point.X = int(anchor.Position.X) + 120
    point.Y = int(anchor.Position.Y) + 40
    size = uno.createUnoStruct("com.sun.star.awt.Size")
    size.Width = 5000
    size.Height = max(int(anchor.Size.Height) - 80, 650)
    shape.setPosition(point)
    shape.setSize(size)

    try:
        control = document.getCurrentController().getControl(model)
        previous = getattr(runtime, "_EXACT_GENERATION_SETTINGS_LISTENER", None)
        if previous is not None:
            try:
                control.removeActionListener(previous)
            except Exception:
                pass
        listener = _SettingsButtonListener(runtime)
        control.addActionListener(listener)
        runtime._EXACT_GENERATION_SETTINGS_LISTENER = listener
        model.setPropertyValue(
            "ButtonType", uno.Enum("com.sun.star.form.FormButtonType", "PUSH")
        )
    except Exception:
        # Keep the persistent service: URL fallback.
        pass


def _setting(runtime, document, key: str, default):
    value = runtime._EXACT_REPORT_MODULE._meta(runtime, document, key)
    return default if value in (None, "") else value


def show_generation_import_settings(runtime, _args=None) -> None:
    try:
        document = runtime._document()
        _ensure_service(runtime._EXACT_REPORT_MODULE, runtime, document)
        context = runtime.XSCRIPTCONTEXT.getComponentContext()
        manager = context.getServiceManager()
        model = manager.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", context
        )
        model.Width = 300
        model.Height = 224
        model.Title = "Импорт генерации из Outlook"

        fields = (
            ("Mailbox", "Почтовый ящик", "Outlook: почтовый ящик"),
            ("Folder", "Папка", "Outlook: папка"),
            (
                "Attachment",
                "Маска вложения ({date} = предыдущие сутки)",
                "Outlook: маска вложения",
            ),
            (
                "Subject",
                "Тема письма содержит (необязательно)",
                "Outlook: тема содержит",
            ),
            (
                "Sender",
                "Отправитель содержит (необязательно)",
                "Outlook: отправитель содержит",
            ),
        )
        y = 8
        for name, label_text, key in fields:
            label = model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
            label.Name = f"{name}Label"
            label.PositionX = 10
            label.PositionY = y
            label.Width = 278
            label.Height = 10
            label.Label = label_text
            model.insertByName(label.Name, label)
            edit = model.createInstance("com.sun.star.awt.UnoControlEditModel")
            edit.Name = name
            edit.PositionX = 10
            edit.PositionY = y + 11
            edit.Width = 278
            edit.Height = 16
            edit.Text = str(_setting(runtime, document, key, ""))
            model.insertByName(name, edit)
            y += 33

        days_label = model.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        days_label.Name = "DaysLabel"
        days_label.PositionX = 10
        days_label.PositionY = y
        days_label.Width = 155
        days_label.Height = 10
        days_label.Label = "Глубина поиска, дней"
        model.insertByName("DaysLabel", days_label)

        days = model.createInstance("com.sun.star.awt.UnoControlNumericFieldModel")
        days.Name = "Days"
        days.PositionX = 168
        days.PositionY = y - 3
        days.Width = 54
        days.Height = 16
        days.ValueMin = 1
        days.ValueMax = 60
        days.DecimalAccuracy = 0
        days.Value = float(
            _setting(runtime, document, "Outlook: глубина поиска, дней", 7)
        )
        model.insertByName("Days", days)
        y += 22

        fallback = model.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        fallback.Name = "Fallback"
        fallback.PositionX = 10
        fallback.PositionY = y
        fallback.Width = 278
        fallback.Height = 12
        fallback.Label = (
            "Если письмо не найдено — предложить выбрать файл вручную"
        )
        fallback.State = (
            1
            if float(
                _setting(
                    runtime,
                    document,
                    "Outlook: ручной выбор при отсутствии",
                    1,
                )
                or 0
            )
            else 0
        )
        model.insertByName("Fallback", fallback)

        ok = model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        ok.Name = "OK"
        ok.PositionX = 176
        ok.PositionY = y + 22
        ok.Width = 52
        ok.Height = 18
        ok.Label = "Сохранить"
        ok.PushButtonType = 1
        model.insertByName("OK", ok)

        cancel = model.createInstance("com.sun.star.awt.UnoControlButtonModel")
        cancel.Name = "Cancel"
        cancel.PositionX = 234
        cancel.PositionY = y + 22
        cancel.Width = 54
        cancel.Height = 18
        cancel.Label = "Отмена"
        cancel.PushButtonType = 2
        model.insertByName("Cancel", cancel)

        dialog = manager.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialog", context
        )
        dialog.setModel(model)
        toolkit = manager.createInstanceWithContext(
            "com.sun.star.awt.Toolkit", context
        )
        parent = document.getCurrentController().getFrame().getContainerWindow()
        dialog.createPeer(toolkit, parent)
        try:
            if int(dialog.execute()) != 1:
                return
            values = {
                "Outlook: почтовый ящик": dialog.getControl(
                    "Mailbox"
                ).getText().strip(),
                "Outlook: папка": dialog.getControl("Folder").getText().strip(),
                "Outlook: маска вложения": dialog.getControl(
                    "Attachment"
                ).getText().strip(),
                "Outlook: тема содержит": dialog.getControl(
                    "Subject"
                ).getText().strip(),
                "Outlook: отправитель содержит": dialog.getControl(
                    "Sender"
                ).getText().strip(),
                "Outlook: глубина поиска, дней": float(
                    dialog.getControl("Days").getValue()
                ),
                "Outlook: ручной выбор при отсутствии": float(
                    dialog.getControl("Fallback").getState() != 0
                ),
            }
        finally:
            dialog.dispose()

        if not values["Outlook: почтовый ящик"]:
            raise RuntimeError("Почтовый ящик Outlook не может быть пустым.")
        if not values["Outlook: маска вложения"]:
            raise RuntimeError("Маска имени вложения не может быть пустой.")
        for key, value in values.items():
            runtime._EXACT_REPORT_MODULE._meta(runtime, document, key, value)
        runtime._message("Настройки импорта генерации сохранены в книге.")
    except Exception as exc:
        runtime._message(f"Не удалось сохранить настройки Outlook: {exc}", error=True)


def _ps(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _outlook_attachment(runtime, document, report_date: date) -> Path | None:
    if os.name != "nt":
        return None
    mailbox = str(
        _setting(
            runtime,
            document,
            "Outlook: почтовый ящик",
            "НСС Кочубеевская ВЭС",
        )
    )
    folder_path = str(_setting(runtime, document, "Outlook: папка", "Входящие"))
    pattern = str(
        _setting(
            runtime,
            document,
            "Outlook: маска вложения",
            "Генерация КВЭС за вчера_{date}.xlsx",
        )
    ).replace(
        "{date}", (report_date - timedelta(days=1)).strftime("%d_%m_%Y")
    )
    subject = str(_setting(runtime, document, "Outlook: тема содержит", ""))
    sender = str(
        _setting(runtime, document, "Outlook: отправитель содержит", "")
    )
    days = max(
        1,
        min(
            60,
            int(
                float(
                    _setting(
                        runtime,
                        document,
                        "Outlook: глубина поиска, дней",
                        7,
                    )
                )
            ),
        ),
    )

    safe_name = re.sub(r'[<>:"/\\|?*]+', "_", pattern.replace("*", "all"))
    target_dir = Path(tempfile.gettempdir()) / "ShiftHelper"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_name

    script = f"""
$ErrorActionPreference = 'Stop'
$mailbox = {_ps(mailbox)}
$folderPath = {_ps(folder_path)}
$pattern = {_ps(pattern)}
$subjectFilter = {_ps(subject)}
$senderFilter = {_ps(sender)}
$target = {_ps(target)}
$cutoff = [datetime]{_ps((report_date - timedelta(days=days)).isoformat())}
$outlook = New-Object -ComObject Outlook.Application
$ns = $outlook.GetNamespace('MAPI')
$folder = $null
try {{
  $folder = $ns.Folders.Item($mailbox)
  foreach ($part in ($folderPath -split '[\\\\/]')) {{
    if ($part) {{ $folder = $folder.Folders.Item($part) }}
  }}
}} catch {{}}
if ($null -eq $folder) {{
  $recip = $ns.CreateRecipient($mailbox)
  $recip.Resolve() | Out-Null
  $folder = $ns.GetSharedDefaultFolder($recip, 6)
}}
$items = $folder.Items
$items.Sort('[ReceivedTime]', $true)
$found = $false
foreach ($item in $items) {{
  try {{
    if ($item.ReceivedTime -lt $cutoff) {{ break }}
    if ($subjectFilter -and ($item.Subject -notlike ('*' + $subjectFilter + '*'))) {{ continue }}
    $senderText = (($item.SenderName | Out-String) + ' ' + ($item.SenderEmailAddress | Out-String))
    if ($senderFilter -and ($senderText -notlike ('*' + $senderFilter + '*'))) {{ continue }}
    foreach ($att in $item.Attachments) {{
      if ($att.FileName -like $pattern) {{
        if (Test-Path $target) {{ Remove-Item $target -Force }}
        $att.SaveAsFile($target)
        $found = $true
        break
      }}
    }}
  }} catch {{}}
  if ($found) {{ break }}
}}
if (-not $found) {{ exit 3 }}
Write-Output $target
"""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=flags,
            check=False,
        )
    except Exception:
        return None
    return target if completed.returncode == 0 and target.is_file() else None


def import_generation(runtime, _args=None) -> None:
    try:
        document = runtime._document()
        if not document.getSheets().hasByName(runtime.INPUT_MAIN):
            runtime.prepare_report_input_sheets()
        main = document.getSheets().getByName(runtime.INPUT_MAIN)
        values = runtime._main_map(main, document)
        report_date, _offset = runtime._prep_settings(document)
        source = _outlook_attachment(runtime, document, report_date)
        fallback = float(
            _setting(
                runtime,
                document,
                "Outlook: ручной выбор при отсутствии",
                1,
            )
            or 0
        )
        if source is None and fallback:
            source = runtime._EXACT_ORIGINAL_PICK_XLSX(
                "Вложение Outlook не найдено. Выберите файл генерации вручную"
            )
        if source is None:
            runtime._message(
                "Подходящее вложение Outlook не найдено. "
                "Проверьте «Настройки импорта генерации»."
            )
            return

        daily, own = runtime._read_generation(source)
        old_date = values.get("Последняя дата импорта генерации")
        if isinstance(old_date, datetime):
            old_date = old_date.date()
        old_daily = float(values.get("Последняя выработка за сутки") or 0)
        old_own = float(values.get("Последние собственные нужды за сутки") or 0)
        month_generation = float(values.get("Выработка с начала месяца, кВт*ч") or 0)
        month_own = float(values.get("Собственные нужды с начала месяца, кВт*ч") or 0)
        if isinstance(old_date, date) and old_date == report_date:
            month_generation += daily - old_daily
            month_own += own - old_own
        elif (
            isinstance(old_date, date)
            and old_date.year == report_date.year
            and old_date.month == report_date.month
        ):
            month_generation += daily
            month_own += own
        elif report_date.day <= 2:
            month_generation, month_own = daily, own
        else:
            month_generation += daily
            month_own += own

        updates = {
            "Выработка за предыдущие сутки, кВт*ч": daily,
            "Выработка с начала месяца, кВт*ч": month_generation,
            "Собственные нужды за сутки, кВт*ч": own,
            "Собственные нужды с начала месяца, кВт*ч": month_own,
            "Последний файл генерации": source.name,
            "Последняя дата импорта генерации": report_date,
            "Последняя выработка за сутки": daily,
            "Последние собственные нужды за сутки": own,
        }
        for key, value in updates.items():
            runtime._set_main_value(main, key, value, document)
        runtime._write_value(
            main.getCellByPosition(9, report_date.month + 3), month_generation
        )
        runtime._EXACT_REPORT_MODULE._apply_formulas(runtime, document)
        runtime._message(
            "Генерация импортирована.\n"
            f"Выработка: {daily:.0f} кВт*ч.\n"
            f"Средняя нагрузка: {daily / 24000:.2f} МВт.\n"
            f"Собственные нужды: {own:.0f} кВт*ч.\n"
            f"Источник: {source.name}"
        )
    except Exception as exc:
        runtime._message(f"Не удалось импортировать генерацию: {exc}", error=True)


def _prepare_post(module, runtime, original, _args=None) -> None:
    original(_args)
    document = runtime._document()
    _ensure_outage_form(module, runtime, document)
    _ensure_service(module, runtime, document)
    _apply_formulas(module, runtime, document, lambda _r, _d: None)
    _refresh_outages(runtime, document)
    _install_calendar_button(runtime, document)
    _install_generation_settings_button(runtime, document)


def install_acceptance_repairs(module, runtime, _extension_root: Path) -> None:
    """Install the owner-visible repair set without redrawing approved report sheets."""

    if getattr(runtime, "_ACCEPTANCE_REPAIRS_006_APPLIED", False):
        return
    runtime._EXACT_REPORT_MODULE = module

    module._ensure_service = lambda rt, doc: _ensure_service(module, rt, doc)
    module._meta = lambda rt, doc, key, value=...: _meta(
        module, rt, doc, key, value
    )
    module._status_map = lambda rt, doc: _status_map(module, rt, doc)

    original_apply = module._apply_formulas
    module._apply_formulas = lambda rt, doc: _apply_formulas(
        module, rt, doc, original_apply
    )

    original_prepare = runtime.prepare_report_input_sheets
    runtime.prepare_report_input_sheets = lambda _args=None: _prepare_post(
        module, runtime, original_prepare, _args
    )
    runtime.show_report_date_calendar = lambda _args=None: show_report_date_calendar(
        runtime, _args
    )
    runtime.show_generation_import_settings = (
        lambda _args=None: show_generation_import_settings(runtime, _args)
    )
    runtime.import_generation_from_outlook = lambda _args=None: import_generation(
        runtime, _args
    )

    workspace = tuple(getattr(runtime, "WORKSPACE_SHEETS", ()))
    if INPUT_OUTAGES not in workspace:
        runtime.WORKSPACE_SHEETS = (*workspace, INPUT_OUTAGES)
    runtime.INPUT_OUTAGES = INPUT_OUTAGES
    runtime._ACCEPTANCE_REPAIRS_006_APPLIED = True
