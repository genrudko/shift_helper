from __future__ import annotations

import ast
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "packaging/libreoffice_extension/Templates/report_template.xlsx"


def _sheet_names(path: Path) -> list[str]:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
    namespace = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    }
    sheets = root.find("m:sheets", namespace)
    assert sheets is not None
    return [item.attrib["name"] for item in sheets]


def test_embedded_report_contains_all_approved_sheets() -> None:
    assert _sheet_names(REPORT) == [
        "Основные данные",
        "Аварийные отключения ЛЭП",
        "Команды по внешней инициативе",
        "Нарушения ОТиПБ + Экология",
        "Состояние ВЭУ",
        "Запланированные работы",
        "Дефекты оборудования",
    ]


def test_exact_runtime_imports_forms_and_hides_external_template_picker() -> None:
    path = ROOT / "src/shift_helper/core/exact_report_contract.py"
    source = path.read_text(encoding="utf-8")
    ast.parse(source)
    for marker in (
        "report_template.xlsx",
        "importSheet",
        "Внешний файл шаблона не требуется",
        "_main_map",
        "_state_rows",
        "install_exact_report_contract",
        "main.getCellByPosition(9, report_date.month + 3)",
        '"C3"',
        '"C4"',
        '"C12"',
        '"C15"',
    ):
        assert marker in source


def test_exact_tools_runtime_uses_report_state_coordinates() -> None:
    path = ROOT / "src/shift_helper/core/exact_tools_contract.py"
    source = path.read_text(encoding="utf-8")
    ast.parse(source)
    for marker in (
        "getCellByPosition(3, row)",
        "getCellByPosition(6, row)",
        "getCellByPosition(7, row)",
        "update_rotor_limits_from_log",
        "install_exact_tools_contract",
    ):
        assert marker in source


def test_controls_install_exact_contracts_for_report_and_tools() -> None:
    source = (
        ROOT / "packaging/libreoffice_extension/shift_helper_controls.py"
    ).read_text(encoding="utf-8")
    assert "install_exact_report_contract(runtime, root)" in source
    assert "install_exact_tools_contract(runtime, root)" in source
    assert "install_calc_workspace_repairs" not in source


def test_extension_payload_registers_template_and_exact_runtimes() -> None:
    source = (
        ROOT / "src/shift_helper/extension_builder_payload.py"
    ).read_text(encoding="utf-8")
    assert '"Templates/report_template.xlsx"' in source
    assert "exact_report_contract.py" in source
    assert "exact_tools_contract.py" in source
