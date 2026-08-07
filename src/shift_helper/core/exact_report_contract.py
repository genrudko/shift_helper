"""Exact embedded report forms for Shift-Helper LibreOffice Calc."""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import uno

_TEMPLATE = Path("Templates") / "report_template.xlsx"
FORMS = (
    ("Основные данные", "Ввод - Основные", "B2", "Основные данные"),
    ("Команды по внешней инициативе", "Ввод - Команды", "B3", "ГТП"),
    ("Нарушения ОТиПБ + Экология", "Ввод - Нарушения", "B3", "№"),
    ("Состояние ВЭУ", "Ввод - Состояние ВЭУ", "D3", "ВЭУ"),
    ("Запланированные работы", "Ввод - Работы", "B3", "Вид заявки"),
    ("Дефекты оборудования", "Ввод - Дефекты", "B3", "№"),
)
MAIN = {
    "Установленная мощность ВЭС, МВт": "C3",
    "Средняя нагрузка за предыдущие сутки, МВт": "C6",
    "Текущая нагрузка на 07:00, МВт": "C7",
    "Выработка за предыдущие сутки, кВт*ч": "C10",
    "Выработка с начала месяца, кВт*ч": "C11",
    "Собственные нужды за сутки, кВт*ч": "C16",
    "Собственные нужды с начала месяца, кВт*ч": "C17",
    "Температура наружного воздуха, °C": "F10",
    "Скорость ветра, м/с": "F11",
    "Направление ветра": "F12",
    "Напряжение U 35 кВ, кВ": "F15",
    "Напряжение U 110/220/330 кВ, кВ": "F16",
    "Мощность Q 35 кВ, МВАр": "F17",
    "Мощность Q 110/220/330 кВ, МВАр": "F18",
}
META = (
    "Последний файл генерации",
    "Последняя дата импорта генерации",
    "Последняя выработка за сутки",
    "Последние собственные нужды за сутки",
)
STATUSES = ("Работа", "Останов", "Авария", "Ремонт")


def _template(runtime: Any) -> Path:
    path = Path(runtime._SHIFT_HELPER_EXTENSION_ROOT) / _TEMPLATE
    if not path.is_file():
        raise RuntimeError("В расширении отсутствует встроенный шаблон рапорта.")
    return path


def _cell(sheet, address):
    return sheet.getCellRangeByName(address)


def _exact(document, name, address, marker):
    sheets = document.getSheets()
    return sheets.hasByName(name) and str(_cell(sheets.getByName(name), address).getString()).strip() == marker


def _ensure_service(runtime, document):
    prep = document.getSheets().getByName(runtime.INPUT_PREP)
    prep.getCellByPosition(6, 0).setString("ВЭУ")
    prep.getCellByPosition(7, 0).setString("Статус ВЭУ")
    old = {str(prep.getCellByPosition(6, r).getString()).strip(): str(prep.getCellByPosition(7, r).getString()).strip() for r in range(1, 90)}
    for number in range(1, 85):
        name = f"ВЭУ-{number}"
        prep.getCellByPosition(6, number).setString(name)
        prep.getCellByPosition(7, number).setString(old.get(name) if old.get(name) in STATUSES else "Работа")
    prep.getCellByPosition(9, 0).setString("Служебный параметр")
    prep.getCellByPosition(10, 0).setString("Значение")
    existing = {str(prep.getCellByPosition(9, r).getString()).strip(): r for r in range(1, 30)}
    row = max(existing.values(), default=0) + 1
    for key in META:
        if key not in existing:
            prep.getCellByPosition(9, row).setString(key)
            existing[key] = row
            row += 1
    for col in (6, 7, 9, 10):
        try:
            prep.getColumns().getByIndex(col).IsVisible = False
        except Exception:
            pass


def _meta(runtime, document, key, value=...):
    _ensure_service(runtime, document)
    prep = document.getSheets().getByName(runtime.INPUT_PREP)
    row = next(r for r in range(1, 30) if str(prep.getCellByPosition(9, r).getString()).strip() == key)
    cell = prep.getCellByPosition(10, row)
    if value is ...:
        return runtime._cell_value(cell, document)
    runtime._write_value(cell, value, document, "DD.MM.YYYY" if isinstance(value, (date, datetime)) else None)


