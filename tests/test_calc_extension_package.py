import zipfile
from pathlib import Path

from shift_helper.extension_builder import build_calc_extension, verify_calc_extension


def test_build_extension_contains_only_safe_required_payload(tmp_path: Path) -> None:
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
    assert all(
        not name.startswith("/") and ".." not in name.split("/") for name in names
    )

    with zipfile.ZipFile(output) as archive:
        description = archive.read("description.xml").decode("utf-8")
        manifest = archive.read("META-INF/manifest.xml").decode("utf-8")
        addons = archive.read("Addons.xcu").decode("utf-8")
        window_state = archive.read("CalcWindowState.xcu").decode("utf-8")
        controls = archive.read("shift_helper_controls.py").decode("utf-8")
        macro = archive.read("Scripts/python/shift_helper_calc.py").decode("utf-8")
        automatic = archive.read("Scripts/python/shift_helper_auto.py").decode("utf-8")

        assert '<version value="0.3.1.dev3"/>' in description
        assert "application/vnd.sun.star.uno-component;type=Python" in manifest
        assert "application/vnd.sun.star.configuration-data" in manifest
        assert "shift_helper_controls.py" in manifest
        assert "Addons.xcu" in manifest
        assert "CalcWindowState.xcu" in manifest

        assert "g_exportedScripts" in macro
        assert "normalize_selected_dates" in macro
        assert "normalize_selected_times" in macro
        assert "enable_automatic_input" in automatic
        assert "disable_automatic_input" in automatic
        assert "automatic_input_status" in automatic
        assert "XSelectionChangeListener" in automatic
        assert "XModifyListener" in automatic
        assert "XCallback" in automatic
        assert "XDispatchProviderInterceptor" in automatic
        assert "XInterceptorInfo" in automatic
        assert "XDispatch" in automatic
        assert "registerDispatchProviderInterceptor" in automatic
        assert "releaseDispatchProviderInterceptor" in automatic
        assert '".uno:Paste"' in automatic
        assert "com.sun.star.awt.AsyncCallback" in automatic
        assert "com.sun.star.datatransfer.clipboard.SystemClipboard" in automatic
        assert "getTransferData" in automatic
        assert "enterHiddenUndoContext" in automatic
        assert "enterUndoContext" in automatic
        assert "XKeyHandler" not in automatic
        assert "addKeyHandler" not in automatic
        assert "__file__" not in macro
        assert "__file__" not in automatic
        assert "from shift_helper.uno_adapter.calc_selection import" in automatic

        assert "XJobExecutor" in controls
        assert "unohelper.ImplementationHelper" in controls
        assert "ru.kves.shifthelper.calc.controls" in controls
        assert "importlib.util.spec_from_file_location" in controls
        assert 'root / "Scripts" / "python"' in controls
        assert 'scripts / "pythonpath"' in controls
        assert "_ScriptContextAdapter" in controls
        assert "getCurrentComponent" in controls
        assert "runtime.XSCRIPTCONTEXT" in controls
        assert "MasterScriptProviderFactory" not in controls
        assert "vnd.sun.star.script:" not in controls

        assert "com.sun.star.sheet.SpreadsheetDocument" in addons
        assert "service:ru.kves.shifthelper.calc.controls?enable" in addons
        assert "service:ru.kves.shifthelper.calc.controls?disable" in addons
        assert "service:ru.kves.shifthelper.calc.controls?status" in addons
        assert "vnd.sun.star.script:" not in addons
        assert "Включить быстрый ввод" in addons
        assert "Выключить быстрый ввод" in addons
        assert "Состояние Shift-Helper" in addons

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
