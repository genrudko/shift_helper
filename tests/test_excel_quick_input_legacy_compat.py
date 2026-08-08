from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VBA = ROOT / "packaging" / "excel_addin" / "vba"


def _source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def test_quick_input_does_not_compete_with_legacy_macro_workbooks() -> None:
    compat = _source("modShiftHelperQuickCompat.bas")
    events = _source("CShiftHelperAppEvents.cls")

    assert "Public Function SH_QuickInputEventAllowed" in compat
    assert 'Right$(fileName, 5) = ".xlsm"' in compat
    assert 'Right$(fileName, 5) = ".xlsb"' in compat
    assert 'Right$(fileName, 4) = ".xls"' in compat
    assert "If Not SH_QuickInputEventAllowed(Sh) Then Exit Sub" in events
    assert events.count("If Not SH_QuickInputEventAllowed(Sh) Then Exit Sub") == 2


def test_quick_input_remains_available_for_macro_free_shared_xlsx() -> None:
    compat = _source("modShiftHelperQuickCompat.bas")

    assert 'Right$(fileName, 5) = ".xlsx"' not in compat
    assert "SH_QuickInputEventAllowed = True" in compat
