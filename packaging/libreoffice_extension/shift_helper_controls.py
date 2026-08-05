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
}
_ACTIONS = {
    "enable": ("auto", "enable_automatic_input"),
    "disable": ("auto", "disable_automatic_input"),
    "status": ("auto", "automatic_input_status"),
    "prepare": ("report", "prepare_report_input_sheets"),
    "generation": ("report", "import_generation_from_outlook"),
    "report": ("report", "generate_full_report"),
}
_RUNTIMES: dict[str, ModuleType] = {}


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
    function()


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