def _status_map(runtime, document):
    _ensure_service(runtime, document)
    prep = document.getSheets().getByName(runtime.INPUT_PREP)
    return {str(prep.getCellByPosition(6, r).getString()).strip(): str(prep.getCellByPosition(7, r).getString()).strip() for r in range(1, 85)}


def _main_map(runtime, sheet, document):
    values = {key: runtime._cell_value(_cell(sheet, address), document) for key, address in MAIN.items()}
    prep = document.getSheets().getByName(runtime.INPUT_PREP)
    values["Дата рапорта"] = runtime._cell_value(prep.getCellByPosition(1, 2), document)
    values["ФИО НСС"] = runtime._cell_value(prep.getCellByPosition(1, 6), document)
    for key in META:
        values[key] = _meta(runtime, document, key)
    values["_plans"] = {m: float(v) for m in range(1, 13) if isinstance((v := runtime._cell_value(sheet.getCellByPosition(8, m + 3), document)), (int, float))}
    values["_facts"] = {m: float(v) for m in range(1, 13) if isinstance((v := runtime._cell_value(sheet.getCellByPosition(9, m + 3), document)), (int, float))}
    return values


def _set_main(runtime, sheet, key, value, document):
    prep = document.getSheets().getByName(runtime.INPUT_PREP)
    if key == "Дата рапорта":
        runtime._write_value(prep.getCellByPosition(1, 2), value, document, "DD.MM.YYYY")
    elif key == "ФИО НСС":
        runtime._write_value(prep.getCellByPosition(1, 6), value, document)
    elif key in META:
        _meta(runtime, document, key, value)
    elif key in MAIN:
        runtime._write_value(_cell(sheet, MAIN[key]), value, document)
    else:
        raise RuntimeError(f"В точной форме отсутствует параметр: {key}.")


def _rows(runtime, sheet, columns, document):
    name = str(sheet.getName())
    if name == runtime.INPUT_VIOLATIONS:
        result, category = [], "ОТиПБ"
        for row in range(1, max(runtime._last_used_row(sheet), 13) + 1):
            label = str(sheet.getCellByPosition(1, row).getString()).strip()
            if label in ("ОТиПБ", "Экология", "Объектовая безопасность"):
                category = label
                continue
            values = [runtime._cell_value(sheet.getCellByPosition(1 + col, row), document) for col in range(5)]
            if label != "№" and any(v not in (None, "") for v in values):
                result.append([category, *values])
        return result
    config = {
        runtime.INPUT_COMMANDS: (6, 5),
        runtime.INPUT_WORKS: (11, 13),
        runtime.INPUT_DEFECTS: (10, 17),
    }.get(name)
    if config is None:
        return runtime._EXACT_ORIGINAL_READ_ROWS(sheet, columns, document)
    count, minimum_end = config
    result = []
    for row in range(3, max(runtime._last_used_row(sheet), minimum_end) + 1):
        values = [runtime._cell_value(sheet.getCellByPosition(1 + col, row), document) for col in range(count)]
        if any(value not in (None, "") for value in values):
            result.append(values)
    return result


def _infer(reason, p_avail, p_repair):
    text = str(reason or "").casefold()
    if any(x in text for x in ("авар", "отказ", "поврежд", "неисправ", "ошибка", "сработка")):
        return "Авария"
    if re.search(r"(?:^|[\s,;:()/-])ремонт(?:[\s,;:()/-]|$)", text):
        return "Ремонт"
    if any(x in text for x in ("техническое обслуживание", "плановые работы", "для проведения работ", "отбор проб", "ревизия")) or re.search(r"(?:^|[\s,;:()/-])то(?:[\s,;:()/-]|$)", text):
        return "Останов"
    return "Работа" if float(p_avail or 0) > 0 else ("Ремонт" if float(p_repair or 0) > 0 and not text else "Останов")


def _state_rows(runtime, document):
    sheet = document.getSheets().getByName(runtime.INPUT_STATE)
    statuses = _status_map(runtime, document)
    result, group, code = [], "", ""
    for row in range(3, max(runtime._last_used_row(sheet), 97) + 1):
        name = str(sheet.getCellByPosition(3, row).getString()).strip()
        row_code = str(sheet.getCellByPosition(2, row).getString()).strip()
        if row_code and not name:
            group, code = str(sheet.getCellByPosition(1, row).getString()).strip(), row_code
            continue
        if not name.startswith("ВЭУ-"):
            continue
        data = [runtime._cell_value(sheet.getCellByPosition(col, row), document) for col in range(4, 11)]
        status = statuses.get(name) if statuses.get(name) in STATUSES else _infer(data[4], data[3], data[2])
        result.append(runtime._normalize_state_row([group, code, name, data[0], data[1], data[2], data[3], status, data[4], data[5], data[6]]))
    return result


