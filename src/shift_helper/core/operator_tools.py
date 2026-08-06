"""Pure helpers for Shift-Helper operator macros migrated from legacy VBA."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

_SPACE_RE = re.compile(r"[\t\r\n\u00a0 ]+")
_CELL_REF_RE = re.compile(
    r"(?<![A-Z0-9_])(?P<col>\$?[A-Z]{1,3})(?P<row>\$?\d+)(?![A-Z0-9_])"
)
_LIMIT_RE = re.compile(r"0[.,]\d{1,2}")
_WTG_RE = re.compile(r"(?:ВЭУ[-\s]*)?(\d{1,3})", re.IGNORECASE)


def normalize_spaces(value: object) -> str:
    """Collapse tabs, line breaks, NBSP and repeated spaces to one space."""

    return _SPACE_RE.sub(" ", str(value or "")).strip()


def merge_nonempty(values: Iterable[object]) -> str:
    """Join non-empty cell values in row-major order with single spaces."""

    return " ".join(text for value in values if (text := normalize_spaces(value)))


def russian_year_word(number: int) -> str:
    """Return the grammatically correct Russian word for a year count."""

    number = abs(int(number))
    last_digit = number % 10
    last_two = number % 100
    if last_digit == 1 and last_two != 11:
        return "год"
    if 2 <= last_digit <= 4 and not 12 <= last_two <= 14:
        return "года"
    return "лет"


def parse_wtg_numbers(
    raw: str,
    *,
    minimum: int = 1,
    maximum: int = 84,
) -> list[int]:
    """Parse comma/semicolon/space separated WTG identifiers without duplicates."""

    tokens = re.split(r"[,;\s]+", str(raw).strip())
    result: list[int] = []
    seen: set[int] = set()
    for token in tokens:
        if not token:
            continue
        match = _WTG_RE.fullmatch(token)
        if match is None:
            raise ValueError(f"Не удалось распознать номер ВЭУ: {token!r}.")
        number = int(match.group(1))
        if number < minimum or number > maximum:
            raise ValueError(
                "Номер ВЭУ должен быть в диапазоне "
                f"{minimum}–{maximum}: {number}."
            )
        if number not in seen:
            result.append(number)
            seen.add(number)
    if not result:
        raise ValueError("Не указаны номера ВЭУ.")
    return result


def maintenance_text(
    wtg_number: int,
    *,
    half_year: bool = False,
    years: int | None = None,
    bolt_torque_check: bool = False,
) -> str:
    """Build the accepted WTG maintenance wording from the legacy macro."""

    number = int(wtg_number)
    if half_year:
        return (
            f"ВЭУ-{number}: базовая платформа, гондола, ступица - "
            "Техническое обслуживание ВЭУ в объеме ТО-6 месяцев "
            "за исключением работ на токоведущих частях в конвертере "
            f"К-1-{number}, конвертере К-2-{number}, ВРУ-0,69, "
            "технический осмотр системы охлаждения конвертера "
            f"К-1-{number} и конвертера К-2-{number} без проникновения "
            "за защитные ограждения."
        )
    if years is None or int(years) <= 0:
        raise ValueError("Количество лет ТО должно быть положительным.")
    years = int(years)
    years_text = f"{years} {russian_year_word(years)}"
    if bolt_torque_check:
        return (
            f"ВЭУ-{number}: базовая платформа, конвертер К-1-{number}, "
            f"конвертер К-2-{number}, ТСН ВЭУ-{number}, ВРУ-0,69 - "
            f"Техническое обслуживание ВЭУ в объеме ТО {years_text}, "
            "проверка моментов затяжки болтовых контактных соединений "
            f"в конвертере К-1-{number}, конвертере К-2-{number}, "
            f"ТСН ВЭУ-{number}, ВРУ-0,69."
        )
    return (
        f"ВЭУ-{number}: базовая платформа, гондола, ступица - "
        f"Техническое обслуживание ВЭУ в объеме ТО {years_text} "
        "за исключением работ на токоведущих частях в конвертере "
        f"К-1-{number}, конвертере К-2-{number}, ВРУ-0,69, "
        "технический осмотр системы охлаждения конвертера "
        f"К-1-{number} и конвертера К-2-{number} без проникновения "
        "за защитные ограждения."
    )


def extract_rotor_limit(text: object) -> float | None:
    """Extract a rotor-speed limitation such as 0,85 from an event description."""

    normalized = str(text or "").lower()
    match = _LIMIT_RE.search(normalized)
    if match is None:
        return None
    return float(match.group(0).replace(",", "."))


def rotor_repair_power(limit_value: float) -> float:
    """Return the accepted P-repair mapping from the VBA beta macro."""

    value = round(float(limit_value), 2)
    if value < 0.7:
        return 2.5
    if value >= 0.95:
        return 0.0
    mapping = {
        0.90: 0.55,
        0.85: 0.75,
        0.80: 1.0,
        0.75: 1.2,
        0.70: 1.4,
    }
    return mapping.get(value, 0.45)


@dataclass(frozen=True, slots=True)
class RotorLimitRecord:
    wtg_number: int
    limit_value: float
    event_time: datetime
    source_text: str


def active_rotor_limits(
    rows: Iterable[tuple[datetime, int, object]],
    *,
    end_time: datetime,
) -> dict[int, RotorLimitRecord]:
    """Resolve active rotor limits at ``end_time`` from chronological log rows."""

    active: dict[int, RotorLimitRecord] = {}
    for event_time, wtg_number, source in sorted(rows, key=lambda row: row[0]):
        if event_time >= end_time:
            continue
        text = str(source or "")
        lowered = text.lower()
        number = int(wtg_number)
        if "снято" in lowered and "огранич" in lowered:
            active.pop(number, None)
            continue
        if (
            "установлено ограничение" in lowered
            and "оборот" in lowered
            and (limit_value := extract_rotor_limit(lowered)) is not None
        ):
            active[number] = RotorLimitRecord(
                wtg_number=number,
                limit_value=limit_value,
                event_time=event_time,
                source_text=text,
            )
    return active


def absolute_a1_references(formula: str) -> str:
    """Make ordinary A1 references absolute before sorting selected rows."""

    source = str(formula or "")
    if not source.startswith("="):
        return source

    def replace(match: re.Match[str]) -> str:
        col = match.group("col").lstrip("$")
        row = match.group("row").lstrip("$")
        # Do not rewrite function-like names such as LOG10(...).
        suffix = source[match.end() :]
        if suffix.lstrip().startswith("("):
            return match.group(0)
        return f"${col}${row}"

    return _CELL_REF_RE.sub(replace, source)


def sort_key_for_time(value: object) -> tuple[int, float | str]:
    """Stable sort key for Calc values from a time column."""

    if value is None or value == "":
        return (2, "")
    if isinstance(value, (int, float)):
        return (0, float(value))
    text = str(value).strip()
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if match:
        hour, minute, second = (int(part or 0) for part in match.groups())
        return (0, hour * 3600 + minute * 60 + second)
    return (1, text.casefold())


def inspection_shift(now: datetime) -> tuple[str, str]:
    """Return legacy day/night shift code and caption."""

    minutes = now.hour * 60 + now.minute
    if 8 * 60 <= minutes < 20 * 60:
        return "Д", "с 08:00 до 20:00"
    return "Н", "с 20:00 до 08:00"


def inspection_message(
    now: datetime,
    assignments: Sequence[tuple[str, str, str | None]],
) -> str:
    """Format the operator message for the KTP inspection schedule."""

    shift, caption = inspection_shift(now)
    weekday_names = (
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
    )
    lines = [
        f"Сегодня ({now:%d.%m.%Y}, {weekday_names[now.weekday()]}, "
        f"смена {shift} {caption}) назначены:"
    ]
    for mk_number, ktp_number, note in assignments:
        line = f"М.К. {mk_number} > КТП {{{ktp_number}}}"
        if note:
            line += f" ({note})"
        lines.append(line)
    return "\n".join(lines)


# WORKSPACE-GRID-REPAIR-002 -------------------------------------------------


def _workspace_empty_grid(rng, uno_module) -> None:
    """Remove all visible cell borders from a Calc range."""

    border = uno_module.createUnoStruct("com.sun.star.table.TableBorder")
    line = uno_module.createUnoStruct("com.sun.star.table.BorderLine")
    line.Color = 0x000000
    line.InnerLineWidth = 0
    line.OuterLineWidth = 0
    line.LineDistance = 0
    for field in (
        "TopLine",
        "BottomLine",
        "LeftLine",
        "RightLine",
        "HorizontalLine",
        "VerticalLine",
    ):
        setattr(border, field, line)
    for field in (
        "IsTopLineValid",
        "IsBottomLineValid",
        "IsLeftLineValid",
        "IsRightLineValid",
        "IsHorizontalLineValid",
        "IsVerticalLineValid",
    ):
        setattr(border, field, True)
    rng.setPropertyValue("TableBorder", border)


def _workspace_black_grid(rng, uno_module) -> None:
    """Apply a compact black grid matching the accepted report worksheets."""

    border = uno_module.createUnoStruct("com.sun.star.table.TableBorder")
    line = uno_module.createUnoStruct("com.sun.star.table.BorderLine")
    line.Color = 0x000000
    line.InnerLineWidth = 0
    line.OuterLineWidth = 18
    line.LineDistance = 0
    for field in (
        "TopLine",
        "BottomLine",
        "LeftLine",
        "RightLine",
        "HorizontalLine",
        "VerticalLine",
    ):
        setattr(border, field, line)
    for field in (
        "IsTopLineValid",
        "IsBottomLineValid",
        "IsLeftLineValid",
        "IsRightLineValid",
        "IsHorizontalLineValid",
        "IsVerticalLineValid",
    ):
        setattr(border, field, True)
    rng.setPropertyValue("TableBorder", border)


def _workspace_cell_is_meaningful(cell, *, ignore_formula: bool = False) -> bool:
    formula = str(cell.getFormula())
    if formula.startswith("="):
        return not ignore_formula
    if str(cell.getString()).strip():
        return True
    try:
        return float(cell.getValue()) != 0.0
    except Exception:
        return False


def _workspace_last_meaningful_row(
    sheet,
    column_count: int,
    ignored_formula_columns: tuple[int, ...] = (),
) -> int:
    cursor = sheet.createCursor()
    cursor.gotoEndOfUsedArea(True)
    end = max(int(cursor.getRangeAddress().EndRow), 1)
    for row in range(end, 0, -1):
        for column in range(column_count):
            if _workspace_cell_is_meaningful(
                sheet.getCellByPosition(column, row),
                ignore_formula=column in ignored_formula_columns,
            ):
                return row
    return 0


def _workspace_compact_table(
    runtime,
    sheet,
    column_count: int,
    ignored_formula_columns: tuple[int, ...] = (),
    minimum_scan_end: int = 200,
) -> int:
    import uno

    used_end = max(runtime._last_used_row(sheet), minimum_scan_end, 1)
    last_data = _workspace_last_meaningful_row(
        sheet,
        column_count,
        ignored_formula_columns,
    )
    visible_end = max(1, last_data + (1 if last_data else 0))

    whole = sheet.getCellRangeByPosition(0, 1, column_count - 1, used_end)
    _workspace_empty_grid(whole, uno)
    whole.setPropertyValue("CellBackColor", runtime.WHITE)

    visible = sheet.getCellRangeByPosition(0, 0, column_count - 1, visible_end)
    visible.setPropertyValue("IsTextWrapped", True)
    _workspace_black_grid(visible, uno)
    data = sheet.getCellRangeByPosition(0, 1, column_count - 1, visible_end)
    data.setPropertyValue("CellBackColor", runtime.INPUT_FILL)
    try:
        sheet.getRows().getByIndex(visible_end).Height = 620
    except Exception:
        pass
    return visible_end


def _workspace_repair_grids(runtime, document) -> None:
    """Restrict borders to actual data plus one operator input row."""

    import uno

    sheets = document.getSheets()
    specs = (
        (runtime.INPUT_COMMANDS, 6, ()),
        (runtime.INPUT_VIOLATIONS, 6, ()),
        (runtime.INPUT_WORKS, 11, (5,)),
        (runtime.INPUT_DEFECTS, 10, ()),
    )
    for name, columns, ignored in specs:
        if not sheets.hasByName(name):
            continue
        _workspace_compact_table(
            runtime,
            sheets.getByName(name),
            columns,
            ignored,
        )

    if sheets.hasByName(runtime.INPUT_STATE):
        state = sheets.getByName(runtime.INPUT_STATE)
        state_end = max(runtime._last_used_row(state), 84)
        _workspace_empty_grid(
            state.getCellRangeByPosition(0, 0, 10, state_end),
            uno,
        )
        _workspace_black_grid(
            state.getCellRangeByPosition(0, 0, 10, 84),
            uno,
        )

    if sheets.hasByName(runtime.INPUT_WORKS):
        works = sheets.getByName(runtime.INPUT_WORKS)
        for row in range(1, 201):
            excel_row = row + 1
            works.getCellByPosition(5, row).setFormula(
                f'=IF(COUNTA(D{excel_row}:E{excel_row})=0;"";'
                f'MAX(D{excel_row}-E{excel_row};0))'
            )


def _workspace_install_calendar_button(runtime, document) -> None:
    """Install an idempotent calendar button beside preparation-cell B3."""

    import uno

    sheets = document.getSheets()
    if not sheets.hasByName(runtime.INPUT_PREP):
        return
    sheet = sheets.getByName(runtime.INPUT_PREP)
    draw_page = sheet.getDrawPage()
    forms = draw_page.getForms()
    form_name = "ShiftHelperControls"
    if forms.hasByName(form_name):
        form = forms.getByName(form_name)
    else:
        form = document.createInstance("com.sun.star.form.component.Form")
        form.setPropertyValue("Name", form_name)
        forms.insertByName(form_name, form)

    button_name = "ShiftHelperReportDateCalendar"
    if form.hasByName(button_name):
        model = form.getByName(button_name)
    else:
        model = document.createInstance(
            "com.sun.star.form.component.CommandButton"
        )
        model.setPropertyValue("Name", button_name)
        form.insertByName(button_name, model)
    model.setPropertyValue("Label", "Календарь…")
    model.setPropertyValue(
        "ButtonType",
        uno.Enum("com.sun.star.form.FormButtonType", "URL"),
    )
    model.setPropertyValue(
        "TargetURL",
        "service:ru.kves.shifthelper.calc.controls?calendarprep",
    )
    model.setPropertyValue("TargetFrame", "_self")
    try:
        model.setPropertyValue("HelpText", "Выбрать дату рапорта в B3")
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

    anchor = sheet.getCellByPosition(2, 2)
    point = uno.createUnoStruct("com.sun.star.awt.Point")
    point.X = int(anchor.Position.X) + 120
    point.Y = int(anchor.Position.Y) + 40
    size = uno.createUnoStruct("com.sun.star.awt.Size")
    size.Width = 4300
    size.Height = max(int(anchor.Size.Height) - 80, 650)
    shape.setPosition(point)
    shape.setSize(size)
    runtime._set_col_width(sheet, 2, 4700)


def install_calc_workspace_repairs(runtime) -> None:
    """Patch the integrated report runtime with compact workspace UI repairs."""

    if getattr(runtime, "_WORKSPACE_GRID_REPAIR_002_APPLIED", False):
        return
    original_prepare = runtime.prepare_report_input_sheets

    def prepare_report_input_sheets(_args=None) -> None:
        original_prepare(_args)
        document = runtime._document()
        _workspace_repair_grids(runtime, document)
        _workspace_install_calendar_button(runtime, document)

    runtime.prepare_report_input_sheets = prepare_report_input_sheets
    runtime._WORKSPACE_GRID_REPAIR_002_APPLIED = True
