from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VBA = ROOT / "packaging" / "excel_addin" / "vba"


def _source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def test_station_profiles_cover_kochubeevskaya_and_kuzminskaya_reports() -> None:
    station = _source("modShiftHelperStation.bas")

    assert "Public Const SH_STATION_KOCH As Long = 1" in station
    assert "Public Const SH_STATION_KUZ As Long = 2" in station
    assert "SH_ReportStationWtgCount = 64" in station
    assert "SH_ReportStationWtgCount = 84" in station
    assert "SH_ReportStationStateLastRow = 74" in station
    assert "SH_ReportStationStateLastRow = 98" in station

    # Kuzminskaya reference report uploaded during live acceptance.
    for value in (
        "36814159#",
        "33290612#",
        "45586481#",
        "39089392#",
        "30340811#",
        "20301332#",
        "20890080#",
        "31380024#",
        "27937084#",
        "52918060#",
        "40794027#",
        "45505936#",
    ):
        assert value in station

    assert "starts = Array(1, 33, 57, 25, 41, 49, 17)" in station
    assert "ends = Array(16, 40, 64, 32, 48, 56, 24)" in station
    assert (
        'codes = Array("GVIE0531", "GVIE0543", "GVIE0545", "GVIE0546", '
        '"GVIE0547", "GVIE0549", "GVIE0555")'
    ) in station


def test_station_profile_remains_compatible_with_kochubeevskaya_layout() -> None:
    station = _source("modShiftHelperStation.bas")

    assert "starts = Array(45, 5, 13, 21, 29, 37, 61, 53, 69, 77, 1)" in station
    assert "ends = Array(52, 12, 20, 28, 36, 44, 68, 60, 76, 84, 4)" in station
    assert (
        'codes = Array("GVIE0532", "GVIE0534", "GVIE0536", "GVIE0537", '
        '"GVIE0538", "GVIE0539", "GVIE0570", "GVIE0571", "GVIE0573", '
        '"GVIE0580", "GVIE0891")'
    ) in station


def test_report_actions_use_station_aware_contour_and_visible_station_selector() -> None:
    station = _source("modShiftHelperStation.bas")
    station_facts = _source("modShiftHelperStationFacts.bas")
    station_import = _source("modShiftHelperStationImport.bas")
    ribbon = _source("modShiftHelperRibbon.bas")
    output = _source("modShiftHelperReportOutput.bas")
    custom_ui = (ROOT / "packaging" / "excel_addin" / "customUI14.xml").read_text(
        encoding="utf-8"
    )

    assert "Public Sub SH_EnsureStationReportContour" in station
    assert "SH_ApplyStationProfile wb, stationId" in station
    assert "SH_ApplyCriticalFormulas wb" in station
    assert "SH_ApplyStationOverrides wb, stationId" in station
    assert "SH_EnsureStationReportContour wb" in output

    assert "SH_PrepareStationReportForRibbon" in ribbon
    assert "SH_ShowStationCalendarForRibbon" in ribbon
    assert "SH_GenerateStationReportForRibbon" in ribbon
    assert "SH_SelectStationForRibbon" in ribbon
    assert "SH_ImportStationGenerationSelected" in ribbon
    assert "SH_ImportGenerationUniversal" in station_import
    assert 'SH_U("041A04430437")' in station_import
    assert "SH_ApplyStationHistoricalFacts wb" in station_import
    assert "SH_ApplyStationHistoricalFacts wb" in station_facts
    assert "SH_GeneratePreparedReport" in station_facts
    assert "SH_UpdateStationRotorLimits" in ribbon
    assert "SH_RibbonStationMenu" in ribbon
    assert "SH_RibbonSetStation" in ribbon

    assert 'id="btnStation"' in custom_ui
    assert 'getContent="SH_RibbonStationMenu"' in custom_ui


def test_kuzminskaya_state_profile_keeps_status_service_only_and_merged_gtp_blocks() -> None:
    station = _source("modShiftHelperStation.bas")
    output = _source("modShiftHelperReportOutput.bas")

    assert "state.Cells(rowNumber, 12).Value = SH_StatusText(1)" in station
    assert 'state.Rows("75:98").Delete Shift:=xlUp' in station
    assert '.Range("B" & CStr(groupRow) & ":B" & CStr(rowNumber - 1)).Merge' in station
    assert '.Range("C" & CStr(groupRow) & ":C" & CStr(rowNumber - 1)).Merge' in station
    assert "SH_OutputRemoveWtgServiceColumns target" in output
    assert "target.Columns(12).Delete" in output


def test_station_history_seeds_known_2026_facts_without_overwriting_current_month() -> None:
    facts = _source("modShiftHelperStationFacts.bas")

    for value in (
        "30154342#",
        "33176283#",
        "33173000#",
        "21151677#",
        "29470109#",
        "11951418#",
        "13003670#",
    ):
        assert value in facts

    assert "lastKnownMonth = Application.Min(7, Month(reportDate) - 1)" in facts
    assert "main.Cells(monthIndex + 4, 10).Value2 = value" in facts
