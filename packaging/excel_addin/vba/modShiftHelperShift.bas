Attribute VB_Name = "modShiftHelperShift"
Option Explicit

Public Sub SH_GotoCurrentInspectionShift()
    On Error GoTo Failed
    Dim wb As Workbook, ws As Worksheet, found As Range, wanted As String, r As Long, targetRow As Long
    Set wb = SH_JournalBook()
    Set ws = wb.Worksheets(SH_InspectionSheetName())
    If Hour(Now) >= 8 And Hour(Now) < 20 Then wanted = SH_T("SHIFT_DAY") Else wanted = SH_T("SHIFT_NIGHT")
    Set found = ws.UsedRange.Find(What:=CDbl(Date), LookIn:=xlValues, LookAt:=xlWhole, SearchOrder:=xlByRows)
    If found Is Nothing Then GoTo NotFound
    targetRow = found.Row
    For r = Application.Max(1, found.Row - 1) To Application.Min(ws.Rows.Count, found.Row + 2)
        If Application.WorksheetFunction.CountIf(ws.Rows(r), wanted) > 0 Then targetRow = r: Exit For
    Next r
    ws.Activate
    ws.Rows(targetRow).Select
    Application.Goto ws.Cells(targetRow, 1), True
    Exit Sub
NotFound:
    MsgBox SH_T("SHIFT_NOT_FOUND"), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub
