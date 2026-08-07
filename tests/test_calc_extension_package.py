from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from shift_helper.extension_builder import (
    _decode_integrated_report,
    build_calc_extension,
    verify_calc_extension,
)


def test_build_extension_contains_integrated_exact_form_payload(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output = tmp_path / "Shift-Helper-Calc-FULL-TEST-001.oxt"
    build_calc_extension(repo_root=repo_root, output=output)
    names = verify_calc_extension(output)

    required = {
        "description.xml",
        "Addons.xcu",
        "CalcWindowState.xcu",
        "shift_helper_controls.py",
        "Scripts/python/shift_helper_auto.py",
        "Scripts/python/shift_helper_report.py",
        "Templates/report_template.xlsx",
        "Scripts/python/pythonpath/shift_helper/core/exact_report_contract.py",
        "Scripts/python/pythonpath/shift_helper/core/exact_storage_contract.py",
        "Scripts/python/pythonpath/shift_helper/core/exact_migration_contract.py",
        "Scripts/python/pythonpath/shift_helper/core/exact_tools_contract.py",
        "Scripts/python/pythonpath/shift_helper/core/acceptance_repairs_006.py",
    }
    assert required.issubset(names)
    assert all(
        not name.startswith("/") and ".." not in name.split("/")
        for name in names
    )

    with zipfile.ZipFile(output) as archive:
        description = archive.read("description.xml").decode("utf-8")
        manifest = archive.read("META-INF/manifest.xml").decode("utf-8")
        addons = archive.read("Addons.xcu").decode("utf-8")
        controls = archive.read("shift_helper_controls.py").decode("utf-8")
        report_loader = archive.read(
            "Scripts/python/shift_helper_report.py"
        ).decode("utf-8")
        report = _decode_integrated_report(report_loader)
        migration = archive.read(
            "Scripts/python/pythonpath/shift_helper/core/"
            "exact_migration_contract.py"
        ).decode("utf-8")
        acceptance = archive.read(
            "Scripts/python/pythonpath/shift_helper/core/"
            "acceptance_repairs_006.py"
        ).decode("utf-8")
        template = archive.read("Templates/report_template.xlsx")

    assert '<version value="0.4.0.dev0"/>' in description
    assert "application/vnd.sun.star.uno-component;type=Python" in manifest
    assert "prepare_report_input_sheets" in report
    assert "import_generation_from_outlook" in report
    assert "generate_full_report" in report
    assert "openpyxl" not in report

    assert "install_exact_storage_contract(exact_report_contract)" in controls
    assert "exact_report_contract.install_exact_report_contract(runtime, root)" in controls
    assert "install_acceptance_repairs(exact_report_contract, runtime, root)" in controls
    assert "install_exact_migration_contract(exact_report_contract, runtime)" in controls
    assert "install_exact_tools_contract(runtime, root)" in controls
    assert "runtime.XSCRIPTCONTEXT" in controls

    assert "install_exact_migration_contract" in migration
    assert "_legacy_main" in migration
    assert "_legacy_state" in migration
    assert "_restore_works" in migration
    assert "openpyxl" not in migration
    compile(migration, "exact_migration_contract.py", "exec")

    for marker in (
        'INPUT_OUTAGES = "Ввод - Аварийные отключения"',
        "show_report_date_calendar",
        "show_generation_import_settings",
        "import_generation",
        "C10/24000",
        "STATUS_COLUMN = 11",
    ):
        assert marker in acceptance
    compile(acceptance, "acceptance_repairs_006.py", "exec")

    assert hashlib.sha256(template).hexdigest() == (
        "cde2d2fb042f27dc514f71ac991676e423dd6a68667fbb6d3f928ab610acbb32"
    )
    assert "service:ru.kves.shifthelper.calc.controls?prepare" in addons
    assert "service:ru.kves.shifthelper.calc.controls?report" in addons


def test_extension_build_is_deterministic(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    first = tmp_path / "first.oxt"
    second = tmp_path / "second.oxt"
    build_calc_extension(repo_root=repo_root, output=first)
    build_calc_extension(repo_root=repo_root, output=second)
    assert first.read_bytes() == second.read_bytes()
