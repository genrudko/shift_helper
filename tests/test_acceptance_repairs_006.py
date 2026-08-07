from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_acceptance_repair_source_covers_owner_blockers() -> None:
    path = ROOT / "src/shift_helper/core/acceptance_repairs_006.py"
    source = path.read_text(encoding="utf-8")
    ast.parse(source)

    for marker in (
        'INPUT_OUTAGES = "Ввод - Аварийные отключения"',
        "STATUS_COLUMN = 11",
        '"Статус ВЭУ"',
        "C10/24000",
        "EOMONTH('Подготовка рапорта'.B3;0)",
        "COUNTIF",
        '"com.sun.star.awt.UnoControlDateFieldModel"',
        "field.Dropdown = True",
        '"Настройки Outlook…"',
        '"Outlook: почтовый ящик"',
        '"Outlook: папка"',
        '"Outlook: маска вложения"',
        '"Outlook: глубина поиска, дней"',
        "select_emergency_events",
        "_refresh_outages",
        "_outlook_attachment",
        "service:ru.kves.shifthelper.calc.controls?generationsettings",
    ):
        assert marker in source

    # The emergency preview is deliberately NOT added to module.FORMS because
    # the six-form legacy migration uses that tuple to decide whether to clear
    # and restore operator data.
    assert "module.FORMS =" not in source
    assert "_ensure_outage_form(module, runtime, document)" in source
    assert "_clear_legacy_statuses(prep)" in source


def test_controls_route_report_specific_dialogs_to_report_runtime() -> None:
    source = (
        ROOT / "packaging/libreoffice_extension/shift_helper_controls.py"
    ).read_text(encoding="utf-8")
    ast.parse(source)

    assert '"calendarprep": ("report", "show_report_date_calendar")' in source
    assert (
        '"generationsettings": ("report", "show_generation_import_settings")'
        in source
    )
    acceptance_install = (
        "install_acceptance_repairs(exact_report_contract, runtime, root)"
    )
    migration_install = (
        "install_exact_migration_contract(exact_report_contract, runtime)"
    )
    assert acceptance_install in source
    assert source.index(acceptance_install) < source.index(migration_install)


def test_extension_payload_packages_acceptance_runtime() -> None:
    source = (
        ROOT / "src/shift_helper/extension_builder_payload.py"
    ).read_text(encoding="utf-8")
    ast.parse(source)
    assert "acceptance_repairs_006.py" in source
    assert (
        '"Scripts/python/pythonpath/shift_helper/core/acceptance_repairs_006.py"'
        in source
    )
