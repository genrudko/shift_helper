from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
VBA = ROOT / "packaging" / "excel_addin" / "vba"
RIBBON = ROOT / "packaging" / "excel_addin" / "customUI14.xml"
NS = {"ui": "http://schemas.microsoft.com/office/2009/07/customui"}


def _source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def test_calendar_is_ribbon_owned_and_never_creates_a_workbook() -> None:
    calendar = _source("modShiftHelperCalendar.bas")
    callbacks = _source("modShiftHelperRibbon.bas")
    root = ET.parse(RIBBON).getroot()
    control = root.find(".//ui:dynamicMenu[@id='btnCalendar']", NS)
    assert control is not None
    assert control.attrib["getContent"] == "SH_RibbonCalendarMenu"
    assert "Workbooks.Add" not in calendar
    assert "SH_CalendarMenuXml" in calendar
    assert "SH_CalendarPickTag" in calendar
    assert "Public Sub SH_RibbonCalendarPick" in callbacks


def test_outlook_settings_are_ribbon_owned_and_never_create_a_workbook() -> None:
    outlook = _source("modShiftHelperOutlook.bas")
    callbacks = _source("modShiftHelperRibbon.bas")
    root = ET.parse(RIBBON).getroot()
    control = root.find(".//ui:dynamicMenu[@id='btnOutlook']", NS)
    assert control is not None
    assert control.attrib["getContent"] == "SH_RibbonOutlookMenu"
    assert "Workbooks.Add" not in outlook
    assert "mSettingsBook" not in outlook
    assert "SH_OutlookMenuXml" in outlook
    assert "SH_EditOutlookSetting" in outlook
    assert "Public Sub SH_RibbonOutlookEdit" in callbacks


def test_report_commands_bootstrap_instead_of_assuming_prep_sheet_exists() -> None:
    report = _source("modShiftHelperReport.bas")
    util = _source("modShiftHelperUtil.bas")
    outlook = _source("modShiftHelperOutlook.bas")
    rotor = _source("modShiftHelperRotor.bas")
    assert "Public Sub SH_EnsureReportContour" in report
    assert "Set prep = SH_EnsurePrepSheet(wb)" in report
    assert "SH_EnsureReportContour wb" in outlook
    assert "SH_EnsureReportContour wb" in rotor
    assert "Public Function SH_EnsurePrepSheet" in util
    assert "Public Function SH_RequireSheet" in util
    assert "If Not SH_HasSheet(wb, SH_PrepSheetName()) Then Err.Raise" not in report


def test_service_metadata_has_safe_missing_prep_behavior() -> None:
    meta = _source("modShiftHelperMeta.bas")
    assert "If Not SH_HasSheet(wb, SH_PrepSheetName()) Then Exit Function" in meta
    assert "Set ws = SH_EnsurePrepSheet(wb)" in meta


def test_selection_tools_cannot_mutate_a_transient_or_foreign_workbook() -> None:
    journal = _source("modShiftHelperJournal.bas")
    util = _source("modShiftHelperUtil.bas")
    assert journal.count("SH_SelectionRange(wb)") == 3
    assert "Public Function SH_SelectionRange" in util
    assert "ERR_SELECTION_BOOK" in util


def test_inspection_navigation_reports_missing_sheet_through_shared_guard() -> None:
    shift = _source("modShiftHelperShift.bas")
    assert "Set ws = SH_RequireSheet(wb, SH_InspectionSheetName())" in shift


def test_embedded_report_template_waits_for_the_file_it_actually_extracts() -> None:
    embedded = _source("modShiftHelperEmbedded.bas")
    assert 'targetPath = tempRoot & Application.PathSeparator & "shift_helper_report_template.xlsx"' in embedded
    assert 'zipFolder.ParseName("shift_helper_report_template.xlsx")' in embedded
    assert 'Application.PathSeparator & "report_template.xlsx"' not in embedded
    assert 'DateDiff("s", startedAt, Now) > 20' in embedded
