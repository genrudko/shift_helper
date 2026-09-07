from pathlib import Path


VBA = Path(__file__).resolve().parents[1] / "packaging" / "excel_addin" / "vba"


def source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


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
        expected = f"Case SH_InputSheetName({sheet_index}): SH_QuickCombinedColumns = Array({columns})"
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
    serial = "If n >= 20000# And n < 80000# Then"
    assert compact in quick and serial in quick
    assert quick.index(compact) < quick.index(serial)
    assert "If CDbl(value) = Int(CDbl(value)) Then Exit Function" in quick


def test_calendar_requires_explicit_acceptance_and_station_picker_skips_contour() -> None:
    calendar = source("modShiftHelperCalendar.bas")
    station = source("modShiftHelperStation.bas")
    navigation_commit = "If DateValue(currentDate) <> DateValue(initialDate) Then"
    assert navigation_commit not in calendar
    assert "SH_CalendarPointInDayGrid" in calendar
    body = station.split("Public Sub SH_ShowStationCalendar()", 1)[1].split("End Sub", 1)[0]
    assert "SH_EnsureStationReportContour" not in body
    assert "SH_ShowCalendar" in body


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
