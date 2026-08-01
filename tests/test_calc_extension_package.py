import zipfile
from pathlib import Path

from shift_helper.extension_builder import build_calc_extension, verify_calc_extension


def test_build_extension_contains_only_safe_required_payload(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output = tmp_path / "Shift-Helper-Calc-UNO-001.oxt"
    build_calc_extension(repo_root=repo_root, output=output)
    names = verify_calc_extension(output)
    assert "description.xml" in names
    assert "Scripts/python/shift_helper_calc.py" in names
    assert "Scripts/python/shift_helper_auto.py" in names
    assert all(not name.startswith("/") and ".." not in name.split("/") for name in names)

    with zipfile.ZipFile(output) as archive:
        description = archive.read("description.xml").decode("utf-8")
        macro = archive.read("Scripts/python/shift_helper_calc.py").decode("utf-8")
        automatic = archive.read("Scripts/python/shift_helper_auto.py").decode("utf-8")
        assert '<version value="0.3.0.dev4"/>' in description
        assert "g_exportedScripts" in macro
        assert "normalize_selected_dates" in macro
        assert "normalize_selected_times" in macro
        assert "enable_automatic_input" in automatic
        assert "disable_automatic_input" in automatic
        assert "automatic_input_status" in automatic
        assert "XSelectionChangeListener" in automatic
        assert "XModifyListener" in automatic
        assert "XCallback" in automatic
        assert "XKeyHandler" in automatic
        assert "com.sun.star.awt.AsyncCallback" in automatic
        assert "com.sun.star.datatransfer.clipboard.SystemClipboard" in automatic
        assert "addCallback" in automatic
        assert "addKeyHandler" in automatic
        assert "getTransferData" in automatic
        assert "keyPressed" in automatic
        assert "enterHiddenUndoContext" in automatic
        assert "enterUndoContext" in automatic
        assert "__file__" not in macro
        assert "__file__" not in automatic
        assert "from shift_helper.uno_adapter.calc_selection import" in automatic


def test_extension_build_is_deterministic(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    first = tmp_path / "first.oxt"
    second = tmp_path / "second.oxt"
    build_calc_extension(repo_root=repo_root, output=first)
    build_calc_extension(repo_root=repo_root, output=second)
    assert first.read_bytes() == second.read_bytes()
