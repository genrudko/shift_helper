import zipfile
from pathlib import Path

from shift_helper.extension_builder import (
    _decode_integrated_report,
    build_calc_extension,
    verify_calc_extension,
)


def test_build_extension_contains_integrated_full_test_payload(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output = tmp_path / "Shift-Helper-Calc-FULL-TEST-001.oxt"
    build_calc_extension(repo_root=repo_root, output=output)
    names = verify_calc_extension(output)

    assert "description.xml" in names
    assert "Addons.xcu" in names
    assert "CalcWindowState.xcu" in names
    assert "shift_helper_controls.py" in names
    assert "Scripts/python/shift_helper_auto.py" in names
    assert "Scripts/python/shift_helper_report.py" in names
    assert "Scripts/python/pythonpath/shift_helper/core/selection.py" in names
    assert all(
        not name.startswith("/") and ".." not in name.split("/")
        for name in names
    )

    with zipfile.ZipFile(output) as archive:
        description = archive.read("description.xml").decode("utf-8")
        manifest = archive.read("META-INF/manifest.xml").decode("utf-8")
        addons = archive.read("Addons.xcu").decode("utf-8")
        window_state = archive.read("CalcWindowState.xcu").decode("utf-8")
        controls = archive.read("shift_helper_controls.py").decode("utf-8")
        automatic = archive.read("Scripts/python/shift_helper_auto.py").decode("utf-8")
        report_loader = archive.read("Scripts/python/shift_helper_report.py").decode(
            "utf-8"
        )
        report = _decode_integrated_report(report_loader)

        assert '<version value="0.4.0.dev0"/>' in description
        assert "application/vnd.sun.star.uno-component;type=Python" in manifest
        assert "application/vnd.sun.star.configuration-data" in manifest

        assert "XSelectionChangeListener" in automatic
        assert "XModifyListener" in automatic
        assert "XDispatchProviderInterceptor" in automatic
        assert '".uno:Paste"' in automatic

        assert "base64.b85decode" in report_loader
        assert "zlib.decompress" in report_loader
        assert "prepare_report_input_sheets" in report
        assert "import_generation_from_outlook" in report
        assert "generate_full_report" in report
        assert "generate_emergency_report" in report
        assert "select_emergency_events" in report
        assert "read_uno_journal" in report
        assert 'INPUT_PREP = "Подготовка рапорта"' in report
        assert "Смещение времени в готовом рапорте, ч" in report
        assert "DEFAULT_TIME_OFFSET_HOURS = -3.0" in report
        assert "def _apply_grid" in report
        assert 'uno.createUnoStruct("com.sun.star.table.TableBorder")' in report
        assert "def _normalize_state_row" in report
        assert "p_avail = max(p_set - p_repair, 0.0)" in report
        assert "elapsed_days = max(report_date.day - 1, 0)" in report
        assert "def _shift_datetime" in report
        assert "time_offset_hours=time_offset_hours" in report
        assert "Ввод - Основные" in report
        assert "Ввод - Команды" in report
        assert "Ввод - Нарушения" in report
        assert "Ввод - Состояние ВЭУ" in report
        assert "Ввод - Работы" in report
        assert "Ввод - Дефекты" in report
        assert "openpyxl" not in report

        assert '"prepare": ("report", "prepare_report_input_sheets")' in controls
        assert '"generation": ("report", "import_generation_from_outlook")' in controls
        assert '"report": ("report", "generate_full_report")' in controls
        assert "runtime.XSCRIPTCONTEXT" in controls
        assert "def _synchronize_report_date" in controls
        assert 'main_cell.setFormula(f"=\'{_INPUT_PREP}\'.B3")' in controls
        assert "main_changed or prep_created or _cell_is_empty(prep_cell)" in controls

        assert "service:ru.kves.shifthelper.calc.controls?prepare" in addons
        assert "service:ru.kves.shifthelper.calc.controls?generation" in addons
        assert "service:ru.kves.shifthelper.calc.controls?report" in addons
        assert "Подготовить полный контур рапорта" in addons
        assert "Импортировать генерацию" in addons
        assert "Сформировать полный утренний рапорт" in addons

        assert (
            "private:resource/toolbar/addon_ru.kves.shifthelper.calc.toolbar.v033"
            in window_state
        )
        assert "<value>true</value>" in window_state


def test_extension_build_is_deterministic(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    first = tmp_path / "first.oxt"
    second = tmp_path / "second.oxt"
    build_calc_extension(repo_root=repo_root, output=first)
    build_calc_extension(repo_root=repo_root, output=second)
    assert first.read_bytes() == second.read_bytes()
