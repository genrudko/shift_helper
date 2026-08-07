import ast
import base64
import re
import zlib
from pathlib import Path


def _calc_source() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (
        repo_root
        / "packaging/libreoffice_extension/Scripts/python/shift_helper_calc.py"
    ).read_text(encoding="utf-8")


def _repair_source() -> str:
    tree = ast.parse(_calc_source())
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "_PHOTO_REPAIR_PAYLOAD"
            for target in node.targets
        )
    )
    payload = ast.literal_eval(assignment.value)
    source = zlib.decompress(base64.b64decode(payload)).decode("utf-8")
    compile(source, "shift_helper_report_repairs.py", "exec")
    return source


def _controls_source() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return (
        repo_root / "packaging/libreoffice_extension/shift_helper_controls.py"
    ).read_text(encoding="utf-8")


def _function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_photo_repair_rebuilds_dates_percentages_and_violation_layout() -> None:
    calc = _calc_source()
    source = _repair_source()
    controls = _controls_source()
    main = _function_source(source, "_write_main")
    violations = _function_source(source, "_write_violations")
    generation = _function_source(source, "_import_generation")

    assert "PHOTO-REPAIR-001" in calc
    assert "previous_day = report_date - timedelta(days=1)" in main
    assert "Последние изменения" in main
    assert "План с 01 по" in main
    assert "Нарастающий итог на" in main
    assert "completion = month_generation / plan_to_date if plan_to_date else 0.0" in main
    assert 'runtime._set_number_format(book, cell, "0.00%")' in main
    assert "required_power = -1.0" in main

    assert 'headers = (\n        "№",\n        "Наименование нарушения"' in violations
    assert '"Примечание"' not in violations
    assert "_apply_black_grid" in violations
    assert 'setPropertyValue("CharFontName", "Calibri")' in violations
    assert "visible_rows = max(len(data), 1)" in violations

    assert "report_date, _offset = runtime._prep_settings(document)" in generation
    assert "_ask_report_date" not in generation
    assert 'main.getCellByPosition(1, 1).setFormula' in generation

    assert 'scripts / "shift_helper_calc.py"' in controls
    assert "repairs.patch_report_runtime(runtime)" in controls
    assert "install_acceptance_repairs" in controls
    assert '"generation": ("report", "import_generation_from_outlook")' in controls


def test_photo_repair_status_inference_separates_categories() -> None:
    source = _repair_source()
    tree = ast.parse(source)
    selected = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_number", "_infer_state_status"}
    ]
    namespace = {"re": re}
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), "repair-status", "exec"),
        namespace,
    )
    infer = namespace["_infer_state_status"]

    assert infer("ТО оборудования 1С 35 РУ ВЭС", 2.5, 0, 2.5) == "Останов"
    assert infer("Отбор проб масла главного подшипника", 2.5, 0, 0) == "Останов"
    assert infer("Повреждение ВЭУ-24 от внешнего воздействия", 2.5, 0, 2.5) == "Авария"
    assert infer("Плановый ремонт редуктора", 2.5, 0, 2.5) == "Ремонт"
    assert infer("", 2.5, 2.5, 0) == "Работа"
    assert infer("", 2.5, 1.5, 0) == "Ограничение"
