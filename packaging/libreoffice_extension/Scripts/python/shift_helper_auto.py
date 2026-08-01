"""Automatic quick-input integration for LibreOffice Calc."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any

import uno
import unohelper
from com.sun.star.awt import XCallback
from com.sun.star.frame import XDispatch, XDispatchProviderInterceptor, XInterceptorInfo
from com.sun.star.util import XModifyListener
from com.sun.star.view import XSelectionChangeListener

from shift_helper.uno_adapter.calc_selection import (
    SelectionPlan,
    plan_date_selection,
    plan_time_selection,
)

XSCRIPTCONTEXT: Any = globals().get("XSCRIPTCONTEXT")

_VERSION = "0.3.0.dev5"
_SHEET_NAME = "ЖС"
_TEXT_FORMAT = "@"
_DATE_FORMAT = "DD.MM.YYYY"
_TIME_FORMAT = "HH:MM"
_BUFFER_ROWS = 256
_DATE_COLUMNS = frozenset({1, 8})
_TIME_COLUMNS = frozenset({2, 9})
_SUPPORTED_COLUMNS = _DATE_COLUMNS | _TIME_COLUMNS
_PASTE_URL = ".uno:Paste"
_SESSION: AutomaticInputSession | None = None


def _document():
    if XSCRIPTCONTEXT is None:
        raise RuntimeError("Макрос запущен вне LibreOffice.")
    document = XSCRIPTCONTEXT.getDocument()
    if document is None or not document.supportsService(
        "com.sun.star.sheet.SpreadsheetDocument"
    ):
        raise RuntimeError("Откройте книгу LibreOffice Calc.")
    return document


def _sheet(document):
    sheet = document.getCurrentController().getActiveSheet()
    if sheet.getName() != _SHEET_NAME:
        raise RuntimeError(f"Откройте лист «{_SHEET_NAME}».")
    return sheet


def _message(text: str, *, error: bool = False) -> None:
    context = XSCRIPTCONTEXT.getComponentContext()
    toolkit = context.getServiceManager().createInstanceWithContext(
        "com.sun.star.awt.Toolkit", context
    )
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


def _address(document):
    selection = document.getCurrentController().getSelection()
    getter = getattr(selection, "getRangeAddress", None)
    if callable(getter):
        return getter()
    raise RuntimeError("Выделите один непрерывный диапазон.")


def _kind(cell) -> str:
    value = cell.getType()
    return str(getattr(value, "value", value)).upper()


def _is_empty(cell) -> bool:
    return "EMPTY" in _kind(cell) and not cell.getString() and not cell.getFormula()


def _is_text(cell) -> bool:
    return "TEXT" in _kind(cell) and bool(cell.getString().strip())


def _is_formula(cell) -> bool:
    return "FORMULA" in _kind(cell) or cell.getFormula().startswith("=")


def _null_date(document) -> date:
    value = document.getNumberFormatSettings().getPropertyValue("NullDate")
    return date(int(value.Year), int(value.Month), int(value.Day))


def _numeric_date(cell, null_date: date) -> date | None:
    if _is_formula(cell) or "VALUE" not in _kind(cell) or not cell.getString().strip():
        return None
    return null_date + timedelta(days=int(cell.getValue()))


def _numeric_time(cell) -> time | None:
    if _is_formula(cell) or "VALUE" not in _kind(cell) or not cell.getString().strip():
        return None
    minutes = int(round((cell.getValue() % 1.0) * 24 * 60)) % (24 * 60)
    return time(minutes // 60, minutes % 60)


def _format_key(document, cell, code: str) -> int:
    formats = document.getNumberFormats()
    locale = cell.getPropertyValue("CharLocale")
    key = formats.queryKey(code, locale, True)
    return formats.addNew(code, locale) if key == -1 else key


def _write_one(document, sheet, write) -> None:
    cell = sheet.getCellByPosition(write.column, write.row)
    if write.kind == "date":
        cell.setValue(float((write.value - _null_date(document)).days))
        cell.setPropertyValue(
            "NumberFormat", _format_key(document, cell, _DATE_FORMAT)
        )
        return
    seconds = write.value.hour * 3600 + write.value.minute * 60
    cell.setValue(seconds / 86400.0)
    cell.setPropertyValue("NumberFormat", _format_key(document, cell, _TIME_FORMAT))


def _write_plan(document, sheet, plan: SelectionPlan) -> None:
    if not plan.writes:
        return
    undo = None
    opened = False
    document.lockControllers()
    try:
        try:
            undo = document.getUndoManager()
            undo.enterHiddenUndoContext()
            opened = True
        except Exception:
            undo = None
        for write in plan.writes:
            _write_one(document, sheet, write)
    finally:
        if undo is not None and opened:
            try:
                undo.leaveUndoContext()
            except Exception:
                pass
        document.unlockControllers()


def _groups(rows: list[int]) -> list[tuple[int, int]]:
    ordered = sorted(set(rows))
    if not ordered:
        return []
    result: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for row in ordered[1:]:
        if row != previous + 1:
            result.append((start, previous))
            start = row
        previous = row
    result.append((start, previous))
    return result


def _column_name(column: int) -> str:
    return {1: "B", 2: "C", 8: "I", 9: "J"}.get(column, str(column + 1))


def _clipboard_text() -> str | None:
    context = XSCRIPTCONTEXT.getComponentContext()
    manager = context.getServiceManager()
    clipboard = manager.createInstanceWithContext(
        "com.sun.star.datatransfer.clipboard.SystemClipboard",
        context,
    )
    if clipboard is None:
        return None
    transferable = clipboard.getContents()
    if transferable is None:
        return None

    flavors = tuple(transferable.getTransferDataFlavors())
    ordered = sorted(
        flavors,
        key=lambda flavor: (
            0 if "charset=utf-16" in str(flavor.MimeType).lower() else 1,
            str(flavor.MimeType).lower(),
        ),
    )
    for flavor in ordered:
        mime = str(flavor.MimeType).lower()
        if not mime.startswith("text/plain"):
            continue
        try:
            data = transferable.getTransferData(flavor)
        except Exception:
            continue
        if isinstance(data, str):
            return data.rstrip("\x00")
        value = getattr(data, "value", data)
        if isinstance(value, (bytes, bytearray, memoryview)):
            encoding = "utf-16" if "utf-16" in mime else "utf-8"
            try:
                return bytes(value).decode(encoding).rstrip("\x00")
            except UnicodeError:
                continue
    return None


def _single_clipboard_column(text: str) -> list[str] | None:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\x00")
    while normalized.endswith("\n"):
        normalized = normalized[:-1]
    if not normalized:
        return []
    rows = normalized.split("\n")
    if any("\t" in row for row in rows):
        return None
    if len(rows) > _BUFFER_ROWS:
        raise RuntimeError(
            f"За одну операцию поддерживается не более {_BUFFER_ROWS} строк."
        )
    return rows


class PasteDispatchInterceptor(
    unohelper.Base,
    XDispatchProviderInterceptor,
    XInterceptorInfo,
    XDispatch,
):
    """Intercept .uno:Paste before Calc performs clipboard type inference."""

    def __init__(self, session: AutomaticInputSession) -> None:
        self.session = session
        self.master = None
        self.slave = None

    def getInterceptedURLs(self):  # noqa: N802
        return (_PASTE_URL,)

    def getMasterDispatchProvider(self):  # noqa: N802
        return self.master

    def setMasterDispatchProvider(self, provider) -> None:  # noqa: N802
        self.master = provider

    def getSlaveDispatchProvider(self):  # noqa: N802
        return self.slave

    def setSlaveDispatchProvider(self, provider) -> None:  # noqa: N802
        self.slave = provider

    def queryDispatch(self, url, target_frame_name, search_flags):  # noqa: N802
        if str(getattr(url, "Complete", "")) == _PASTE_URL:
            return self
        if self.slave is None:
            return None
        return self.slave.queryDispatch(url, target_frame_name, search_flags)

    def queryDispatches(self, requests):  # noqa: N802
        return tuple(
            self.queryDispatch(
                request.FeatureURL,
                request.FrameName,
                request.SearchFlags,
            )
            for request in requests
        )

    def dispatch(self, url, arguments) -> None:
        if (
            str(getattr(url, "Complete", "")) == _PASTE_URL
            and self.session.try_paste_from_clipboard()
        ):
            return
        delegate = self._delegate(url)
        if delegate is not None:
            delegate.dispatch(url, arguments)

    def addStatusListener(self, listener, url) -> None:  # noqa: N802
        delegate = self._delegate(url)
        if delegate is not None:
            delegate.addStatusListener(listener, url)

    def removeStatusListener(self, listener, url) -> None:  # noqa: N802
        delegate = self._delegate(url)
        if delegate is not None:
            delegate.removeStatusListener(listener, url)

    def _delegate(self, url):
        if self.slave is None:
            return None
        return self.slave.queryDispatch(url, "", 0)


class AutomaticInputSession(
    unohelper.Base,
    XSelectionChangeListener,
    XModifyListener,
    XCallback,
):
    """Preserve raw tokens, normalize ordinary input and intercept paste dispatches."""

    def __init__(self, document) -> None:
        self.document = document
        self.controller = document.getCurrentController()
        self.frame = self.controller.getFrame()
        self.sheet = _sheet(document)
        self.prepared: dict[tuple[int, int], int] = {}
        self.invalid: dict[tuple[int, int], str] = {}
        self.guard = False
        self.enabled = True
        self.callback_pending = False
        self.change_revision = 0
        self.confirmed_revision = -1

        context = XSCRIPTCONTEXT.getComponentContext()
        manager = context.getServiceManager()
        self.async_callback = manager.createInstanceWithContext(
            "com.sun.star.awt.AsyncCallback", context
        )
        if self.async_callback is None or not hasattr(
            self.async_callback, "addCallback"
        ):
            raise RuntimeError("LibreOffice не предоставил сервис AsyncCallback.")

        self.paste_interceptor = PasteDispatchInterceptor(self)
        if not hasattr(self.frame, "registerDispatchProviderInterceptor"):
            raise RuntimeError(
                "Окно LibreOffice не поддерживает перехват команд Dispatch."
            )

        self.controller.addSelectionChangeListener(self)
        self.document.addModifyListener(self)
        self.frame.registerDispatchProviderInterceptor(self.paste_interceptor)
        self.prepare()

    def selectionChanged(self, _event) -> None:  # noqa: N802
        if self.enabled and not self.guard:
            self.prepare()
            self.request_normalize()

    def modified(self, _event) -> None:
        if self.enabled and not self.guard:
            self.request_normalize()

    def notify(self, data) -> None:
        self.callback_pending = False
        if not self.enabled or self.guard:
            return
        try:
            scheduled_revision = int(data)
        except (TypeError, ValueError):
            scheduled_revision = -1
        if scheduled_revision != self.change_revision:
            self._enqueue_callback()
            return
        if self.confirmed_revision != self.change_revision:
            self.confirmed_revision = self.change_revision
            self._enqueue_callback()
            return
        self.confirmed_revision = -1
        self.normalize()
        self.prepare()

    def disposing(self, _event) -> None:
        self.detach(restore=False)

    def request_normalize(self) -> None:
        self.change_revision += 1
        self.confirmed_revision = -1
        self._enqueue_callback()

    def _enqueue_callback(self) -> None:
        if self.callback_pending or not self.enabled:
            return
        self.callback_pending = True
        try:
            self.async_callback.addCallback(self, self.change_revision)
        except Exception:
            self.callback_pending = False
            raise

    def _paste_target(self) -> tuple[int, int] | None:
        if self.controller.getActiveSheet().getName() != _SHEET_NAME:
            return None
        try:
            address = _address(self.document)
        except RuntimeError:
            return None
        if (
            address.StartColumn != address.EndColumn
            or address.StartRow != address.EndRow
        ):
            return None
        column = int(address.StartColumn)
        row = int(address.StartRow)
        if column not in _SUPPORTED_COLUMNS or row < 1:
            return None
        return column, row

    def try_paste_from_clipboard(self) -> bool:
        if not self.enabled or self.guard:
            return False
        target = self._paste_target()
        if target is None:
            return False
        text = _clipboard_text()
        if text is None:
            return False
        try:
            values = _single_clipboard_column(text)
        except RuntimeError as exc:
            _message(str(exc), error=True)
            return True
        if values is None:
            return False
        if not values:
            return True
        column, start = target
        try:
            self._paste_column(column, start, values)
        except Exception as exc:
            _message(f"Не удалось обработать вставку: {exc}", error=True)
        return True

    def _paste_column(self, column: int, start: int, values: list[str]) -> None:
        last_row = start + len(values) - 1
        if last_row >= self.sheet.getRows().getCount():
            raise RuntimeError("Вставка выходит за пределы листа.")
        occupied = [
            row
            for row in range(start, last_row + 1)
            if not _is_empty(self.sheet.getCellByPosition(column, row))
        ]
        if occupied:
            first = occupied[0] + 1
            raise RuntimeError(
                "Массовая вставка Shift-Helper разрешена только в пустые ячейки. "
                f"Первая занятая строка: {first}."
            )

        undo = None
        opened = False
        self.guard = True
        self.document.lockControllers()
        try:
            try:
                undo = self.document.getUndoManager()
                undo.enterUndoContext("Shift-Helper: массовая вставка")
                opened = True
            except Exception:
                undo = None

            for offset, raw in enumerate(values):
                row = start + offset
                key = (column, row)
                cell = self.sheet.getCellByPosition(column, row)
                if key not in self.prepared:
                    self.prepared[key] = int(cell.getPropertyValue("NumberFormat"))
                cell.setPropertyValue(
                    "NumberFormat",
                    _format_key(self.document, cell, _TEXT_FORMAT),
                )
                cell.setString(raw)

            plan = self._plan_values(column, start, values)
            for write in plan.writes:
                _write_one(self.document, self.sheet, write)
                self.prepared.pop((write.column, write.row), None)
                self.invalid.pop((write.column, write.row), None)

            target_range = self.sheet.getCellRangeByPosition(
                column, start, column, last_row
            )
            self.controller.select(target_range)
        finally:
            if undo is not None and opened:
                try:
                    undo.leaveUndoContext()
                except Exception:
                    pass
            self.document.unlockControllers()
            self.guard = False

        self._report_plans([plan])
        self.prepare()

    def prepare(self) -> None:
        if self.controller.getActiveSheet().getName() != _SHEET_NAME:
            return
        try:
            address = _address(self.document)
        except RuntimeError:
            return
        if address.StartColumn != address.EndColumn:
            return
        column = int(address.StartColumn)
        if column not in _SUPPORTED_COLUMNS or address.EndRow < 1:
            return
        start = max(1, int(address.StartRow))
        last = self.sheet.getRows().getCount() - 1
        end = min(last, int(address.EndRow) + _BUFFER_ROWS)
        was_modified = bool(self.document.isModified())
        undo = None
        self.guard = True
        self.document.lockControllers()
        try:
            try:
                undo = self.document.getUndoManager()
                undo.lock()
            except Exception:
                undo = None
            for row in range(start, end + 1):
                key = (column, row)
                if key in self.prepared:
                    continue
                cell = self.sheet.getCellByPosition(column, row)
                if not _is_empty(cell):
                    continue
                self.prepared[key] = int(cell.getPropertyValue("NumberFormat"))
                cell.setPropertyValue(
                    "NumberFormat",
                    _format_key(self.document, cell, _TEXT_FORMAT),
                )
        finally:
            if undo is not None:
                try:
                    undo.unlock()
                except Exception:
                    pass
            self.document.unlockControllers()
            try:
                self.document.setModified(was_modified)
            except Exception:
                pass
            self.guard = False

    def normalize(self) -> None:
        by_column: dict[int, list[int]] = defaultdict(list)
        for column, row in tuple(self.prepared):
            cell = self.sheet.getCellByPosition(column, row)
            if _is_text(cell):
                by_column[column].append(row)
            elif not _is_empty(cell):
                self.prepared.pop((column, row), None)
                self.invalid.pop((column, row), None)
        if not by_column:
            return

        plans: list[SelectionPlan] = []
        self.guard = True
        try:
            for column, rows in by_column.items():
                for start, end in _groups(rows):
                    plan = self._plan(column, start, end)
                    _write_plan(self.document, self.sheet, plan)
                    plans.append(plan)
                    for write in plan.writes:
                        self.prepared.pop((write.column, write.row), None)
                        self.invalid.pop((write.column, write.row), None)
        finally:
            self.guard = False

        self._report_plans(plans)

    def _report_plans(self, plans: list[SelectionPlan]) -> None:
        fresh: list[str] = []
        has_error = False
        for plan in plans:
            has_error = has_error or bool(plan.errors)
            for issue in plan.issues:
                key = (issue.column, issue.row)
                token = self.sheet.getCellByPosition(*key).getString().strip()
                if self.invalid.get(key) == token:
                    continue
                self.invalid[key] = token
                fresh.append(
                    f"{_column_name(issue.column)}{issue.row + 1}: {issue.message}"
                )
        if fresh:
            _message("\n".join(fresh[:10]), error=has_error)

    def _plan(self, column: int, start: int, end: int) -> SelectionPlan:
        raw = [
            self.sheet.getCellByPosition(column, row).getString().strip()
            for row in range(start, end + 1)
        ]
        return self._plan_values(column, start, raw)

    def _plan_values(
        self, column: int, start: int, raw: list[object]
    ) -> SelectionPlan:
        null_date = _null_date(self.document)
        if column in _DATE_COLUMNS:
            previous = None
            if start > 1:
                previous = _numeric_date(
                    self.sheet.getCellByPosition(column, start - 1),
                    null_date,
                )
            return plan_date_selection(
                start_row=start,
                column=column,
                raw_values=raw,
                previous_above=previous,
                today=date.today(),
            )

        previous_time = None
        if start > 1:
            previous_time = _numeric_time(
                self.sheet.getCellByPosition(column, start - 1)
            )
        paired_column = 1 if column == 2 else 8
        paired_dates = [
            _numeric_date(
                self.sheet.getCellByPosition(paired_column, row),
                null_date,
            )
            for row in range(start, start + len(raw))
        ]
        return plan_time_selection(
            start_row=start,
            column=column,
            raw_values=raw,
            previous_above=previous_time,
            paired_dates=paired_dates,
            now=datetime.now(),
        )

    def detach(self, *, restore: bool = True) -> None:
        if not self.enabled:
            return
        self.enabled = False
        try:
            self.controller.removeSelectionChangeListener(self)
        except Exception:
            pass
        try:
            self.document.removeModifyListener(self)
        except Exception:
            pass
        try:
            self.frame.releaseDispatchProviderInterceptor(self.paste_interceptor)
        except Exception:
            pass
        if not restore:
            return

        was_modified = bool(self.document.isModified())
        undo = None
        self.guard = True
        self.document.lockControllers()
        try:
            try:
                undo = self.document.getUndoManager()
                undo.lock()
            except Exception:
                undo = None
            for key, original_format in tuple(self.prepared.items()):
                cell = self.sheet.getCellByPosition(*key)
                if _is_empty(cell):
                    cell.setPropertyValue("NumberFormat", original_format)
        finally:
            if undo is not None:
                try:
                    undo.unlock()
                except Exception:
                    pass
            self.document.unlockControllers()
            try:
                self.document.setModified(was_modified)
            except Exception:
                pass
            self.guard = False
        self.prepared.clear()
        self.invalid.clear()


def enable_automatic_input(_args=None) -> None:
    global _SESSION
    try:
        document = _document()
        _sheet(document)
        if _SESSION is not None and _SESSION.enabled:
            _SESSION.detach()
        _SESSION = AutomaticInputSession(document)
        _message(
            f"Автоматический ввод {_VERSION} включён.\n"
            "Столбцы: B, C, I, J.\n"
            "Команда .uno:Paste перехватывается до обработки Calc."
        )
    except Exception as exc:
        _SESSION = None
        _message(f"Не удалось включить автоматический ввод: {exc}", error=True)


def disable_automatic_input(_args=None) -> None:
    global _SESSION
    if _SESSION is None or not _SESSION.enabled:
        _message("Автоматический ввод уже выключен.")
        return
    try:
        _SESSION.detach()
        _SESSION = None
        _message("Автоматический ввод выключен; пустые ячейки восстановлены.")
    except Exception as exc:
        _message(f"Не удалось выключить автоматический ввод: {exc}", error=True)


def automatic_input_status(_args=None) -> None:
    if _SESSION is None or not _SESSION.enabled:
        _message(f"Версия {_VERSION}. Автоматический ввод выключен.")
        return
    _message(
        f"Версия {_VERSION}. Автоматический ввод включён.\n"
        f"Подготовлено пустых ячеек: {len(_SESSION.prepared)}.\n"
        "Перехват .uno:Paste: включён."
    )


g_exportedScripts = (
    enable_automatic_input,
    disable_automatic_input,
    automatic_input_status,
)
