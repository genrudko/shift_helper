from pathlib import Path


def test_report_dialog_push_button_types_are_adapted() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    controls = (
        repo_root / "packaging/libreoffice_extension/shift_helper_controls.py"
    ).read_text(encoding="utf-8")
    report = (
        repo_root
        / "packaging/libreoffice_extension/Scripts/python/shift_helper_report.py"
    ).read_text(encoding="utf-8")

    assert "class _UnoCompatProxy" in controls
    assert '"com.sun.star.awt.PushButtonType.OK": "OK"' in controls
    assert '"com.sun.star.awt.PushButtonType.CANCEL": "CANCEL"' in controls
    assert "module.uno = _UnoCompatProxy(uno)" in controls
    assert (
        'uno.getConstantByName("com.sun.star.awt.PushButtonType.OK")' in report
    )
