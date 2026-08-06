"""UNO component exposing Shift-Helper controls to LibreOffice Calc UI."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import uno
import unohelper
from com.sun.star.task import XJobExecutor

_IMPLEMENTATION_NAME = "ru.kves.shifthelper.calc.controls"
_CALC_SERVICE = "com.sun.star.sheet.SpreadsheetDocument"
_INPUT_PREP = "Подготовка рапорта"
_INPUT_MAIN = "Ввод - Основные"
_RUNTIME_FILES = {
    "auto": ("_shift_helper_extension_auto", "shift_helper_auto.py"),
    "report": ("_shift_helper_extension_report", "shift_helper_report.py"),
    "tools": ("_shift_helper_extension_tools", "shift_helper_tools.py"),
}
_ACTIONS = {
    "enable": ("auto", "enable_automatic_input"),
    "disable": ("auto", "disable_automatic_input"),
    "status": ("auto", "automatic_input_status"),
    "prepare": ("report", "prepare_report_input_sheets"),
    "generation": ("report", "import_generation_from_outlook"),
    "report": ("report", "generate_full_report"),
    "calendar": ("tools", "show_calendar"),
    "calendarprep": ("tools", "show_report_date_calendar"),
    "time": ("tools", "show_time_picker"),
    "autofit": ("tools", "auto_fit_selected_rows"),
    "clean": ("tools", "clean_selected_spaces"),
    "mergecopy": ("tools", "merge_and_copy_selection"),
    "sorttime": ("tools", "sort_selected_rows_by_time"),
    "maintenance": ("tools", "insert_wtg_maintenance_text"),
    "inspections": ("tools", "show_today_inspections"),
    "rotor": ("tools", "update_rotor_limits_from_log"),
    "mail": ("tools", "create_outlook_mail_draft"),
}
_RUNTIMES: dict[str, ModuleType] = {}
_REPORT_REPAIRS_MODULE = "_shift_helper_extension_report_repairs"
_REPORT_REPAIRS_FILE = "shift_helper_calc.py"


def _desktop(context):
    return context.getServiceManager().createInstanceWithContext(
        "com.sun.star.frame.Desktop", context
    )


def _current_calc(context):
    document = _desktop(context).getCurrentComponent()
    if document is None or not document.supportsService(_CALC_SERVICE):
        raise RuntimeError("Откройте книгу LibreOffice Calc.")
    return document


def _message(context, document, text: str, *, error: bool = False) -> None:
    toolkit = context.getServiceManager().createInstanceWithContext(
        "com.sun.star.awt.Toolkit", context
    )
    parent = document.getCurrentController().getFrame().getContainerWindow()
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


def _component_root() -> Path:
    raw = str(globals().get("__file__", "")).strip()
    if not raw:
        raise RuntimeError("LibreOffice не передал путь установленного расширения.")
    if raw.lower().startswith("file:"):
        raw = uno.fileUrlToSystemPath(raw)
    return Path(raw).resolve().parent


def _patch_report_runtime(module: ModuleType, scripts: Path) -> None:
    repairs_path = scripts / _REPORT_REPAIRS_FILE
    if not repairs_path.is_file():
        raise RuntimeError(
            f"В установленном расширении отсутствует {repairs_path.name}."
        )
    spec = importlib.util.spec_from_file_location(
        _REPORT_REPAIRS_MODULE, repairs_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Не удалось создать загрузчик {repairs_path.name}."
        )
    repairs = importlib.util.module_from_spec(spec)
    sys.modules[_REPORT_REPAIRS_MODULE] = repairs
    try:
        spec.loader.exec_module(repairs)
        repairs.patch_report_runtime(module)
    except Exception:
        sys.modules.pop(_REPORT_REPAIRS_MODULE, None)
        raise


def _load_runtime(runtime_key: str) -> ModuleType:
    cached = _RUNTIMES.get(runtime_key)
    if cached is not None:
        return cached
    module_name, filename = _RUNTIME_FILES[runtime_key]
    root = _component_root()
    scripts = root / "Scripts" / "python"
    pythonpath = scripts / "pythonpath"
    runtime_path = scripts / filename
    if not runtime_path.is_file():
        raise RuntimeError(f"В установленном расширении отсутствует {runtime_path.name}.")
    for directory in (pythonpath, scripts):
        value = str(directory)
        if value not in sys.path:
            sys.path.insert(0, value)
    spec = importlib.util.spec_from_file_location(module_name, runtime_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось создать загрузчик {runtime_path.name}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        if runtime_key == "report":
            _patch_report_runtime(module, scripts)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    _RUNTIMES[runtime_key] = module
    return module


class _ScriptContextAdapter:
    def __init__(self, context, desktop, document) -> None:
        self._context = context
        self._desktop = desktop
        self._document = document

    def getComponentContext(self):  # noqa: N802
        return self._context

    def getDesktop(self):  # noqa: N802
        return self._desktop

    def getDocument(self):  # noqa: N802
        return self._document

    def getInvocationContext(self):  # noqa: N802
        return self._document


def _cell_signature(document, sheet_name: str, column: int, row: int):
    sheets = document.getSheets()
    if not sheets.hasByName(sheet_name):
        return None
    cell = sheets.getByName(sheet_name).getCellByPosition(column, row)
    return (str(cell.getFormula()), float(cell.getValue()), str(cell.getString()))


def _cell_is_empty(cell) -> bool:
    return not str(cell.getString()).strip() and not float(cell.getValue())


def _copy_date_value(source, target) -> None:
    value = float(source.getValue())
    if value:
        target.setValue(value)
    else:
        target.setString(str(source.getString()).strip())


def _synchronize_report_date(document, before_main, before_prep) -> None:
    """Make preparation B3 authoritative after the legacy preparation routine."""
    sheets = document.getSheets()
    if not sheets.hasByName(_INPUT_PREP) or not sheets.hasByName(_INPUT_MAIN):
        return

    prep_cell = sheets.getByName(_INPUT_PREP).getCellByPosition(1, 2)
    main_cell = sheets.getByName(_INPUT_MAIN).getCellByPosition(1, 1)
    after_main = _cell_signature(document, _INPUT_MAIN, 1, 1)
    main_changed = before_main is not None and after_main != before_main
    prep_created = before_prep is None

    # The integrated runtime imports an old report date into the legacy main cell.
    # Copy it to B3 only when that import changed the cell, when the workspace was
    # just created, or when B3 is genuinely empty. Existing operator B3 data wins.
    if (
        not _cell_is_empty(main_cell)
        and (main_changed or prep_created or _cell_is_empty(prep_cell))
    ):
        _copy_date_value(main_cell, prep_cell)

    main_cell.setFormula(f"='{_INPUT_PREP}'.B3")
    try:
        document.calculateAll()
    except Exception:
        pass


def _invoke_runtime(context, document, runtime_key: str, function_name: str) -> None:
    runtime = _load_runtime(runtime_key)
    runtime.XSCRIPTCONTEXT = _ScriptContextAdapter(
        context,
        _desktop(context),
        document,
    )
    function = getattr(runtime, function_name, None)
    if not callable(function):
        raise RuntimeError(f"В ядре Shift-Helper отсутствует функция {function_name}.")

    synchronize_date = runtime_key == "report" and function_name in (
        "prepare_report_input_sheets",
        "import_generation_from_outlook",
    )
    before_main = (
        _cell_signature(document, _INPUT_MAIN, 1, 1) if synchronize_date else None
    )
    before_prep = (
        _cell_signature(document, _INPUT_PREP, 1, 2) if synchronize_date else None
    )
    function()
    if runtime_key == "report" and function_name == "prepare_report_input_sheets":
        repair = getattr(runtime, "_repair_photo_state_statuses", None)
        if callable(repair):
            repair(document)
    if synchronize_date:
        _synchronize_report_date(document, before_main, before_prep)


class ShiftHelperControls(unohelper.Base, XJobExecutor):
    def __init__(self, context: Any) -> None:
        self.context = context

    def trigger(self, event: str) -> None:
        document = None
        try:
            document = _current_calc(self.context)
            action = str(event).strip().lower()
            route = _ACTIONS.get(action)
            if route is None:
                raise RuntimeError(f"Неизвестная команда Shift-Helper: {event!r}.")
            _invoke_runtime(self.context, document, route[0], route[1])
        except Exception as exc:
            if document is None:
                try:
                    document = _current_calc(self.context)
                except Exception:
                    return
            _message(self.context, document, str(exc), error=True)


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    ShiftHelperControls,
    _IMPLEMENTATION_NAME,
    ("com.sun.star.task.Job",),
)
