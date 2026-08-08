Attribute VB_Name = "modShiftHelperJournal"
Option Explicit

Public Sub SH_SortJournalByTime()
    On Error GoTo Failed
    Dim wb As Workbook, ws As Worksheet, selected As Range
    Dim firstRow As Long, lastRow As Long, lastCol As Long, sortRange As Range
    Set wb = SH_JournalBook()
    Set ws = SH_RequireSheet(wb, SH_JournalSheetName())

    firstRow = 2
    lastRow = Application.Max(SH_LastRow(ws, 2), SH_LastRow(ws, 3))
    If TypeName(Selection) = "Range" Then
        Set selected = Selection
        If selected.Worksheet.Parent Is wb Then
            If selected.Worksheet.Name = ws.Name And selected.Rows.Count > 1 Then
                firstRow = Application.Max(2, selected.Row)
                lastRow = Application.Min(lastRow, selected.Row + selected.Rows.Count - 1)
            End If
        End If
    End If
    If lastRow <= firstRow Then Exit Sub
    lastCol = ws.Cells(1, ws.Columns.Count).End(xlToLeft).Column
    If lastCol < 10 Then lastCol = 10
    Set sortRange = ws.Range(ws.Cells(firstRow, 1), ws.Cells(lastRow, lastCol))
    With ws.Sort
        .SortFields.Clear
        .SortFields.Add Key:=ws.Range("B" & firstRow & ":B" & lastRow), SortOn:=xlSortOnValues, Order:=xlAscending, DataOption:=xlSortNormal
        .SortFields.Add Key:=ws.Range("C" & firstRow & ":C" & lastRow), SortOn:=xlSortOnValues, Order:=xlAscending, DataOption:=xlSortNormal
        .SetRange sortRange
        .Header = xlNo
        .MatchCase = False
        .Orientation = xlTopToBottom
        .Apply
    End With
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_MergeAndCopy()
    On Error GoTo Failed
    Dim wb As Workbook, target As Range, cell As Range, merged As String, part As String
    Set wb = SH_JournalBook()
    Set target = SH_SelectionRange(wb)
    For Each cell In target.Cells
        If cell.MergeCells Then
            If cell.Address <> cell.MergeArea.Cells(1, 1).Address Then GoTo NextCell
        End If
        part = SH_NormalizeSpaces(cell.Value2)
        If Len(part) > 0 Then
            If Len(merged) > 0 Then merged = merged & " "
            merged = merged & part
        End If
NextCell:
    Next cell
    If Not SH_CopyUnicodeText(merged) Then Err.Raise vbObjectError + 521, , SH_T("ERR_COPY")
    MsgBox SH_T("OK_COPY"), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_CleanSpaces()
    On Error GoTo Failed
    Dim wb As Workbook, target As Range, cell As Range
    Set wb = SH_JournalBook()
    Set target = SH_SelectionRange(wb)
    For Each cell In target.Cells
        If Not cell.HasFormula And VarType(cell.Value2) = vbString Then cell.Value = SH_NormalizeSpaces(cell.Value2)
    Next cell
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_SetRowHeight()
    On Error GoTo Failed
    Dim wb As Workbook, target As Range, answer As Variant, heightValue As Double
    Set wb = SH_JournalBook()
    Set target = SH_SelectionRange(wb)
    answer = Application.InputBox(SH_T("ROW_HEIGHT_PROMPT"), SH_T("ROW_HEIGHT_TITLE"), 18, Type:=1)
    If VarType(answer) = vbBoolean Then If answer = False Then Exit Sub
    heightValue = CDbl(answer)
    If heightValue < 5 Or heightValue > 200 Then Err.Raise vbObjectError + 524, , "5..200"
    target.EntireRow.RowHeight = heightValue
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub
