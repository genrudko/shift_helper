"""Small runtime hardening repairs for the Calc/Excel parity bridge."""

from __future__ import annotations

from typing import Any

# Clear values/formulas/annotations only; keep styles, borders, widths and other
# formatting copied from the approved prepared-sheet form.
_CONTENT_FLAGS = 1 | 2 | 4 | 8 | 16


def _clear_contents(range_obj: Any) -> None:
    range_obj.clearContents(_CONTENT_FLAGS)


def _station_report_filename(parity, module, runtime, report_date) -> str:
    document = runtime._document()
    station_id = parity._station_id(module, runtime, document)
    station_name = parity.STATION_NAMES[station_id]
    return f"Рапорт НСС {station_name} от {report_date:%Y-%m-%d}.xlsx"


def install_calc_excel_parity_repair(parity, module, runtime) -> None:
    """Preserve exact form styling and make output naming station-aware."""

    if getattr(runtime, "_CALC_EXCEL_PARITY_REPAIR_APPLIED", False):
        return
    parity._clear = _clear_contents
    runtime.default_report_filename = lambda report_date: _station_report_filename(
        parity,
        module,
        runtime,
        report_date,
    )
    runtime._CALC_EXCEL_PARITY_REPAIR_APPLIED = True
