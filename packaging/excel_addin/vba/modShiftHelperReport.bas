Attribute VB_Name = "modShiftHelperReport"
Option Explicit

Public Sub SH_PrepareReportContour()
    On Error GoTo Failed
    Dim wb As Workbook, template As Workbook, templatePath As String
    Dim i As Long, inputName As String, reportName As String
    Set wb = SH_JournalBook()
    If Not SH_HasSheet(wb, SH_PrepSheetName()) Then Err.Raise vbObjectError + 530, , SH_T("SHEET_MISSING") & SH_PrepSheetName()
    templatePath = SH_ExtractEmbeddedReportTemplate()
    Set template = Workbooks.Open(Filename:=templatePath, UpdateLinks:=0, ReadOnly:=True, AddToMru:=False)
    For i = 1 To SH_ReportSheetCount()
        inputName = SH_InputSheetName(i)
        reportName = SH_ReportSheetName(i)
        If Not SH_HasSheet(wb, inputName) Then
            template.Worksheets(reportName).Copy After:=wb.Worksheets(wb.Worksheets.Count)
            wb.Worksheets(wb.Worksheets.Count).Name = inputName
        End If
    Next i
    template.Close SaveChanges:=False
    SH_ApplyCriticalFormulas wb
    SH_RefreshEmergencyOutages wb
    wb.Calculate
    MsgBox SH_T("OK_PREP") & vbCrLf & SH_T("NO_TEMPLATE_PICK"), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    On Error Resume Next
    If Not template Is Nothing Then template.Close SaveChanges:=False
    On Error GoTo 0
    MsgBox SH_T("ERR_PREP") & Err.Description, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_ApplyCriticalFormulas(ByVal wb As Workbook)
    Dim main As Worksheet, state As Worksheet, works As Worksheet
    Dim groups As Collection, r As Long, lastRow As Long, i As Long
    Dim groupRow As Long, firstChild As Long, lastChild As Long, nextGroup As Long
    Dim col As Variant, q As String
    q = Chr$(34)
    Set main = wb.Worksheets(SH_InputSheetName(1))
    Set state = wb.Worksheets(SH_InputSheetName(5))
    Set works = wb.Worksheets(SH_InputSheetName(6))
    SH_EnsureStatusColumn state

    main.Range("C6").Formula = "=IFERROR(C10/24000,0)"
    main.Range("C6").NumberFormat = "0.00"
    main.Range("C12").Formula = "=INDEX(I5:I16,MONTH('" & SH_PrepSheetName() & "'!B3))*(DAY('" & SH_PrepSheetName() & "'!B3)-1)/DAY(EOMONTH('" & SH_PrepSheetName() & "'!B3,0))"
    main.Range("C13").Formula = "=C11-C12"
    main.Range("C14").Formula = "=IFERROR(C11/C12,0)"
    main.Range("C15").Formula = "=IFERROR(IF(C13>=0,-1,(INDEX(I5:I16,MONTH('" & SH_PrepSheetName() & "'!B3))-C11)/((DAY(EOMONTH('" & SH_PrepSheetName() & "'!B3,0))-DAY('" & SH_PrepSheetName() & "'!B3)+1)*24)),0)"
    main.Range("C15").NumberFormat = "0.0"

    For r = 5 To 16
        main.Cells(r, 11).Formula = "=IF(J" & r & "=" & q & q & "," & q & q & ",J" & r & "-I" & r & ")"
        main.Cells(r, 12).Formula = "=IFERROR(J" & r & "/I" & r & "," & q & q & ")"
    Next r
    main.Range("I17").Formula = "=SUM(I5:I16)"
    main.Range("J17").Formula = "=SUM(J5:J16)"
    main.Range("K17").Formula = "=J17-I17"
    main.Range("L17").Formula = "=IFERROR(J17/I17," & q & q & ")"
    main.Range("I18").Formula = "=SUMPRODUCT(I5:I16,--(ROW(I5:I16)-ROW(I5)+1<MONTH('" & SH_PrepSheetName() & "'!B3)))+INDEX(I5:I16,MONTH('" & SH_PrepSheetName() & "'!B3))*(DAY('" & SH_PrepSheetName() & "'!B3)-1)/DAY(EOMONTH('" & SH_PrepSheetName() & "'!B3,0))"
    main.Range("J18").Formula = "=SUMPRODUCT(J5:J16,--(ROW(J5:J16)-ROW(J5)+1<=MONTH('" & SH_PrepSheetName() & "'!B3)))"
    main.Range("K18").Formula = "=J18-I18"
    main.Range("L18").Formula = "=IFERROR(J18/I18," & q & q & ")"

    Set groups = New Collection
    lastRow = Application.Max(SH_LastRow(state, 3), SH_LastRow(state, 4), 98)
    For r = 4 To lastRow
        If Len(CStr(state.Cells(r, 3).Value2)) > 0 And Len(CStr(state.Cells(r, 4).Value2)) = 0 Then
            groups.Add r
        ElseIf Left$(CStr(state.Cells(r, 4).Value2), 4) = SH_U("0412042D0423002D") Then
            state.Cells(r, 8).Formula = "=MAX(F" & r & "-G" & r & ",0)"
            If Not SH_ValidStatus(CStr(state.Cells(r, 12).Value2)) Then state.Cells(r, 12).Value = SH_InferStatus(state, r)
        End If
    Next r
    For i = 1 To groups.Count
        groupRow = CLng(groups(i))
        firstChild = groupRow + 1
        If i < groups.Count Then nextGroup = CLng(groups(i + 1)) Else nextGroup = lastRow + 1
        lastChild = nextGroup - 1
        For Each col In Array("E", "F", "G", "H")
            state.Range(CStr(col) & groupRow).Formula = "=SUM(" & CStr(col) & firstChild & ":" & CStr(col) & lastChild & ")"
        Next col
    Next i
    If groups.Count > 0 Then
        main.Range("C3").Formula = SH_GroupSumFormula(state.Name, "E", groups)
        main.Range("C4").Formula = SH_GroupSumFormula(state.Name, "H", groups)
    End If
    For i = 1 To 4
        main.Cells(i + 3, 6).Formula = "=COUNTIF('" & state.Name & "'!L4:L98," & q & SH_StatusText(i) & q & ")"
    Next i

    lastRow = Application.Max(SH_LastRow(works, 4), SH_LastRow(works, 5), 200)
    For r = 4 To lastRow
        works.Cells(r, 7).Formula = "=IF(COUNTA(E" & r & ":F" & r & ")=0," & q & q & ",MAX(E" & r & "-F" & r & ",0))"
    Next r
