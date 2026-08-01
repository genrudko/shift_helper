import zipfile
from pathlib import Path

from shift_helper.extension_builder import build_calc_extension, verify_calc_extension


def test_build_extension_contains_safe_operator_and_report_payload(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output = tmp_path / "Shift-Helper-Calc-UNO-001.oxt"
    build_calc_extension(repo_root=repo_root, output=output)
    names = verify_calc_extension(output)

    assert "description.xml" in names
    assert "Addons.xcu" in names
    assert "CalcWindowState.xcu" in names
    assert "shift_helper_controls.py" in names
    assert "Scripts/python/shift_helper_calc.py" in names
    assert "Scripts/python/shift_helper_auto.py" in names
    assert "Scripts/python/shift_helper_report.py" in names
    assert "Scripts/python/pythonpath/shift_helper/core/events.py" in names
    assert "Scripts/python/pythonpath/shift_helper/core/selection.py" in names
    assert (
        "Scripts/python/pythonpath/shift_helper/uno_adapter/report_generation.py"
        in names
    )
    assert all(
        not name.startswith("/") and ".." not in name.split("/") for name in names
    )

    with zipfile.ZipFile(output) as archive:
        description = archive.read("description.xml").decode("utf-8")
        manifest = archive.read("META-INF/manifest.xml").decode("utf-8")
        addons = archive.read("Addons.xcu").decode("utf-8")
        window_state = archive.read("CalcWindowState.xcu").decode("utf-8")
        controls = archive.read("shift_helper_controls.py").decode("utf-8")
        automatic = archive.read("Scripts/python/shift_helper_auto.py").decode("utf-8")
        report = archive.read("Scripts/python/shift_helper_report.py").decode("utf-8")

        assert '<version value="0.3.2.dev0"/>' in description
        assert "application/vnd.sun.star.uno-component;type=Python" in manifest
        assert "application/vnd.sun.star.configuration-data" in manifest
        assert "shift_helper_controls.py" in manifest
        assert "Scripts/python" in manifest
        assert "Addons.xcu" in manifest
        assert "CalcWindowState.xcu" in manifest

        assert "XSelectionChangeListener" in automatic
        assert "XModifyListener" in automatic
        assert "XDispatchProviderInterceptor" in automatic
        assert '".uno:Paste"' in automatic
        assert "enable_automatic_input" in automatic
        assert "disable_automatic_input" in automatic
        assert "automatic_input_status" in automatic

        assert "generate_emergency_report" in report
        assert "UnoControlDialogModel" in report
        assert "com.sun.star.ui.dialogs.FilePicker" in report
        assert "loadComponentFromURL" in report
        assert "select_emergency_events" in report
        assert "read_uno_journal" in report
        assert "document.isModified()" in report
        assert "os.replace" in report
        assert "openpyxl" not in report

        assert (
            '"report": ("_shift_helper_extension_report", "shift_helper_report.py")'
            in controls
        )
        assert '"report": ("report", "generate_emergency_report")' in controls
        assert "importlib.util.spec_from_file_location" in controls
        assert "runtime.XSCRIPTCONTEXT" in controls
        assert "MasterScriptProviderFactory" not in controls
        assert "vnd.sun.star.script:" not in controls

        assert "service:ru.kves.shifthelper.calc.controls?report" in addons
        assert "Сформировать утренний рапорт" in addons
        assert "service:ru.kves.shifthelper.calc.controls?enable" in addons
        assert "service:ru.kves.shifthelper.calc.controls?disable" in addons
        assert "service:ru.kves.shifthelper.calc.controls?status" in addons
        assert "vnd.sun.star.script:" not in addons

        assert (
            "private:resource/toolbar/addon_ru.kves.shifthelper.calc.toolbar.v031"
            in window_state
        )
        assert "<value>true</value>" in window_state
        assert '<value xml:lang="ru-RU">Shift-Helper</value>' in window_state


def test_extension_build_is_deterministic(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    first = tmp_path / "first.oxt"
    second = tmp_path / "second.oxt"
    build_calc_extension(repo_root=repo_root, output=first)
    build_calc_extension(repo_root=repo_root, output=second)
    assert first.read_bytes() == second.read_bytes()
