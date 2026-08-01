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
    assert all(not name.startswith("/") and ".." not in name.split("/") for name in names)

    with zipfile.ZipFile(output) as archive:
        macro = archive.read("Scripts/python/shift_helper_calc.py").decode("utf-8")
        assert "g_exportedScripts" in macro
        assert "normalize_selected_dates" in macro
        assert "normalize_selected_times" in macro
        assert "__file__" not in macro
        assert "from shift_helper.uno_adapter.calc_selection import" in macro


def test_extension_build_is_deterministic(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    first = tmp_path / "first.oxt"
    second = tmp_path / "second.oxt"
    build_calc_extension(repo_root=repo_root, output=first)
    build_calc_extension(repo_root=repo_root, output=second)
    assert first.read_bytes() == second.read_bytes()