def _import_form(document, source, source_name, target_name):
    sheets = document.getSheets()
    if sheets.hasByName(target_name):
        sheets.removeByName(target_name)
    position = sheets.getCount()
    imported = sheets.importSheet(source, source_name, position)
    sheets.getByIndex(imported).setName(target_name)


def _formula(sheet, address, formula):
    _cell(sheet, address).setFormula(formula)


def _apply_formulas(runtime, document):
    sheets = document.getSheets()
    prep, main, state, works = (sheets.getByName(name) for name in (runtime.INPUT_PREP, runtime.INPUT_MAIN, runtime.INPUT_STATE, runtime.INPUT_WORKS))
    _ensure_service(runtime, document)
    if runtime._cell_value(prep.getCellByPosition(1, 2), document) in (None, ""):
        runtime._write_value(prep.getCellByPosition(1, 2), date.today(), document, "DD.MM.YYYY")
    if runtime._cell_value(prep.getCellByPosition(1, 5), document) in (None, ""):
        runtime._write_value(prep.getCellByPosition(1, 5), -3.0)
    prep.getCellByPosition(0, 6).setString("ФИО НСС")
    _formula(main, "B1", '=CONCATENATE("Рапорт НСС на ";TEXT(\'Подготовка рапорта\'.B3;"DD.MM.YYYY");" Кочубеевская ВЭС (";\'Подготовка рапорта\'.B7;"). Последние изменения ";TEXT(NOW();"DD.MM.YYYY, HH:MM:SS"))')
    _formula(main, "B6", '=CONCATENATE(" Средняя нагрузка за ";TEXT(\'Подготовка рапорта\'.B3-1;"DD.MM.YYYY");", МВт")')
    _formula(main, "B7", '=CONCATENATE(" Текущая нагрузка на 07:00 ";TEXT(\'Подготовка рапорта\'.B3;"DD.MM.YYYY");", МВт")')
    _formula(main, "B10", '=CONCATENATE(" Выработка за ";TEXT(\'Подготовка рапорта\'.B3-1;"DD.MM.YYYY");", кВт*ч")')
    _formula(main, "B12", '=CONCATENATE(" План с 01 по ";TEXT(\'Подготовка рапорта\'.B3;"DD.MM.YYYY");", кВт*ч")')
    _formula(main, "E9", '=CONCATENATE("Погодные условия на 07:00 ";TEXT(\'Подготовка рапорта\'.B3;"DD.MM.YYYY"))')
    _formula(main, "E14", '=CONCATENATE("Параметры сети ВЭС на 07:00 ";TEXT(\'Подготовка рапорта\'.B3;"DD.MM.YYYY"))')
    _formula(main, "H3", '=CONCATENATE("План/Факт Кочубеевская ВЭС ";YEAR(\'Подготовка рапорта\'.B3))')
    _formula(main, "H18", '=CONCATENATE("Нарастающий итог на ";TEXT(\'Подготовка рапорта\'.B3;"DD.MM.YYYY"))')
    groups = []
    for row in range(3, max(runtime._last_used_row(state), 97) + 1):
        name, code = str(state.getCellByPosition(3, row).getString()).strip(), str(state.getCellByPosition(2, row).getString()).strip()
        if code and not name:
            groups.append(row + 1)
        elif name.startswith("ВЭУ-"):
            _formula(state, f"H{row + 1}", f"=MAX(F{row + 1}-G{row + 1};0)")
    for index, group_row in enumerate(groups):
        first, last = group_row + 1, (groups[index + 1] - 1 if index + 1 < len(groups) else max(runtime._last_used_row(state), 97) + 1)
        for col in "EFGH":
            _formula(state, f"{col}{group_row}", f"=SUM({col}{first}:{col}{last})")
    if groups:
        _formula(main, "C3", "=SUM(" + ";".join(f"'Ввод - Состояние ВЭУ'.E{row}" for row in groups) + ")")
        _formula(main, "C4", "=SUM(" + ";".join(f"'Ввод - Состояние ВЭУ'.H{row}" for row in groups) + ")")
    for row, status in zip(range(4, 8), ("Останов", "Работа", "Авария", "Ремонт")):
        _formula(main, f"F{row}", f'=COUNTIF(\'Подготовка рапорта\'.H2:H85;"{status}")')
    _formula(main, "C12", '=INDEX(I5:I16;MONTH(\'Подготовка рапорта\'.B3))*(DAY(\'Подготовка рапорта\'.B3)-1)/DAY(EOMONTH(\'Подготовка рапорта\'.B3;0))')
    _formula(main, "C13", "=C11-C12")
    _formula(main, "C14", "=IFERROR(C11/C12;0)")
    _formula(main, "C15", '=IF(C13>=0;-1;(INDEX(I5:I16;MONTH(\'Подготовка рапорта\'.B3))-C11)/((DAY(EOMONTH(\'Подготовка рапорта\'.B3;0))-DAY(\'Подготовка рапорта\'.B3)+1)*24))')
    for month in range(1, 13):
        row = month + 4
        _formula(main, f"K{row}", f'=IF(J{row}="";"";J{row}-I{row})')
        _formula(main, f"L{row}", f'=IFERROR(J{row}/I{row};"")')
    for address, formula in (("I17", "=SUM(I5:I16)"), ("J17", "=SUM(J5:J16)"), ("K17", "=J17-I17"), ("L17", '=IFERROR(J17/I17;"")'), ("K18", "=J18-I18"), ("L18", '=IFERROR(J18/I18;"")')):
        _formula(main, address, formula)
    _formula(main, "I18", '=SUMPRODUCT(I5:I16;--(ROW(I5:I16)-ROW(I5)+1<MONTH(\'Подготовка рапорта\'.B3)))+INDEX(I5:I16;MONTH(\'Подготовка рапорта\'.B3))*(DAY(\'Подготовка рапорта\'.B3)-1)/DAY(EOMONTH(\'Подготовка рапорта\'.B3;0))')
    _formula(main, "J18", '=SUMPRODUCT(J5:J16;--(ROW(J5:J16)-ROW(J5)+1<=MONTH(\'Подготовка рапорта\'.B3)))')
    for row in range(4, 15):
        _formula(works, f"G{row}", f'=IF(COUNTA(E{row}:F{row})=0;"";MAX(E{row}-F{row};0))')
    for name, title in ((runtime.INPUT_COMMANDS, "Команды по внешней инициативе"), (runtime.INPUT_VIOLATIONS, "Нарушения ОТиПБ + Экология"), (runtime.INPUT_STATE, "Состояние ВЭУ"), (runtime.INPUT_WORKS, "Запланированные работы"), (runtime.INPUT_DEFECTS, "Дефекты оборудования")):
        _formula(sheets.getByName(name), "B1", f'=CONCATENATE("{title} на ";TEXT(\'Подготовка рапорта\'.B3;"DD.MM.YYYY");" Кочубеевская ВЭС")')
    try:
        document.calculateAll()
    except Exception:
        pass


