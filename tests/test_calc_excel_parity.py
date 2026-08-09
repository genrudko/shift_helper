from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARITY = ROOT / "src/shift_helper/core/calc_excel_parity.py"
CONTROLS = ROOT / "packaging/libreoffice_extension/shift_helper_controls.py"
ADDONS = ROOT / "packaging/libreoffice_extension/Addons.xcu"
BUILDER = ROOT / "src/shift_helper/extension_builder.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_calc_parity_carries_both_accepted_station_profiles() -> None:
    source = _source(PARITY)
    ast.parse(source)
    for marker in (
        "STATION_KOCH = 1",
        "STATION_KUZ = 2",
        'STATION_WTG_COUNTS = {STATION_KOCH: 84, STATION_KUZ: 64}',
        '(1, 16, "GVIE0531")',
        '(17, 24, "GVIE0555")',
        '(25, 32, "GVIE0546")',
        '(33, 40, "GVIE0543")',
        '(41, 48, "GVIE0547")',
        '(49, 56, "GVIE0549")',
        '(57, 64, "GVIE0545")',
        "36814159",
        "45505936",
        "30154342",
        "13003670",
        "51934734",
        "60625012",
        "49433027",
        "14234957",
    ):
        assert marker in source
    assert "_expected_assets(station_id)" in source
    assert 'f"ВЭУ-{number}"' in source


def test_calc_parity_syncs_report_window_from_b3_contract() -> None:
    source = _source(PARITY)
    assert "_sync_report_window" in source
    assert "runtime._refresh_prep_window(document, prep, report_date)" in source
    assert "XModifyListener" in source
    assert "_ReportWindowListener" in source
    assert "current == self.last_date" in source
    assert "_sync_report_window(runtime, document)" in source


def test_calc_generation_supports_both_station_workbook_contracts() -> None:
    source = _source(PARITY)
    for marker in (
        '"J26"',
        '"Z26"',
        '"G26"',
        '"Q26"',
        '"сумма по вэс"',
        '"потреблен"',
        "numeric_rows >= 20",
        "source_date != expected_date",
        'expected_profile = "kuz" if station_id == STATION_KUZ else "kves"',
        "Fallback-Match",
        "Station-Match",
        "GetSharedDefaultFolder",
    ):
        assert marker in source


def test_calc_final_report_copies_prepared_sheets_and_freezes_values() -> None:
    source = _source(PARITY)
    for marker in (
        "REPORT_INPUTS",
        "REPORT_OUTPUTS",
        "target_sheets.importSheet(document, input_name, position)",
        "data_range.getDataArray()",
        ".setDataArray(data)",
        'if _sheet_text(state, "L3") == "Статус ВЭУ"',
        "state.getColumns().removeByIndex(11, 1)",
        "state.getRows().removeByIndex(74, 24)",
        "OUTPUT_OFFSETS",
        '"Calc MS Excel 2007 XML"',
        'sheet.getCellRangeByName("B10").setString(str(path))',
    ):
        assert marker in source


def test_calc_mailing_matches_accepted_excel_station_contract() -> None:
    source = _source(PARITY)
    for marker in (
        '"list:1"',
        '"foreign-list:1"',
        '"foreign-morning"',
        '"foreign-sheet"',
        '"Рассылка"',
        'f"Список рассылки №{list_number}"',
        '"Рапорт утро"',
        '"Зарубежнефть"',
        '"A8"',
        '"B17"',
        '"B18"',
        '"B19"',
        '"B20"',
        "WordEditor",
        "Attachments.Add",
        "service:ru.kves.shifthelper.calc.controls?",
    ):
        assert marker in source
    assert ".Send()" not in source
    assert "$mail.Send" not in source


def test_calc_ui_and_oxt_builder_expose_parity_runtime() -> None:
    controls = _source(CONTROLS)
    addons = _source(ADDONS)
    builder = _source(BUILDER)
    for marker in (
        '"stationkoch": ("report", "select_koch_station")',
        '"stationkuz": ("report", "select_kuz_station")',
        '"mail1": ("report", "mail_list_1")',
        '"foreignsheet": ("report", "mail_foreign_sheet")',
        '"mailbuttons": ("report", "refresh_mail_buttons")',
        "calc_excel_parity.install_calc_excel_parity",
    ):
        assert marker in controls
    for action in (
        "stationkoch",
        "stationkuz",
        "calendarprep",
        "generationsettings",
        "mail1",
        "mail2",
        "mail3",
        "mailmorning",
        "foreignmail1",
        "foreignmail2",
        "foreignmail3",
        "foreignmorning",
        "foreignsheet",
        "mailbuttons",
    ):
        assert f"service:ru.kves.shifthelper.calc.controls?{action}" in addons
    assert "calc_excel_parity.py" in builder


def test_calc_station_rebuild_preserves_styles_and_filename_is_station_aware() -> None:
    controls = _source(CONTROLS)
    assert "range_obj.clearContents(31)" in controls
    assert "HARDATTR/STYLES" in controls
    assert "runtime.default_report_filename = station_report_filename" in controls
    assert 'return f"Рапорт НСС {station_name} от {report_date:%Y-%m-%d}.xlsx"' in controls
    assert "parity.STATION_NAMES[station_id]" in controls
