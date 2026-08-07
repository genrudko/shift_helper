from __future__ import annotations

import ast
import base64
import hashlib
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "packaging/libreoffice_extension/Templates"
TEMPLATE_SHA256 = "cde2d2fb042f27dc514f71ac991676e423dd6a68667fbb6d3f928ab610acbb32"


def _report_bytes() -> bytes:
    assert not (TEMPLATE_DIR / "report_template.xlsx").exists()
    chunks = sorted(TEMPLATE_DIR.glob("report_template.b64.*"))
    assert len(chunks) == 8
    encoded = "".join(path.read_text(encoding="ascii") for path in chunks)
    content = base64.b64decode(encoded, validate=True)
    assert hashlib.sha256(content).hexdigest() == TEMPLATE_SHA256
    return content


def _sheet_names(content: bytes) -> list[str]:
    with ZipFile(BytesIO(content)) as archive:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
    namespace = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    }
    sheets = root.find("m:sheets", namespace)
    assert sheets is not None
    return [item.attrib["name"] for item in sheets]


def test_embedded_report_contains_all_approved_sheets() -> None:
    assert _sheet_names(_report_bytes()) == [
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


def test_final_acceptance_moves_status_to_visible_state_sheet() -> None:
    storage = (
        ROOT / "src/shift_helper/core/exact_storage_contract.py"
    ).read_text(encoding="utf-8")
    acceptance = (
        ROOT / "src/shift_helper/core/acceptance_repairs_006.py"
    ).read_text(encoding="utf-8")
    ast.parse(storage)
    ast.parse(acceptance)

    # M:N remain the only hidden service area in the final acceptance repair.
    assert "META_KEY_COL = 12" in storage
    assert "META_VALUE_COL = 13" in storage
    assert "META_KEY_COLUMN = 12" in acceptance
    assert "META_VALUE_COLUMN = 13" in acceptance

    # The transitional J:K status store is migrated and then removed.
    assert "STATUS_COLUMN = 11" in acceptance
    assert 'header.setString("Статус ВЭУ")' in acceptance
    assert "_clear_legacy_statuses(prep)" in acceptance
    assert "getCellByPosition(STATUS_COLUMN, row)" in acceptance


def test_exact_migration_preserves_legacy_data_before_form_rebuild() -> None:
    path = ROOT / "src/shift_helper/core/exact_migration_contract.py"
    source = path.read_text(encoding="utf-8")
    ast.parse(source)
    for marker in (
        "_legacy_main",
        "_legacy_state",
        "_restore_main",
        "_restore_state",
        "_restore_works",
        "_restore_violations",
        "needs_rebuild",
        "had_legacy_data",
        "if not needs_rebuild:",
        "Данные старых листов перенесены",
        "Демонстрационные значения встроенного шаблона очищены",
        "install_exact_migration_contract",
    ):
        assert marker in source
    assert "openpyxl" not in source


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


def test_controls_install_final_report_contracts_in_order() -> None:
    source = (
        ROOT / "packaging/libreoffice_extension/shift_helper_controls.py"
    ).read_text(encoding="utf-8")
    assert "install_exact_storage_contract(exact_report_contract)" in source
    assert "exact_report_contract.install_exact_report_contract(runtime, root)" in source
    assert "install_acceptance_repairs(exact_report_contract, runtime, root)" in source
    assert "install_exact_migration_contract(exact_report_contract, runtime)" in source
    assert "install_exact_tools_contract(runtime, root)" in source
    assert "install_calc_workspace_repairs" not in source


def test_extension_payload_reconstructs_template_and_registers_runtimes() -> None:
    source = (
        ROOT / "src/shift_helper/extension_builder_payload.py"
    ).read_text(encoding="utf-8")
    assert '"Templates/report_template.xlsx"' in source
    assert "base64.b64decode" in source
    assert TEMPLATE_SHA256 in source
    assert "exact_report_contract.py" in source
    assert "exact_storage_contract.py" in source
    assert "exact_migration_contract.py" in source
    assert "exact_tools_contract.py" in source
    assert "acceptance_repairs_006.py" in source