def _prepare(runtime, _args=None):
    try:
        document = runtime._document()
        prep, created = runtime._ensure_sheet(document, runtime.INPUT_PREP)
        runtime._setup_prep(document, prep, created)
        source = runtime._open_hidden(_template(runtime), read_only=True)
        try:
            for source_name, target_name, address, marker in FORMS:
                if not _exact(document, target_name, address, marker):
                    _import_form(document, source, source_name, target_name)
        finally:
            runtime._close(source)
        _apply_formulas(runtime, document)
        report_date, offset = runtime._prep_settings(document)
        runtime._refresh_prep_window(document, prep, report_date)
        try:
            from shift_helper.core.operator_tools import _workspace_install_calendar_button
            _workspace_install_calendar_button(runtime, document)
        except Exception:
            pass
        runtime._message(f"Контур подготовлен по встроенному утверждённому шаблону.\nДата: {report_date:%d.%m.%Y}. Смещение: {offset:+g} ч.\nВнешний файл шаблона не требуется.")
    except Exception as exc:
        runtime._message(f"Не удалось подготовить точный контур рапорта: {exc}", error=True)


def _output(runtime, _unused, report_date):
    picker = runtime._picker("FILESAVE_AUTOEXTENSION", "Сохранить полный утренний рапорт")
    try:
        source = runtime._document_path(runtime._document())
        if source is not None:
            picker.setDisplayDirectory(uno.systemPathToFileUrl(str(source.parent)))
        picker.setDefaultName(runtime.default_report_filename(report_date))
        ok = uno.getConstantByName("com.sun.star.ui.dialogs.ExecutableDialogResults.OK")
        if int(picker.execute()) != int(ok):
            return None
        files = tuple(picker.getFiles())
    finally:
        picker.dispose()
    if not files:
        return None
    path = Path(uno.fileUrlToSystemPath(files[0])).resolve()
    return path if path.suffix.casefold() == ".xlsx" else path.with_suffix(".xlsx")


