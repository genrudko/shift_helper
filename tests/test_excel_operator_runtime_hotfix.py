from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VBA = ROOT / "packaging" / "excel_addin" / "vba"


def _source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def _procedure(source: str, signature: str) -> str:
    body = source.split(signature, 1)[1]
    return body.split("End Sub", 1)[0]


def test_selection_change_preserves_native_cut_copy_mode() -> None:
    events = _source("CShiftHelperAppEvents.cls")
    handler = _procedure(events, "Private Sub App_SheetSelectionChange")

    guard = "If Application.CutCopyMode <> False Then Exit Sub"
    prepare = "SH_PrepareQuickInputSelection Sh, Target"
    assert guard in handler
    assert prepare in handler
    assert handler.index(guard) < handler.index(prepare)


def test_lw_gui_badge_reads_shifted_day_d9_without_selection_side_effect() -> None:
    source = _source("modShiftHelperLWGUI.bas")
    events = _source("CShiftHelperAppEvents.cls")
    selection_handler = _procedure(events, "Private Sub App_SheetSelectionChange")

    assert 'SH_HasSheet(wb, "Day")' in source
    assert 'Set wsDay = wb.Worksheets("Day")' in source
    assert 'raw = wsDay.Range("D9").Value2' in source
    assert 'desiredText = passwordText' in source
    assert '"LW GUI: "' not in source
    assert 'Font.Size <> 24' in source
    assert 'Font.Size = 24' in source
    assert "If Application.CutCopyMode <> False Then Exit Sub" in source
    assert "SH_RefreshLWGUIBadge Wb" in events
    assert "SH_RefreshLWGUIBadge" not in selection_handler


def test_current_shift_inspection_is_popup_and_uses_schedule_mapping() -> None:
    source = _source("modShiftHelperShift.bas")
    main = _procedure(source, "Public Sub SH_GotoCurrentInspectionShift")

    assert 'If Hour(Now) < 8 Then' in main
    assert 'effectiveDate = DateAdd("d", -1, Date)' in main
    assert 'ElseIf Hour(Now) < 20 Then' in main
    assert "SH_InspectionKtpList(ws, col)" in main
    assert "MsgBox message, vbInformation" in main
    assert ".Activate" not in main
    assert "Application.Goto" not in main

    assert "Private Function SH_InspectionKtpList" in source
    assert "ws.Cells(2, columnNumber).Value2" in source
    assert "For r = 1 To 4" in source
    assert "SH_LooksLikeKtpList" in source


def test_operator_hotfix_vba_sources_remain_ascii_safe() -> None:
    for name in (
        "CShiftHelperAppEvents.cls",
        "modShiftHelperLWGUI.bas",
        "modShiftHelperShift.bas",
    ):
        (VBA / name).read_text(encoding="ascii")


def test_native_excel_copy_paste_bypasses_sheet_change_quick_input() -> None:
    events = _source("CShiftHelperAppEvents.cls")
    body = events.split("Private Sub App_SheetChange", 1)[1].split("End Sub", 1)[0]
    assert "If Application.CutCopyMode <> False Then Exit Sub" in body
    guard = "If Application.CutCopyMode <> False Then Exit Sub"
    assert body.index(guard) < body.index("SH_HandleQuickInputChange")


def test_workbook_activation_does_not_mutate_during_native_copy_mode() -> None:
    events = _source("CShiftHelperAppEvents.cls")
    body = events.split("Private Sub App_WorkbookActivate", 1)[1].split("End Sub", 1)[0]
    guard = "If Application.CutCopyMode <> False Then Exit Sub"
    assert guard in body
    assert body.index(guard) < body.index("SH_RepairMailButtonBindings")


def test_ribbon_load_does_not_disable_other_excel_addins() -> None:
    ribbon = _source("modShiftHelperRibbon.bas")
    quick = _source("modShiftHelperQuickInput.bas")
    assert "SH_DisableDuplicateAddins" not in ribbon
    assert "SH_DisableDuplicateAddins" not in quick
    assert "addin.Installed = False" not in quick


def test_all_application_events_are_scoped_to_shift_helper_workbooks() -> None:
    events = _source("CShiftHelperAppEvents.cls")
    for signature in (
        "Private Sub App_WorkbookOpen",
        "Private Sub App_WorkbookActivate",
        "Private Sub App_SheetActivate",
        "Private Sub App_SheetSelectionChange",
        "Private Sub App_SheetChange",
    ):
        body = events.split(signature, 1)[1].split("End Sub", 1)[0]
        assert "SH_IsShiftHelperWorkbook" in body, signature


def test_shift_helper_workbook_guard_requires_journal_sheet() -> None:
    compat = _source("modShiftHelperQuickCompat.bas")
    assert "Public Function SH_IsShiftHelperWorkbook(ByVal wb As Workbook) As Boolean" in compat
    assert "If wb Is Nothing Then Exit Function" in compat
    assert "If wb Is ThisWorkbook Then Exit Function" in compat
    assert "If Not SH_HasSheet(wb, SH_JournalSheetName()) Then Exit Function" in compat
    assert "SH_IsShiftHelperWorkbook = True" in compat