End Sub

Private Sub SH_EnsureStatusColumn(ByVal state As Worksheet)
    Dim r As Long, lastRow As Long
    lastRow = Application.Max(SH_LastRow(state, 4), 98)
    If CStr(state.Cells(3, 12).Value2) <> SH_U("04210442043004420443044100200412042D0423") Then
        state.Range("K3:K" & lastRow).Copy
        state.Range("L3:L" & lastRow).PasteSpecial Paste:=xlPasteFormats
        Application.CutCopyMode = False
        state.Columns(12).ColumnWidth = 16
        state.Cells(3, 12).Value = SH_U("04210442043004420443044100200412042D0423")
    End If
    For r = 4 To lastRow
        If Left$(CStr(state.Cells(r, 4).Value2), 4) <> SH_U("0412042D0423002D") Then state.Cells(r, 12).ClearContents
    Next r
End Sub

Private Function SH_ValidStatus(ByVal value As String) As Boolean
    Dim i As Long
    For i = 1 To 4
        If StrComp(Trim$(value), SH_StatusText(i), vbTextCompare) = 0 Then SH_ValidStatus = True: Exit Function
    Next i
End Function

Private Function SH_InferStatus(ByVal state As Worksheet, ByVal r As Long) As String
    Dim reason As String, available As Double, repair As Double
    reason = LCase$(CStr(state.Cells(r, 9).Value2))
    available = Val(CStr(state.Cells(r, 8).Value2))
    repair = Val(CStr(state.Cells(r, 7).Value2))
    If InStr(reason, SH_U("0430043204300440")) > 0 Or InStr(reason, SH_U("043E0442043A04300437")) > 0 Or InStr(reason, SH_U("043F043E04320440043504360434")) > 0 Or InStr(reason, SH_U("043D043504380441043F044004300432")) > 0 Or InStr(reason, SH_U("043E044804380431043A")) > 0 Then
        SH_InferStatus = SH_StatusText(3)
    ElseIf InStr(reason, SH_U("04400435043C043E043D0442")) > 0 Then
        SH_InferStatus = SH_StatusText(4)
    ElseIf InStr(reason, SH_U("044204350445043D0438044704350441043A043E04350020043E04310441043B04430436043804320430043D04380435")) > 0 Or InStr(reason, SH_U("043F043B0430043D043E0432044B04350020044004300431043E0442044B")) > 0 Or InStr(reason, SH_U("0434043B044F0020043F0440043E0432043504340435043D0438044F0020044004300431043E0442")) > 0 Or InStr(reason, SH_U("044004350432043804370438044F")) > 0 Then
        SH_InferStatus = SH_StatusText(2)
    ElseIf available > 0 Then
        SH_InferStatus = SH_StatusText(1)
    ElseIf repair > 0 And Len(reason) = 0 Then
        SH_InferStatus = SH_StatusText(4)
    Else
        SH_InferStatus = SH_StatusText(2)
    End If
