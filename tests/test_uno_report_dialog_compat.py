from pathlib import Path

from shift_helper.extension_builder import _decode_integrated_report


def test_integrated_report_uses_real_uno_push_button_enums() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    controls = (
        repo_root / "packaging/libreoffice_extension/shift_helper_controls.py"
    ).read_text(encoding="utf-8")
    loader = (
        repo_root
        / "packaging/libreoffice_extension/Scripts/python/shift_helper_report.py"
    ).read_text(encoding="utf-8")
    report = _decode_integrated_report(loader)

    assert "class _UnoCompatProxy" not in controls
    assert "com.sun.star.awt.PushButtonType" in report
    assert 'uno.Enum("com.sun.star.awt.PushButtonType", "OK")' in report
    assert 'uno.Enum("com.sun.star.awt.PushButtonType", "CANCEL")' in report
    assert 'getConstantByName("com.sun.star.awt.PushButtonType.OK")' not in report
