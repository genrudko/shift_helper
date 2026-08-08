from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
VBA = ROOT / "packaging" / "excel_addin" / "vba"
RIBBON = ROOT / "packaging" / "excel_addin" / "customUI14.xml"
NS = {"ui": "http://schemas.microsoft.com/office/2009/07/customui"}


def _source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def test_calendar_is_native_popup_and_never_creates_a_workbook() -> None:
    calendar = _source("modShiftHelperCalendar.bas")
    callbacks = _source("modShiftHelperRibbon.bas")
    root = ET.parse(RIBBON).getroot()
    control = root.find(".//ui:button[@id='btnCalendar']", NS)
    assert control is not None
    assert control.attrib["onAction"] == "SH_RibbonCalendar"
    assert "Workbooks.Add" not in calendar
    assert 'calendarClass = "SysMonthCal32"' in calendar
    assert "CreateWindowExW" in calendar
    assert "SH_MCN_SELECT" in calendar
    assert "SH_MCM_GETCURSEL" in calendar
    assert "SH_CalendarMenuXml" not in calendar
    assert "Public Sub SH_RibbonCalendar" in callbacks


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


def test_row_height_is_native_autofit_without_manual_prompt() -> None:
    journal = _source("modShiftHelperJournal.bas")
    callbacks = _source("modShiftHelperRibbon.bas")
    root = ET.parse(RIBBON).getroot()
    control = root.find(".//ui:button[@id='btnRows']", NS)
    assert control is not None
    assert control.attrib["label"] == "Автовысота строк"
    assert control.attrib["onAction"] == "SH_RibbonAutoFitRows"
    assert "Public Sub SH_AutoFitRows" in journal
    assert ".EntireRow.AutoFit" in journal
    assert "Application.InputBox" not in journal
    assert "Public Sub SH_RibbonAutoFitRows" in callbacks


def test_every_top_level_shift_helper_control_has_an_icon_callback() -> None:
    callbacks = _source("modShiftHelperRibbon.bas")
    root = ET.parse(RIBBON).getroot()
    controls = root.findall(".//ui:button", NS) + root.findall(".//ui:dynamicMenu", NS)
    assert controls
    assert all(control.attrib.get("getImage") == "SH_RibbonImage" for control in controls)
    assert "Public Sub SH_RibbonImage" in callbacks
    assert "Application.CommandBars.GetImageMso" in callbacks
    assert 'GetImageMso("Paste", 32, 32)' in callbacks


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
    target_line = (
        'targetPath = tempRoot & Application.PathSeparator & '
        '"shift_helper_report_template.xlsx"'
    )
    assert target_line in embedded
    assert 'zipFolder.ParseName("shift_helper_report_template.xlsx")' in embedded
    assert 'Application.PathSeparator & "report_template.xlsx"' not in embedded
    assert 'DateDiff("s", startedAt, Now) > 20' in embedded
