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


def _desktop(context):
    return context.getServiceManager().createInstanceWithContext(
        "com.sun.star.frame.Desktop", context
    )


def _document(context):
    document = _desktop(context).getCurrentComponent()
    if document is None or not document.supportsService(_CALC_SERVICE):
        raise RuntimeError("Откройте книгу LibreOffice Calc.")
    return document


def _message(context, document, text: str) -> None:
    toolkit = context.getServiceManager().createInstanceWithContext(
        "com.sun.star.awt.Toolkit", context
    )
    parent = document.getCurrentController().getFrame().getContainerWindow()
    box = toolkit.createMessageBox(
        parent,
        uno.Enum("com.sun.star.awt.MessageBoxType", "ERRORBOX"),
        uno.getConstantByName("com.sun.star.awt.MessageBoxButtons.BUTTONS_OK"),
        "Shift-Helper",
        text.replace("\n", "\r\n"),
    )
    box.execute()


def _root() -> Path:
    raw = str(globals().get("__file__", "")).strip()
    if not raw:
        raise RuntimeError("LibreOffice не передал путь установленного расширения.")
    if raw.lower().startswith("file:"):
        raw = uno.fileUrlToSystemPath(raw)
    return Path(raw).resolve().parent


def _load_file(module_name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось создать загрузчик {path.name}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _load_runtime(key: str) -> ModuleType:
    cached = _RUNTIMES.get(key)
    if cached is not None:
        return cached
    module_name, filename = _RUNTIME_FILES[key]
    root = _root()
    scripts = root / "Scripts" / "python"
    pythonpath = scripts / "pythonpath"
    for directory in (pythonpath, scripts):
        value = str(directory)
        if value not in sys.path:
            sys.path.insert(0, value)
    path = scripts / filename
    if not path.is_file():
        raise RuntimeError(f"В расширении отсутствует {filename}.")
    runtime = _load_file(module_name, path)
    if key == "report":
        repairs = _load_file(
            "_shift_helper_extension_report_repairs",
            scripts / "shift_helper_calc.py",
        )
        repairs.patch_report_runtime(runtime)
        from shift_helper.core import exact_report_contract
        from shift_helper.core.exact_migration_contract import (
            install_exact_migration_contract,
        )
        from shift_helper.core.exact_storage_contract import (
            install_exact_storage_contract,
        )

        install_exact_storage_contract(exact_report_contract)
        exact_report_contract.install_exact_report_contract(runtime, root)
        install_exact_migration_contract(exact_report_contract, runtime)
    elif key == "tools":
        from shift_helper.core.exact_tools_contract import install_exact_tools_contract

        install_exact_tools_contract(runtime, root)
    _RUNTIMES[key] = runtime
    return runtime


class _ScriptContext:
    def __init__(self, context, document) -> None:
        self.context = context
        self.desktop = _desktop(context)
        self.document = document

    def getComponentContext(self):  # noqa: N802
        return self.context

    def getDesktop(self):  # noqa: N802
        return self.desktop

    def getDocument(self):  # noqa: N802
        return self.document

    def getInvocationContext(self):  # noqa: N802
        return self.document


def _invoke(context, document, key: str, name: str) -> None:
    runtime = _load_runtime(key)
    runtime.XSCRIPTCONTEXT = _ScriptContext(context, document)
    function = getattr(runtime, name, None)
    if not callable(function):
        raise RuntimeError(f"В ядре Shift-Helper отсутствует функция {name}.")
    function()


class ShiftHelperControls(unohelper.Base, XJobExecutor):
    def __init__(self, context: Any) -> None:
        self.context = context

    def trigger(self, event: str) -> None:
        document = None
        try:
            document = _document(self.context)
            action = str(event).strip().lower()
            if action not in _ACTIONS:
                raise RuntimeError(f"Неизвестная команда Shift-Helper: {event!r}.")
            key, name = _ACTIONS[action]
            _invoke(self.context, document, key, name)
        except Exception as exc:
            if document is not None:
                _message(self.context, document, str(exc))


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    ShiftHelperControls,
    _IMPLEMENTATION_NAME,
    ("com.sun.star.task.Job",),
)
