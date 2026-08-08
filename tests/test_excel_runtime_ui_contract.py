from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
VBA = ROOT / "packaging" / "excel_addin" / "vba"
RIBBON = ROOT / "packaging" / "excel_addin" / "customUI14.xml"
NS = {"ui": "http://schemas.microsoft.com/office/2009/07/customui"}


def _source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def test_calendar_is_native_owned_popup_without_workbook_or_subclassing() -> None:
    calendar = _source("modShiftHelperCalendar.bas")
    callbacks = _source("modShiftHelperRibbon.bas")
    root = ET.parse(RIBBON).getroot()
    control = root.find(".//ui:button[@id='btnCalendar']", NS)
    assert control is not None
    assert control.attrib["onAction"] == "SH_RibbonCalendar"
    assert "Workbooks.Add" not in calendar
    assert 'calendarClass = "SysMonthCal32"' in calendar
    assert "CreateWindowExW" in calendar
    assert "SH_MCM_GETCURSEL" in calendar
    assert "GetAsyncKeyState" in calendar
    assert "SetWindowLongPtr" not in calendar
    assert "CallWindowProc" not in calendar
    assert "AddressOf" not in calendar
    assert "SH_EnsureReportContour wb" not in calendar
    assert "Set prep = SH_EnsurePrepSheet(wb)" in calendar
    assert "Public Sub SH_InsertDateIntoSelection" in calendar
    assert "Public Sub SH_RibbonCalendar" in callbacks
    assert "Public Sub SH_RibbonInsertDate" in callbacks


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
    assert root.attrib["onLoad"] == "SH_RibbonOnLoad"
    assert "Public Sub SH_RibbonOnLoad" in callbacks
    assert "Public Sub SH_RibbonImage" in callbacks
    assert "Application.CommandBars.GetImageMso" in callbacks
    assert 'GetImageMso("Paste", 32, 32)' in callbacks


def test_calc_operator_tool_parity_is_exposed_on_excel_ribbon() -> None:
    root = ET.parse(RIBBON).getroot()
    callbacks = _source("modShiftHelperRibbon.bas")
    required = {
        "btnSort": "SH_RibbonSort",
        "btnMergeCopy": "SH_RibbonMergeCopy",
        "btnClean": "SH_RibbonCleanSpaces",
        "btnRows": "SH_RibbonAutoFitRows",
        "btnInsertDate": "SH_RibbonInsertDate",
        "btnTime": "SH_RibbonTime",
        "btnPrepare": "SH_RibbonPrepare",
        "btnCalendar": "SH_RibbonCalendar",
        "btnGenerate": "SH_RibbonGenerate",
        "btnGeneration": "SH_RibbonImportGeneration",
        "btnMailDraft": "SH_RibbonMailDraft",
        "btnMaintenance": "SH_RibbonMaintenance",
        "btnRotor": "SH_RibbonRotorLimits",
        "btnShift": "SH_RibbonCurrentShift",
        "btnQuickOn": "SH_RibbonQuickOn",
        "btnQuickStatus": "SH_RibbonQuickStatus",
        "btnQuickOff": "SH_RibbonQuickOff",
    }
    for control_id, callback in required.items():
        control = root.find(f".//ui:button[@id='{control_id}']", NS)
        assert control is not None, control_id
        assert control.attrib["onAction"] == callback
        assert f"Public Sub {callback}" in callbacks


def test_report_bootstrap_extracts_template_only_when_input_form_is_missing() -> None:
    report = _source("modShiftHelperReport.bas")
    util = _source("modShiftHelperUtil.bas")
    outlook = _source("modShiftHelperOutlook.bas")
    rotor = _source("modShiftHelperRotor.bas")
    assert "Public Sub SH_EnsureReportContour" in report
    assert "Set prep = SH_EnsurePrepSheet(wb)" in report
    assert "needsTemplate" in report
    assert "If needsTemplate Then" in report
    assert "templatePath = SH_ExtractEmbeddedReportTemplate()" in report
    assert report.index("If needsTemplate Then") < report.index(
        "templatePath = SH_ExtractEmbeddedReportTemplate()"
    )
    assert "SH_EnsureReportContour wb" in outlook
    assert "SH_EnsureReportContour wb" in rotor
    assert "Public Function SH_EnsurePrepSheet" in util
    assert "Public Function SH_RequireSheet" in util


