Attribute VB_Name = "modShiftHelperJournal"
Option Explicit

Public Sub SH_SortJournalByTime()
    On Error GoTo Failed
    Dim wb As Workbook, ws As Worksheet, selected As Range, helperRange As Range
    Dim firstRow As Long, lastRow As Long, rowCount As Long, r As Long, col As Variant
    Dim sortRange As Range, formulaText As String, converted As Variant
    Dim hadEvents As Boolean, errDescription As String

    hadEvents = Application.EnableEvents
    Set wb = SH_JournalBook()
    Set ws = SH_RequireSheet(wb, SH_JournalSheetName())
    Set selected = SH_SelectionRange(wb)
    If selected.Worksheet.Name <> ws.Name Then Err.Raise vbObjectError + 518, , SH_T("ERR_SELECTION")
    firstRow = Application.Max(2, selected.Row)
    lastRow = selected.Row + selected.Rows.Count - 1
    If lastRow <= firstRow Then Err.Raise vbObjectError + 519, , SH_U("0412044B04340435043B043804420435002004340432043500200438043B043800200431043E043B044C044804350020044104420440043E043A002E")
    rowCount = lastRow - firstRow + 1
    Set helperRange = ws.Range("S" & firstRow & ":S" & lastRow)

    Application.EnableEvents = False

    For Each col In Array(11, 14, 15, 16, 17, 18)
        For r = firstRow To lastRow
            If ws.Cells(r, CLng(col)).HasFormula Then
                formulaText = CStr(ws.Cells(r, CLng(col)).Formula)
                On Error Resume Next
                converted = Application.ConvertFormula(formulaText, xlA1, xlA1, xlAbsolute)
                If Err.Number = 0 And VarType(converted) = vbString Then ws.Cells(r, CLng(col)).Formula = CStr(converted)
                Err.Clear
                On Error GoTo Failed
            End If
        Next r
    Next col

    For r = 1 To rowCount
        helperRange.Cells(r, 1).Value2 = r
    Next r
    Set sortRange = ws.Range("A" & firstRow & ":S" & lastRow)
    With ws.Sort
        .SortFields.Clear
        .SortFields.Add Key:=ws.Range("C" & firstRow & ":C" & lastRow), SortOn:=xlSortOnValues, Order:=xlAscending, DataOption:=xlSortNormal
        .SortFields.Add Key:=helperRange, SortOn:=xlSortOnValues, Order:=xlAscending, DataOption:=xlSortNormal
        .SetRange sortRange
        .Header = xlNo
        .MatchCase = False
        .Orientation = xlTopToBottom
        .Apply
    End With
    helperRange.ClearContents
    Application.EnableEvents = hadEvents
    ws.Activate
    ws.Range("A" & firstRow & ":R" & lastRow).Select
    Exit Sub
Failed:
    errDescription = Err.Description
    On Error Resume Next
    If Not helperRange Is Nothing Then helperRange.ClearContents
    Application.EnableEvents = hadEvents
    On Error GoTo 0
    If Len(errDescription) = 0 Then errDescription = "Journal sort failed."
    MsgBox errDescription, vbExclamation, "Shift-Helper"
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
    target.EntireRow.AutoFit
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
    target.EntireRow.AutoFit
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_AutoFitRows()
    On Error GoTo Failed
    Dim wb As Workbook, target As Range, area As Range
    Set wb = SH_JournalBook()
    Set target = SH_SelectionRange(wb)
    For Each area In target.Areas
        area.EntireRow.AutoFit
    Next area
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub
