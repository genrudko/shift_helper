Attribute VB_Name = "modShiftHelperReportOutput"
Option Explicit

Public Sub SH_GeneratePreparedReport()
    On Error GoTo Failed
    Dim wb As Workbook, outWb As Workbook, source As Worksheet, target As Worksheet
    Dim seed As Worksheet, reportDate As Date, offsetHours As Double
    Dim outputFolder As String, suggested As String, outputPath As Variant
    Dim i As Long, stage As String, errNumber As Long, errDescription As String
    Dim oldAlerts As Boolean, alertsCaptured As Boolean

    stage = "resolve journal workbook"
    Set wb = SH_JournalBook()

    stage = "prepare report contour"
    SH_EnsureStationReportContour wb
    reportDate = SH_ReportDate(wb)
    offsetHours = SH_ReportOffset(wb)

    stage = "refresh report data"
    SH_RefreshEmergencyOutages wb
    SH_CalculateReportInputs wb

    stage = "create output workbook"
    Set outWb = Workbooks.Add(xlWBATWorksheet)
    Set seed = outWb.Worksheets(1)

    For i = 1 To SH_ReportSheetCount()
        stage = "copy prepared sheet " & CStr(i)
        Set source = SH_RequireSheet(wb, SH_InputSheetName(i))
        source.Copy After:=outWb.Worksheets(outWb.Worksheets.Count)
        Set target = outWb.Worksheets(outWb.Worksheets.Count)
        target.Name = SH_ReportSheetName(i)
        SH_OutputFreezeFormulas source, target
        If i = 5 Then SH_OutputRemoveWtgServiceColumns target
    Next i

    stage = "remove seed sheet"
    oldAlerts = Application.DisplayAlerts
    alertsCaptured = True
    Application.DisplayAlerts = False
    seed.Delete
    Application.DisplayAlerts = oldAlerts

    stage = "apply report captions"
    SH_OutputApplyCaptions outWb, reportDate

    stage = "apply output time offset"
    SH_OutputApplyOffset outWb, offsetHours

    stage = "remove external workbook links"
    SH_OutputBreakLinks outWb

    stage = "validate output workbook"
    SH_OutputValidate outWb

    outputFolder = wb.Path
    If Len(outputFolder) = 0 Then outputFolder = Application.DefaultFilePath
    suggested = outputFolder & Application.PathSeparator & _
        "Shift-Helper-Report-" & Format$(reportDate, "yyyy-mm-dd") & ".xlsx"

    stage = "choose output file"
    outputPath = Application.GetSaveAsFilename( _
        suggested, "Excel Workbook (*.xlsx),*.xlsx", , SH_T("SAVE_REPORT") _
    )
    If VarType(outputPath) = vbBoolean Then
        If outputPath = False Then
            outWb.Close SaveChanges:=False
            Exit Sub
        End If
    End If

    stage = "save output workbook"
    oldAlerts = Application.DisplayAlerts
    alertsCaptured = True
    Application.DisplayAlerts = False
    outWb.SaveAs Filename:=CStr(outputPath), FileFormat:=xlOpenXMLWorkbook
    outWb.Close SaveChanges:=False
    Application.DisplayAlerts = oldAlerts

    stage = "register generated report"
    SH_RegisterGeneratedReport wb, CStr(outputPath)

    MsgBox SH_T("OK_REPORT") & CStr(outputPath), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    On Error Resume Next
    If alertsCaptured Then Application.DisplayAlerts = oldAlerts
    If Not outWb Is Nothing Then outWb.Close SaveChanges:=False
    On Error GoTo 0
    If errNumber = 0 Then errNumber = vbObjectError + 640
    If Len(errDescription) = 0 Then errDescription = "Prepared report export failed."
    MsgBox SH_T("ERR_REPORT") & "[#" & CStr(errNumber) & "] Stage [" & stage & "]: " & _
        errDescription, vbExclamation, "Shift-Helper"
End Sub

Private Sub SH_OutputFreezeFormulas(ByVal source As Worksheet, ByVal target As Worksheet)
    On Error GoTo Failed
    Dim formulas As Range, cell As Range, sourceCell As Range

    On Error Resume Next
    Set formulas = target.UsedRange.SpecialCells(xlCellTypeFormulas)
    On Error GoTo Failed
    If formulas Is Nothing Then Exit Sub

    For Each cell In formulas.Cells
        Set sourceCell = source.Range(cell.Address)
        cell.Value = sourceCell.Value
    Next cell
    Exit Sub
Failed:
    Err.Raise Err.Number, , "Could not freeze report formulas: " & Err.Description
End Sub

Private Sub SH_OutputRemoveWtgServiceColumns(ByVal target As Worksheet)
    If StrComp(Trim$(SH_OutputSafeText(target.Range("L3").Value2)), _
        SH_U("04210442043004420443044100200412042D0423"), vbTextCompare) = 0 Then
        target.Columns(12).Delete
    End If
End Sub