End Function

Private Function SH_GroupSumFormula(ByVal sheetName As String, ByVal col As String, ByVal rows As Collection) As String
    Dim i As Long, result As String
    result = "=SUM("
    For i = 1 To rows.Count
        If i > 1 Then result = result & ","
        result = result & "'" & sheetName & "'!" & col & rows(i)
    Next i
    SH_GroupSumFormula = result & ")"
End Function

Public Function SH_RefreshEmergencyOutages(ByVal wb As Workbook) As Long
    Dim source As Worksheet, target As Worksheet, reportDate As Date, windowStart As Date, windowEnd As Date
    Dim lastRow As Long, r As Long, outRow As Long, eventTime As Variant, endTime As Variant
    Dim description As String, reason As String, asset As String
    Set source = wb.Worksheets(SH_JournalSheetName())
    Set target = wb.Worksheets(SH_InputSheetName(2))
    reportDate = SH_ReportDate(wb)
    windowEnd = DateSerial(Year(reportDate), Month(reportDate), Day(reportDate)) + TimeSerial(7, 0, 0)
    windowStart = windowEnd - 1
    target.Range("B4:F" & Application.Max(200, SH_LastRow(target, 2))).ClearContents
    lastRow = Application.Max(SH_LastRow(source, 2), SH_LastRow(source, 3))
    outRow = 4
    For r = 2 To lastRow
        eventTime = SH_CellDateTime(source, r)
        If Not IsEmpty(eventTime) Then
            If CDbl(eventTime) >= CDbl(windowStart) And CDbl(eventTime) < CDbl(windowEnd) Then
                description = Trim$(CStr(source.Cells(r, 5).Value2))
                reason = Trim$(CStr(source.Cells(r, 6).Value2))
                If SH_SelectEmergency(description, reason) Then
                    asset = CStr(source.Cells(r, 4).Value2)
                    target.Cells(outRow, 2).Value = SH_U("0412042D042300202116") & asset
                    target.Cells(outRow, 3).Value2 = CDbl(eventTime)
                    target.Cells(outRow, 3).NumberFormat = "dd.mm.yyyy hh:mm"
                    target.Cells(outRow, 4).Value = reason
                    target.Cells(outRow, 5).Value = description
                    endTime = SH_EndDateTime(source, r)
                    If Not IsEmpty(endTime) Then target.Cells(outRow, 6).Value2 = CDbl(endTime): target.Cells(outRow, 6).NumberFormat = "dd.mm.yyyy hh:mm"
                    outRow = outRow + 1
                End If
            End If
        End If
    Next r
    SH_RefreshEmergencyOutages = outRow - 4
End Function

Private Function SH_SelectEmergency(ByVal description As String, ByVal reason As String) As Boolean
    Dim eText As String, fText As String, marker As Variant
    eText = LCase$(Trim$(description))
    fText = LCase$(Trim$(reason))
    If Len(fText) = 0 Or fText = "-" Then Exit Function
    If eText = "-" Then Exit Function
    For Each marker In Array( _
        SH_U("043E044104420430043D043E0432043B0435043D0430"), _
        SH_U("0434043B044F0020044004300431043E0442"), _
        SH_U("044004300431043E0442044B0020043F043E"), _
        SH_U("044004300431043E04420020043F043E"), _
        SH_U("043F043504400435043A043B044E04470435043D04380439"))
        If InStr(1, eText, CStr(marker), vbTextCompare) > 0 Then Exit Function
    Next marker
    If InStr(1, eText, SH_U("043E044804380431043A0430002004320020044004300431043E04420435"), vbTextCompare) > 0 Then SH_SelectEmergency = True: Exit Function
    If InStr(1, eText, SH_U("04320020044004300431043E04420435"), vbTextCompare) > 0 Then Exit Function
    SH_SelectEmergency = True
End Function

Private Function SH_EndDateTime(ByVal ws As Worksheet, ByVal rowNumber As Long) As Variant
    Dim d As Variant, t As Variant
    d = ws.Cells(rowNumber, 9).Value2
    t = ws.Cells(rowNumber, 10).Value2
    If (IsDate(d) Or IsNumeric(d)) And (IsDate(t) Or IsNumeric(t)) Then
        SH_EndDateTime = Int(CDbl(d)) + (CDbl(t) - Int(CDbl(t)))
    Else
        SH_EndDateTime = Empty
    End If