def _generation(runtime, _args=None):
    try:
        document = runtime._document()
        runtime._require_input_sheets(document)
        main = document.getSheets().getByName(runtime.INPUT_MAIN)
        report_date, _ = runtime._prep_settings(document)
        values = _main_map(runtime, main, document)
        source = runtime._outlook_attachment(report_date) or runtime._EXACT_ORIGINAL_PICK_XLSX("Вложение Outlook не найдено. Выберите файл генерации вручную")
        if source is None:
            return
        daily, own = runtime._read_generation(source)
        old_date = values.get("Последняя дата импорта генерации")
        if isinstance(old_date, datetime):
            old_date = old_date.date()
        month_generation = float(values.get("Выработка с начала месяца, кВт*ч") or 0)
        month_own = float(values.get("Собственные нужды с начала месяца, кВт*ч") or 0)
        if isinstance(old_date, date) and old_date == report_date:
            month_generation += daily - float(values.get("Последняя выработка за сутки") or 0)
            month_own += own - float(values.get("Последние собственные нужды за сутки") or 0)
        elif isinstance(old_date, date) and (old_date.year, old_date.month) == (report_date.year, report_date.month):
            month_generation, month_own = month_generation + daily, month_own + own
        elif isinstance(old_date, date) or report_date.day <= 2:
            month_generation, month_own = daily, own
        else:
            month_generation, month_own = month_generation + daily, month_own + own
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
            _set_main(runtime, main, key, value, document)
        runtime._write_value(main.getCellByPosition(9, report_date.month + 3), month_generation)
        document.calculateAll()
        runtime._message(f"Генерация импортирована.\nВыработка: {daily:.0f} кВт*ч.\nСобственные нужды: {own:.0f} кВт*ч.\nИсточник: {source.name}")
    except Exception as exc:
        runtime._message(f"Не удалось импортировать генерацию: {exc}", error=True)


def install_exact_report_contract(runtime: Any, extension_root: Path) -> None:
    if getattr(runtime, "_EXACT_REPORT_CONTRACT_003_APPLIED", False):
        return
    runtime._SHIFT_HELPER_EXTENSION_ROOT = str(Path(extension_root).resolve())
    runtime._EXACT_ORIGINAL_READ_ROWS = runtime._read_rows
    runtime._EXACT_ORIGINAL_PICK_XLSX = runtime._pick_xlsx
    runtime._main_map = lambda sheet, document: _main_map(runtime, sheet, document)
    runtime._set_main_value = lambda sheet, key, value, document: _set_main(runtime, sheet, key, value, document)
    runtime._read_rows = lambda sheet, columns, document, start_row=1: _rows(runtime, sheet, columns, document)
    runtime._state_rows = lambda document: _state_rows(runtime, document)
    runtime._pick_xlsx = lambda title: _template(runtime) if "шаблон" in str(title).casefold() else runtime._EXACT_ORIGINAL_PICK_XLSX(title)
    runtime._pick_output = lambda template, report_date: _output(runtime, template, report_date)
    runtime.prepare_report_input_sheets = lambda _args=None: _prepare(runtime, _args)
    runtime.import_generation_from_outlook = lambda _args=None: _generation(runtime, _args)
    runtime._EXACT_REPORT_CONTRACT_003_APPLIED = True


def install_exact_tools_contract(runtime: Any, extension_root: Path) -> None:
    """Reserve the exact-form tools patch point for coordinate-specific macros."""
    runtime._SHIFT_HELPER_EXTENSION_ROOT = str(Path(extension_root).resolve())
    runtime._EXACT_TOOLS_CONTRACT_003_APPLIED = True