Private Sub SH_OutputApplyCaptions(ByVal wb As Workbook, ByVal reportDate As Date)
    Dim main As Worksheet, ws As Worksheet, i As Long, value As String
    Dim generatedAt As Date
    generatedAt = Now

    Set main = wb.Worksheets(SH_ReportSheetName(1))
    value = SH_OutputSafeText(main.Range("B1").Value2)
    value = SH_OutputReplaceFirst(value, "dd.mm.yyyy", Format$(reportDate, "dd.mm.yyyy"))
    value = SH_OutputReplaceFirst(value, "dd.mm.yyyy", Format$(generatedAt, "dd.mm.yyyy"))
    value = Replace(value, "hh:mm:ss", Format$(generatedAt, "hh:mm:ss"), 1, -1, vbTextCompare)
    main.Range("B1").Value = value

    SH_OutputReplaceDateCell main.Range("B6"), DateAdd("d", -1, reportDate)
    SH_OutputReplaceDateCell main.Range("B7"), reportDate
    SH_OutputReplaceDateCell main.Range("B10"), DateAdd("d", -1, reportDate)
    SH_OutputReplaceDateCell main.Range("B12"), reportDate
    SH_OutputReplaceDateCell main.Range("E9"), reportDate
    SH_OutputReplaceDateCell main.Range("E14"), reportDate
    SH_OutputReplaceDateCell main.Range("H18"), reportDate

    For i = 2 To SH_ReportSheetCount()
        Set ws = wb.Worksheets(SH_ReportSheetName(i))
        SH_OutputReplaceDateCell ws.Range("B1"), reportDate
    Next i
End Sub

Private Sub SH_OutputReplaceDateCell(ByVal target As Range, ByVal value As Date)
    Dim text As String
    text = SH_OutputSafeText(target.Value2)
    text = Replace(text, "dd.mm.yyyy", Format$(value, "dd.mm.yyyy"), 1, -1, vbTextCompare)
    target.Value = text
End Sub

Private Function SH_OutputReplaceFirst(ByVal text As String, ByVal token As String, _
    ByVal replacement As String) As String
    Dim position As Long
    position = InStr(1, text, token, vbTextCompare)
    If position = 0 Then
        SH_OutputReplaceFirst = text
    Else
        SH_OutputReplaceFirst = Left$(text, position - 1) & replacement & _
            Mid$(text, position + Len(token))
    End If
End Function

Private Function SH_OutputSafeText(ByVal value As Variant) As String
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    SH_OutputSafeText = CStr(value)
    Exit Function
Failed:
    SH_OutputSafeText = ""
End Function

Private Sub SH_OutputApplyOffset(ByVal wb As Workbook, ByVal offsetHours As Double)
    If offsetHours = 0 Then Exit Sub
    SH_OutputShiftColumns wb.Worksheets(SH_ReportSheetName(2)), Array("C", "F"), 4, offsetHours
    SH_OutputShiftColumns wb.Worksheets(SH_ReportSheetName(3)), Array("E", "F"), 4, offsetHours
    SH_OutputShiftColumns wb.Worksheets(SH_ReportSheetName(4)), Array("D"), 3, offsetHours
    SH_OutputShiftColumns wb.Worksheets(SH_ReportSheetName(5)), Array("J", "K"), 4, offsetHours
    SH_OutputShiftColumns wb.Worksheets(SH_ReportSheetName(6)), Array("I", "J"), 4, offsetHours
    SH_OutputShiftColumns wb.Worksheets(SH_ReportSheetName(7)), Array("C", "I", "J"), 4, offsetHours
End Sub

Private Sub SH_OutputShiftColumns(ByVal ws As Worksheet, ByVal columns As Variant, _
    ByVal firstRow As Long, ByVal offsetHours As Double)
    Dim columnName As Variant, rowNumber As Long, lastRow As Long
    Dim raw As Variant, serial As Double
    lastRow = ws.UsedRange.Row + ws.UsedRange.Rows.Count - 1
    For Each columnName In columns
        For rowNumber = firstRow To lastRow
            raw = ws.Range(CStr(columnName) & rowNumber).Value2
            If SH_OutputTrySerial(raw, serial) Then
                ws.Range(CStr(columnName) & rowNumber).Value2 = serial + offsetHours / 24#
            End If
        Next rowNumber
    Next columnName
End Sub

Private Function SH_OutputTrySerial(ByVal value As Variant, ByRef serial As Double) As Boolean
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If VarType(value) = vbString Then
        If Len(Trim$(CStr(value))) = 0 Then Exit Function
    End If
    If IsNumeric(value) Then
        serial = CDbl(value)
        SH_OutputTrySerial = True
    ElseIf IsDate(value) Then
        serial = CDbl(CDate(value))
        SH_OutputTrySerial = True
    End If
    Exit Function
Failed:
    SH_OutputTrySerial = False
End Function

Private Sub SH_OutputBreakLinks(ByVal wb As Workbook)
    On Error Resume Next
    Dim links As Variant, link As Variant
    links = wb.LinkSources(xlExcelLinks)
    If IsArray(links) Then
        For Each link In links
            wb.BreakLink Name:=CStr(link), Type:=xlLinkTypeExcelLinks
        Next link
    End If
    On Error GoTo 0
End Sub

Private Sub SH_OutputValidate(ByVal wb As Workbook)
    Dim i As Long, wtg As Worksheet
    If wb.Worksheets.Count <> SH_ReportSheetCount() Then
        Err.Raise vbObjectError + 641, , "Output report must contain exactly seven worksheets."
    End If
    For i = 1 To SH_ReportSheetCount()
        If wb.Worksheets(i).Name <> SH_ReportSheetName(i) Then
            Err.Raise vbObjectError + 642, , "Output report worksheet order mismatch."
        End If
    Next i

    Set wtg = wb.Worksheets(SH_ReportSheetName(5))
    If StrComp(Trim$(SH_OutputSafeText(wtg.Range("L3").Value2)), _
        SH_U("04210442043004420443044100200412042D0423"), vbTextCompare) = 0 Then
        Err.Raise vbObjectError + 643, , "WTG status service column must not be exported."
    End If
End Sub
