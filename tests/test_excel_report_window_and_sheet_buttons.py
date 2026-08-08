from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VBA = ROOT / "packaging" / "excel_addin" / "vba"


def _source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def test_report_window_is_derived_from_authoritative_report_date() -> None:
    window = _source("modShiftHelperReportWindow.bas")
    events = _source("CShiftHelperAppEvents.cls")
    station = _source("modShiftHelperStationFacts.bas")

    assert 'raw = prep.Range("B3").Value2' in window
    assert 'prep.Range("B4").Value = reportDate - 1 + TimeSerial(7, 0, 0)' in window
    assert 'prep.Range("B5").Value = reportDate + TimeSerial(7, 0, 0)' in window
    assert 'Set hit = Intersect(Target, Sh.Range("B3"))' in window
    assert "SH_HandlePrepReportDateChange Sh, Target" in events
    assert station.count("SH_SyncReportWindow wb") >= 4


def test_sheet_buttons_have_parameterless_xlam_entry_points() -> None:
    buttons = _source("modShiftHelperMailButtons.bas")

    expected = {
        "SH_Mail_List1": 'SH_CreateStationMailingDraft "list:1"',
        "SH_Mail_List2": 'SH_CreateStationMailingDraft "list:2"',
        "SH_Mail_List3": 'SH_CreateStationMailingDraft "list:3"',
        "SH_Mail_Morning": 'SH_CreateStationMailingDraft "morning"',
        "SH_Mail_Zarubezhneft_List1": 'SH_CreateStationMailingDraft "foreign-list:1"',
        "SH_Mail_Zarubezhneft_List2": 'SH_CreateStationMailingDraft "foreign-list:2"',
        "SH_Mail_Zarubezhneft_List3": 'SH_CreateStationMailingDraft "foreign-list:3"',
        "SH_Mail_Zarubezhneft_Morning": 'SH_CreateStationMailingDraft "foreign-morning"',
        "SH_Mail_Zarubezhneft": 'SH_CreateStationMailingDraft "foreign-sheet"',
    }
    for macro_name, action in expected.items():
        assert f"Public Sub {macro_name}()" in buttons
        assert action in buttons