def test_report_formulas_include_dynamic_titles_and_accepted_status_order() -> None:
    report = _source("modShiftHelperReport.bas")
    assert 'main.Range("B1").Formula' in report
    assert 'main.Range("B6").Formula' in report
    assert 'main.Range("B7").Formula' in report
    assert 'main.Range("B10").Formula' in report
    assert 'main.Range("B12").Formula' in report
    assert 'main.Range("E9").Formula' in report
    assert 'main.Range("E14").Formula' in report
    assert 'main.Range("H3").Formula' in report
    assert 'main.Range("H18").Formula' in report
    assert 'main.Range("C6").Formula = "=IFERROR(C10/24000,0)"' in report
    assert 'main.Range("F4").Formula' in report and "SH_StatusText(2)" in report
    assert 'main.Range("F5").Formula' in report and "SH_StatusText(1)" in report


def test_embedded_report_template_runtime_does_not_depend_on_explorer_zip_shell() -> None:
    embedded = _source("modShiftHelperEmbedded.bas")
    assert "SH_EmbeddedTemplateBase64()" in embedded
    assert 'CreateObject("MSXML2.DOMDocument.6.0")' in embedded
    assert 'CreateObject("ADODB.Stream")' in embedded
    assert "Shell.Application" not in embedded
    assert "ParseName" not in embedded
    assert "FileCopy ThisWorkbook.FullName" not in embedded
    assert 'targetPath = tempRoot & Application.PathSeparator & "shift_helper_report_template.xlsx"' in embedded


def test_quick_input_uses_application_events_and_covers_accepted_journal_columns() -> None:
    event_class = _source("CShiftHelperAppEvents.cls")
    quick = _source("modShiftHelperQuickInput.bas")
    callbacks = _source("modShiftHelperRibbon.bas")
    assert "Public WithEvents App As Application" in event_class
    assert "App_SheetSelectionChange" in event_class
    assert "App_SheetChange" in event_class
    assert "Public SH_AppEvents As CShiftHelperAppEvents" in quick
    assert "SH_InitializeAddin" in quick
    assert "col = 2 Or col = 3 Or col = 9 Or col = 10" in quick
    assert 'If token = "." Then' in quick
    assert 'If token = "!" Then' in quick
    assert 'Left$(token, 1) = "+"' in quick
    assert "dayOffset" in quick
    assert "Application.EnableEvents = False" in quick
    assert "SaveSetting" in quick
    assert "Public Sub SH_RibbonQuickOn" in callbacks
    assert "Public Sub SH_RibbonQuickOff" in callbacks


def test_sort_matches_accepted_a_to_r_time_contract_and_freezes_formula_columns() -> None:
    journal = _source("modShiftHelperJournal.bas")
    assert 'ws.Range("A" & firstRow & ":R" & lastRow)' in journal
    assert 'Key:=temp.Range("C1:C" & rowCount)' in journal
    assert "Application.ConvertFormula" in journal
    assert "xlAbsolute" in journal
    assert "Array(11, 14, 15, 16, 17, 18)" in journal
    assert "xlSheetVeryHidden" in journal
    assert 'temp.Range("A1:S" & rowCount)' in journal


def test_maintenance_text_and_outlook_draft_tools_are_present() -> None:
    tools = _source("modShiftHelperTools.bas")
    assert "Public Sub SH_InsertMaintenanceText" in tools
    assert "Private Function SH_MaintenanceText" in tools
    assert "target.EntireRow.AutoFit" in tools
    assert "Public Sub SH_CreateOutlookDraft" in tools
    assert "mail.SentOnBehalfOfName" in tools
    assert "mail.HTMLBody" in tools
    assert "mail.Attachments.Add" in tools
    assert "mail.Display" in tools
    assert "mail.Send" not in tools
    assert "Public Sub SH_ShowTimePicker" in tools


def test_service_metadata_has_safe_missing_prep_behavior() -> None:
    meta = _source("modShiftHelperMeta.bas")
    assert "If Not SH_HasSheet(wb, SH_PrepSheetName()) Then Exit Function" in meta
    assert "Set ws = SH_EnsurePrepSheet(wb)" in meta


def test_selection_tools_cannot_mutate_a_transient_or_foreign_workbook() -> None:
    journal = _source("modShiftHelperJournal.bas")
    util = _source("modShiftHelperUtil.bas")
    assert journal.count("SH_SelectionRange(wb)") == 4
    assert "Public Function SH_SelectionRange" in util
    assert "ERR_SELECTION_BOOK" in util


def test_inspection_navigation_reports_missing_sheet_through_shared_guard() -> None:
    shift = _source("modShiftHelperShift.bas")
    assert "Set ws = SH_RequireSheet(wb, SH_InspectionSheetName())" in shift