End Function

Public Sub SH_GenerateFullReport()
    On Error GoTo Failed
    Dim wb As Workbook, outWb As Workbook, templatePath As String, i As Long
    Dim reportDate As Date, offsetHours As Double, suggested As String, outputPath As Variant
    Set wb = SH_JournalBook()
    SH_PrepareReportContour
    reportDate = SH_ReportDate(wb)
    offsetHours = SH_ReportOffset(wb)
    SH_RefreshEmergencyOutages wb
    wb.Calculate
    templatePath = SH_ExtractEmbeddedReportTemplate()
    Set outWb = Workbooks.Open(Filename:=templatePath, UpdateLinks:=0, ReadOnly:=False, AddToMru:=False)
    If outWb.Worksheets.Count <> SH_ReportSheetCount() Then Err.Raise vbObjectError + 540, , "Embedded report template sheet count mismatch."
    For i = 1 To SH_ReportSheetCount()
        If outWb.Worksheets(i).Name <> SH_ReportSheetName(i) Then Err.Raise vbObjectError + 541, , "Embedded report template sheet order mismatch."
        SH_CopyValuesIntoTemplate wb.Worksheets(SH_InputSheetName(i)), outWb.Worksheets(SH_ReportSheetName(i))
    Next i
    SH_ApplyReportOffset outWb, offsetHours
    suggested = wb.Path & Application.PathSeparator & "Shift-Helper-Report-" & Format$(reportDate, "yyyy-mm-dd") & ".xlsx"
    outputPath = Application.GetSaveAsFilename(suggested, "Excel Workbook (*.xlsx),*.xlsx", , SH_T("SAVE_REPORT"))
    If VarType(outputPath) = vbBoolean And outputPath = False Then outWb.Close SaveChanges:=False: Exit Sub
    Application.DisplayAlerts = False
    outWb.SaveAs Filename:=CStr(outputPath), FileFormat:=xlOpenXMLWorkbook
    outWb.Close SaveChanges:=False
    Application.DisplayAlerts = True
    MsgBox SH_T("OK_REPORT") & CStr(outputPath), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    Application.DisplayAlerts = True
    On Error Resume Next
    If Not outWb Is Nothing Then outWb.Close SaveChanges:=False
    On Error GoTo 0
    MsgBox SH_T("ERR_REPORT") & Err.Description, vbExclamation, "Shift-Helper"
End Sub

Private Sub SH_CopyValuesIntoTemplate(ByVal source As Worksheet, ByVal target As Worksheet)
    Dim targetRange As Range, sourceRange As Range
    Set targetRange = target.UsedRange
    Set sourceRange = source.Range(targetRange.Address)
    targetRange.Value = sourceRange.Value
End Sub

Private Sub SH_ApplyReportOffset(ByVal wb As Workbook, ByVal offsetHours As Double)
    If offsetHours = 0 Then Exit Sub
    SH_ShiftDateColumns wb.Worksheets(SH_ReportSheetName(2)), Array("C", "F"), 4, offsetHours
    SH_ShiftDateColumns wb.Worksheets(SH_ReportSheetName(3)), Array("E", "F"), 4, offsetHours
    SH_ShiftDateColumns wb.Worksheets(SH_ReportSheetName(4)), Array("D"), 3, offsetHours
    SH_ShiftDateColumns wb.Worksheets(SH_ReportSheetName(5)), Array("J", "K"), 4, offsetHours
    SH_ShiftDateColumns wb.Worksheets(SH_ReportSheetName(6)), Array("I", "J"), 4, offsetHours
    SH_ShiftDateColumns wb.Worksheets(SH_ReportSheetName(7)), Array("C", "I", "J"), 4, offsetHours
End Sub

Private Sub SH_ShiftDateColumns(ByVal ws As Worksheet, ByVal columns As Variant, ByVal firstRow As Long, ByVal offsetHours As Double)
    Dim col As Variant, r As Long, lastRow As Long, value As Variant
    lastRow = ws.UsedRange.Row + ws.UsedRange.Rows.Count - 1
    For Each col In columns
        For r = firstRow To lastRow
            value = ws.Range(CStr(col) & r).Value2
            If Len(CStr(value)) > 0 And IsNumeric(value) Then ws.Range(CStr(col) & r).Value2 = CDbl(value) + offsetHours / 24#
        Next r
    Next col
End Sub
