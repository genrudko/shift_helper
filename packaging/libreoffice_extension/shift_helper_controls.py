"""UNO component exposing Shift-Helper controls to LibreOffice Calc UI."""

from __future__ import annotations

from typing import Any

import uno
import unohelper
from com.sun.star.task import XJobExecutor

_IMPLEMENTATION_NAME = "ru.kves.shifthelper.calc.controls"
_CALC_SERVICE = "com.sun.star.sheet.SpreadsheetDocument"
_ACTIONS = {
    "enable": "enable_automatic_input",
    "disable": "disable_automatic_input",
    "status": "automatic_input_status",
}
_SCRIPT_LOCATIONS = ("user", "share")


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


def _script_provider(context):
    factory = context.getServiceManager().createInstanceWithContext(
        "com.sun.star.script.provider.MasterScriptProviderFactory",
        context,
    )
    return factory.createScriptProvider("")


def _invoke_operator_macro(context, function_name: str) -> None:
    provider = _script_provider(context)
    failures: list[str] = []
    for location in _SCRIPT_LOCATIONS:
        uri = (
            f"vnd.sun.star.script:shift_helper_auto.py${function_name}"
            f"?language=Python&location={location}"
        )
        try:
            script = provider.getScript(uri)
            script.invoke((), (), ())
            return
        except Exception as exc:  # UNO exceptions vary by LibreOffice build.
            failures.append(f"{location}: {exc}")
    raise RuntimeError(
        "Не удалось найти установленный Python-макрос Shift-Helper. "
        + " | ".join(failures)
    )


class ShiftHelperControls(unohelper.Base, XJobExecutor):
    """Dispatch UI actions from Addons.xcu to the accepted Python macros."""

    def __init__(self, context: Any) -> None:
        self.context = context

    def trigger(self, event: str) -> None:
        document = None
        try:
            document = _current_calc(self.context)
            action = str(event).strip().lower()
            function_name = _ACTIONS.get(action)
            if function_name is None:
                raise RuntimeError(f"Неизвестная команда Shift-Helper: {event!r}.")
            _invoke_operator_macro(self.context, function_name)
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
