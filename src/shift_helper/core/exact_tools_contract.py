"""Operator-tool coordinate repairs for the exact report-form workbook."""

from __future__ import annotations

import re
from datetime import datetime, time
from pathlib import Path
from typing import Any


def _update_rotor(runtime: Any, _args=None) -> None:
    try:
        document = runtime._document()
        sheets = document.getSheets()
        if not sheets.hasByName(runtime.JOURNAL_SHEET):
            raise RuntimeError(f"Отсутствует лист «{runtime.JOURNAL_SHEET}».")
        if not sheets.hasByName(runtime.INPUT_STATE):
            raise RuntimeError(
                "Сначала выполните «Подготовить полный контур рапорта»: "
                f"отсутствует лист «{runtime.INPUT_STATE}»."
            )

        report_date = runtime._report_date(document)
        end_time = datetime.combine(report_date, time(7, 0))
        source = sheets.getByName(runtime.JOURNAL_SHEET)
        events: list[tuple[datetime, int, object]] = []
        for row in range(1, runtime._last_used_row(source) + 1):
            event_time = runtime._cell_datetime(source, row, document)
            if event_time is None or event_time >= end_time:
                continue
            number_cell = source.getCellByPosition(3, row)
            number_text = str(number_cell.getString()).strip()
            try:
                number = int(float(number_text or number_cell.getValue()))
            except (TypeError, ValueError):
                continue
            if 1 <= number <= 84:
                events.append(
                    (event_time, number, source.getCellByPosition(6, row).getString())
                )

        active = runtime.active_rotor_limits(events, end_time=end_time)
        target = sheets.getByName(runtime.INPUT_STATE)
        history = runtime._ensure_rotor_log(document)
        updated: list[str] = []
        cleared: list[str] = []

        for row in range(3, max(runtime._last_used_row(target), 97) + 1):
            label = str(target.getCellByPosition(3, row).getString()).strip()
            match = re.fullmatch(r"ВЭУ-(\d+)", label, re.IGNORECASE)
            if match is None:
                continue
            number = int(match.group(1))
            setpoint_cell = target.getCellByPosition(5, row)
            repair_cell = target.getCellByPosition(6, row)
            available_cell = target.getCellByPosition(7, row)
            reason_cell = target.getCellByPosition(8, row)
            time_cell = target.getCellByPosition(9, row)
            current_reason = str(reason_cell.getString()).strip().casefold()
            record = active.get(number)

            if record is not None:
                repair = runtime.rotor_repair_power(record.limit_value)
                repair_cell.setValue(repair)
                available_cell.setValue(
                    max(float(setpoint_cell.getValue()) - repair, 0.0)
                )
                reason = (
                    f"Ограничение по оборотам {record.limit_value:g}"
                ).replace(".", ",")
                reason_cell.setString(reason)
                time_cell.setValue(runtime._to_serial(record.event_time, document))
                runtime._set_number_format(document, time_cell, "DD.MM.YYYY HH:MM")
                target.getCellRangeByPosition(0, row, 10, row).setPropertyValue(
                    "CellBackColor", 0xDCE6F1
                )
                runtime._append_rotor_log(
                    history,
                    document,
                    number,
                    "Ограничение",
                    record.source_text,
                )
                updated.append(
                    f"ВЭУ-{number} — {record.limit_value:g}".replace(".", ",")
                )
            elif "ограничение по оборотам" in current_reason:
                repair_cell.setValue(0.0)
                available_cell.setValue(max(float(setpoint_cell.getValue()), 0.0))
                reason_cell.setString("")
                time_cell.setString("")
                target.getCellRangeByPosition(0, row, 10, row).setPropertyValue(
                    "IsCellBackgroundTransparent", True
                )
                runtime._append_rotor_log(
                    history,
                    document,
                    number,
                    "Очистка",
                    "Активного ограничения по оборотам нет",
                )
                cleared.append(f"ВЭУ-{number}")

        try:
            document.calculateAll()
        except Exception:
            pass
        lines = [f"Ограничения рассчитаны на {report_date:%d.%m.%Y} 07:00."]
        lines.append("Обновлено: " + (", ".join(updated) if updated else "нет"))
        lines.append("Очищено: " + (", ".join(cleared) if cleared else "нет"))
        runtime._message("\n".join(lines))
    except Exception as exc:
        if str(exc) != "Операция отменена.":
            runtime._message(f"Не удалось обновить ограничения: {exc}", error=True)


def install_exact_tools_contract(runtime: Any, extension_root: Path) -> None:
    """Install operator commands that depend on exact report-form coordinates."""

    if getattr(runtime, "_EXACT_TOOLS_CONTRACT_003_APPLIED", False):
        return
    runtime._SHIFT_HELPER_EXTENSION_ROOT = str(Path(extension_root).resolve())
    runtime.update_rotor_limits_from_log = lambda _args=None: _update_rotor(
        runtime, _args
    )
    runtime._EXACT_TOOLS_CONTRACT_003_APPLIED = True
