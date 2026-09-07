import hashlib
from pathlib import Path

VBA = Path(__file__).resolve().parents[1] / "packaging" / "excel_addin" / "vba"
CALC_SHARED_QUICK_INPUT = (
    Path(__file__).resolve().parents[1] / "src" / "shift_helper" / "core" / "quick_input.py"
)
BASE_CALC_SHARED_QUICK_INPUT_SHA256 = (
    "94762b0be347f548abb7b1b121d194e7afe53e6898d347a0d8f0c2a67b604e73"
)


def source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def test_excel_repair_does_not_modify_calc_shared_quick_input() -> None:
    assert hashlib.sha256(CALC_SHARED_QUICK_INPUT.read_bytes()).hexdigest() == (
        BASE_CALC_SHARED_QUICK_INPUT_SHA256
    )


def test_quick_input_dispatches_multicolumn_ranges_and_has_explicit_combined_map() -> None:
    quick = source("modShiftHelperQuickInput.bas")
    assert "Target.Columns.Count <> 1" not in quick
    assert "SH_QuickFieldKind" in quick
    for sheet_index, columns in {
        2: "3, 6",
        3: "5, 6",
        4: "4",
        5: "10, 11",
        6: "9, 10",
        7: "3, 10",
    }.items():
        expected = (
            f"Case SH_InputSheetName({sheet_index}): "
            f"SH_QuickCombinedColumns = Array({columns})"
        )
        assert expected in quick
    assert "Sh.Name = SH_InputSheetName(5) And (col = 10 Or col = 11)" in quick


def test_previous_scan_is_bounded_upward_and_status_checks_actual_viability() -> None:
    quick = source("modShiftHelperQuickInput.bas")
    assert "SH_QUICK_PREVIOUS_LIMIT" in quick
    bounded_scan = (
        "For scanRow = startRow To Application.Max(2, startRow - "
        "SH_QUICK_PREVIOUS_LIMIT) Step -1"
    )
    assert bounded_scan in quick
    assert "Application.EnableEvents = True" in quick
    assert "If Not Application.EnableEvents Then" in quick
    assert "SH_QuickInputEventAllowed(ActiveSheet)" in quick


def test_vba_distinguishes_numeric_compact_dates_and_stored_time_integers() -> None:
    quick = source("modShiftHelperQuickInput.bas")
    compact = 'candidate = Right$("000000" & CStr(CLng(n)), 6)'
    serial = "SH_IsPlausibleOperationalDateSerial"
    assert compact in quick and serial in quick
    assert quick.index(serial) < quick.index(compact)
    assert (
        "If CDbl(value) <> 0 And CDbl(value) = Int(CDbl(value)) Then Exit Function"
        in quick
    )


def test_public_station_generation_delegates_to_selected_station_path() -> None:
    station = source("modShiftHelperStation.bas")
    body = station.split("Public Sub SH_ImportStationGeneration()", 1)[1].split("End Sub", 1)[0]
    assert "SH_ImportStationGenerationSelected" in body
    assert "SH_ImportGenerationUniversal" not in body


def test_calendar_requires_explicit_acceptance_and_station_picker_skips_contour() -> None:
    calendar = source("modShiftHelperCalendar.bas")
    station = source("modShiftHelperStation.bas")
    navigation_commit = "If DateValue(currentDate) <> DateValue(initialDate) Then"
    assert navigation_commit not in calendar
    assert "SH_CalendarPointInDayGrid" in calendar
    body = station.split("Public Sub SH_ShowStationCalendar()", 1)[1].split("End Sub", 1)[0]
    assert "SH_EnsureStationReportContour" not in body
    assert "SH_ShowCalendar" in body


def test_calendar_uses_native_date_cell_hit_testing() -> None:
    calendar = source("modShiftHelperCalendar.bas")
    assert "Private Type SH_MCHITTESTINFO" in calendar
    assert "Private Const SH_MCM_HITTEST As Long = SH_MCM_FIRST + 14" in calendar
    assert "Private Const SH_MCHT_CALENDARDATE As Long = &H20001" in calendar
    assert "ScreenToClient(calendarHwnd, clientPoint)" in calendar
    assert "SendMessageW calendarHwnd, SH_MCM_HITTEST, 0, hitInfo" in calendar
    assert "hitInfo.uHit = SH_MCHT_CALENDARDATE" in calendar
    assert "bounds.Top + 34" not in calendar
    assert "bounds.Bottom - 12" not in calendar


def test_colon_time_components_are_strict_and_combined_time_only_keeps_seconds() -> None:
    quick = source("modShiftHelperQuickInput.bas")
    time_parser = quick.split("Private Function SH_TryParseTime", 1)[1].split(
        "End Function", 1
    )[0]
    combined = quick.split("Private Function SH_TryParseCombined", 1)[1].split(
        "End Function", 1
    )[0]
    assert "SH_IsDigits(CStr(parts(0)))" in time_parser
    assert "SH_IsDigits(CStr(parts(1)))" in time_parser
    assert "SH_IsDigits(CStr(parts(2)))" in time_parser
    assert "secondValue < 0 Or secondValue > 59" in time_parser
    assert "TimeSerial(hourValue, minuteValue, secondValue)" in time_parser
    assert "DateValue(previousValue) + TimeValue(parsedTime)" in combined


def test_generation_has_one_boolean_core_and_explicit_station_override() -> None:
    profiles = source("modShiftHelperGenProfiles.bas")
    station = source("modShiftHelperStationImport.bas")
    legacy = source("modShiftHelperGeneration.bas")
    assert "Public Function SH_ImportGenerationUniversalCore" in profiles
    assert "Optional ByVal stationOverride As String" in profiles
    assert 'stationHint = "kuz"' in station
    assert 'stationHint = "kves"' in station
    assert "SH_ImportGenerationUniversalCore(stationHint)" in station
    assert "SH_G2StationHint" not in station
    assert "monthGeneration =" not in station
    assert "SH_ImportGenerationUniversal" in legacy
    assert "SH_ReadGenerationWorkbook" not in legacy
    assert "factDate = DateAdd(\"d\", -1, DateValue(reportDate))" in profiles
    assert 'If Not SH_G2TryDate(sumSheet.Range("A2").Value2, sourceDate) Then' in profiles
    read_call = (
        'SH_G2ReadWorkbook sourcePath, DateAdd("d", -1, reportDate), '
        "daily, own, profileName"
    )
    profile_guard = "If Len(stationOverride) > 0 And LCase$(profileName) <> stationHint Then"
    assert read_call in profiles
    assert profile_guard in profiles
    assert profiles.index(read_call) < profiles.index(profile_guard)
    assert "Generation workbook profile does not match the selected station." in profiles


def test_report_dates_use_strict_text_parser_and_cut_copy_guard_survives() -> None:
    util = source("modShiftHelperUtil.bas")
    calendar = source("modShiftHelperCalendar.bas")
    report_window = source("modShiftHelperReportWindow.bas")
    events = source("CShiftHelperAppEvents.cls")
    assert "Public Function SH_TryParseReportDate" in util
    calendar_parser = calendar.split("Private Function SH_CalendarTryDate", 1)[1]
    assert "IsDate(value) Or IsNumeric(value)" not in calendar_parser
    assert "SH_TryParseReportDate(raw, reportDate)" in report_window
    assert "If Application.CutCopyMode <> False Then Exit Sub" in events
