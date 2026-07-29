"""Atomic derived .xlsx mirror for the operational event journal."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from threading import Lock

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .domain import EVENT_TYPE_CHOICES
from .models import Event

EVENT_MIRROR_FILENAME = "Журнал событий.xlsx"
EVENT_MIRROR_SHEET = "Журнал событий"
EVENT_MIRROR_META_SHEET = "_shift_helper_meta"
EVENT_MIRROR_SCHEMA_VERSION = 1
_WRITE_LOCK = Lock()
_EVENT_TYPE_LABELS = dict(EVENT_TYPE_CHOICES)

_HEADERS: tuple[str, ...] = (
    "№",
    "Дата",
    "Время",
    "Оборудование",
    "Тип события",
    "Описание",
    "Причина",
    "Принятые меры",
    "Исполнитель",
    "Код ошибки",
    "Ограничение",
    "P ремонт, МВт",
    "Состояние",
    "Окончание",
    "В утренний рапорт",
)
_COLUMN_WIDTHS: tuple[float, ...] = (
    7,
    13,
    10,
    22,
    22,
    42,
    34,
    36,
    24,
    16,
    15,
    17,
    15,
    20,
    18,
)


@dataclass(frozen=True, slots=True)
class EventMirrorResult:
    path: Path
    pending_path: Path
    generated_at: datetime
    record_count: int


class EventMirrorWriteError(RuntimeError):
    """Raised when a valid candidate cannot replace the public mirror file."""

    def __init__(self, target: Path, pending: Path, cause: OSError) -> None:
        super().__init__(
            f"Не удалось обновить {target.name}; закройте файл в Excel и повторите операцию."
        )
        self.target = target
        self.pending = pending
        self.__cause__ = cause


def _decimal_value(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _event_row(event: Event, visual_index: int) -> list[object]:
    return [
        visual_index,
        event.start_at.date(),
        event.start_at.time().replace(second=0, microsecond=0),
        event.asset_label,
        _EVENT_TYPE_LABELS.get(event.event_type, event.event_type),
        event.description,
        event.reason,
        event.actions,
        event.performer,
        event.error_codes,
        _decimal_value(event.rotor_limit),
        _decimal_value(event.repair_power_mw),
        "Открыто" if event.status == "open" else "Завершено",
        event.end_at,
        "Да" if event.include_in_report else "Нет",
    ]


def _style_workbook(workbook: Workbook, events: list[Event], generated_at: datetime) -> None:
    sheet = workbook.active
    if sheet is None:
        raise RuntimeError("Не удалось создать лист зеркала журнала событий.")
    sheet.title = EVENT_MIRROR_SHEET
    sheet.append(list(_HEADERS))

    for visual_index, event in enumerate(events, start=1):
        sheet.append(_event_row(event, visual_index))

    header_fill = PatternFill("solid", fgColor="D9E5F6")
    header_font = Font(name="Arial", size=10, bold=True, color="172033")
    body_font = Font(name="Arial", size=10, color="172033")
    thin_side = Side(style="thin", color="CDD5DF")
    body_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = body_border
    sheet.row_dimensions[1].height = 30

    for row_index in range(2, sheet.max_row + 1):
        sheet.row_dimensions[row_index].height = 24
        status_cell = sheet.cell(row=row_index, column=13)
        if status_cell.value == "Завершено":
            status_cell.fill = PatternFill("solid", fgColor="DCFCE7")
        else:
            status_cell.fill = PatternFill("solid", fgColor="FEF3C7")

        for column_index in range(1, len(_HEADERS) + 1):
            cell = sheet.cell(row=row_index, column=column_index)
            cell.font = body_font
            cell.border = body_border
            cell.alignment = Alignment(vertical="top", wrap_text=True)

        for column_index in (1, 2, 3, 11, 12, 13, 14, 15):
            sheet.cell(row=row_index, column=column_index).alignment = Alignment(
                horizontal="center",
                vertical="top",
                wrap_text=True,
            )

        sheet.cell(row=row_index, column=2).number_format = "dd.mm.yyyy"
        sheet.cell(row=row_index, column=3).number_format = "hh:mm"
        sheet.cell(row=row_index, column=11).number_format = "0.00"
        sheet.cell(row=row_index, column=12).number_format = "0.00"
        sheet.cell(row=row_index, column=14).number_format = "dd.mm.yyyy hh:mm"

    for column_index, width in enumerate(_COLUMN_WIDTHS, start=1):
        sheet.column_dimensions[sheet.cell(row=1, column=column_index).column_letter].width = width

    last_row = max(1, sheet.max_row)
    sheet.freeze_panes = "D2"
    sheet.auto_filter.ref = f"A1:O{last_row}"
    sheet.print_title_rows = "1:1"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_view.showGridLines = True

    meta = workbook.create_sheet(EVENT_MIRROR_META_SHEET)
    meta.sheet_state = "hidden"
    meta.append(["schemaVersion", EVENT_MIRROR_SCHEMA_VERSION])
    meta.append(["generatedAt", generated_at.isoformat(timespec="seconds")])
    meta.append(["source", "SQLite"])
    meta.append([])
    meta.append(["row", "id", "revision", "updatedAt"])
    for visual_index, event in enumerate(events, start=1):
        meta.append(
            [
                visual_index,
                event.id,
                event.revision,
                event.updated_at.isoformat(timespec="seconds"),
            ]
        )

    workbook.properties.title = "Журнал событий Shift-Helper"
    workbook.properties.subject = "Совместимая экспортная копия данных SQLite"
    workbook.properties.creator = "Shift-Helper"
    workbook.properties.modified = generated_at


def refresh_event_journal_mirror(engine: Engine, exports_directory: Path) -> EventMirrorResult:
    """Rebuild and atomically publish the event-journal compatibility mirror."""

    exports_directory.mkdir(parents=True, exist_ok=True)
    target = exports_directory / EVENT_MIRROR_FILENAME
    pending = exports_directory / f".{EVENT_MIRROR_FILENAME}.pending.xlsx"
    generated_at = datetime.now().replace(microsecond=0)

    with _WRITE_LOCK:
        statement = select(Event).order_by(Event.start_at.asc(), Event.id.asc())
        with Session(engine) as session:
            events = list(session.scalars(statement))
            workbook = Workbook()
            _style_workbook(workbook, events, generated_at)
            workbook.save(pending)

        verifier = load_workbook(pending, read_only=True, data_only=False)
        try:
            if EVENT_MIRROR_SHEET not in verifier.sheetnames:
                raise RuntimeError("Проверка зеркала не нашла основной лист журнала событий.")
            if EVENT_MIRROR_META_SHEET not in verifier.sheetnames:
                raise RuntimeError("Проверка зеркала не нашла лист служебных метаданных.")
        finally:
            verifier.close()

        try:
            os.replace(pending, target)
        except OSError as exc:
            raise EventMirrorWriteError(target, pending, exc) from exc

    return EventMirrorResult(
        path=target,
        pending_path=pending,
        generated_at=generated_at,
        record_count=len(events),
    )
