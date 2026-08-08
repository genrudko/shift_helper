Attribute VB_Name = "modShiftHelperReport"
Option Explicit

Public Sub SH_PrepareReportContour()
    On Error GoTo Failed
    Dim wb As Workbook, errDescription As String, errNumber As Long
    Set wb = SH_JournalBook()
    SH_EnsureReportContour wb
    MsgBox SH_T("OK_PREP") & vbCrLf & SH_T("NO_TEMPLATE_PICK"), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    If Len(errDescription) = 0 Then errDescription = "Report contour preparation failed."
    MsgBox SH_T("ERR_PREP") & "[#" & CStr(errNumber) & "] " & errDescription, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_EnsureReportContour(ByVal wb As Workbook)
    On Error GoTo Failed
    Dim template As Workbook, templatePath As String, prep As Worksheet
    Dim i As Long, inputName As String, reportName As String, needsTemplate As Boolean
    Dim errNumber As Long, errDescription As String, stage As String
    Dim oldCalculation As XlCalculation, oldEvents As Boolean, oldScreenUpdating As Boolean
    Dim appStateCaptured As Boolean

    stage = "capture Excel state"
    oldCalculation = Application.Calculation
    oldEvents = Application.EnableEvents
    oldScreenUpdating = Application.ScreenUpdating
    appStateCaptured = True
    Application.EnableEvents = False
    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual

    stage = "prepare service sheet"
    Set prep = SH_EnsurePrepSheet(wb)

    stage = "check report forms"
    For i = 1 To SH_ReportSheetCount()
        If Not SH_HasSheet(wb, SH_InputSheetName(i)) Then
            needsTemplate = True
            Exit For
        End If
    Next i

    If needsTemplate Then
        stage = "restore embedded report template"
        templatePath = SH_ExtractEmbeddedReportTemplate()
        stage = "open embedded report template"
        Set template = Workbooks.Open( _
            Filename:=templatePath, _
            UpdateLinks:=0, _
            ReadOnly:=True, _
            AddToMru:=False _
        )
        stage = "copy missing report forms"
        For i = 1 To SH_ReportSheetCount()
            inputName = SH_InputSheetName(i)
            reportName = SH_ReportSheetName(i)
            If Not SH_HasSheet(wb, inputName) Then
                template.Worksheets(reportName).Copy After:=wb.Worksheets(wb.Worksheets.Count)
                wb.Worksheets(wb.Worksheets.Count).Name = inputName
            End If
        Next i
        template.Close SaveChanges:=False
        Set template = Nothing
    End If

    stage = "apply report formulas"
    SH_ApplyCriticalFormulas wb
    stage = "refresh emergency outages"
    SH_RefreshEmergencyOutages wb
    stage = "calculate report sheets"
    SH_CalculateReportInputs wb

    Application.Calculation = oldCalculation
    Application.EnableEvents = oldEvents
    Application.ScreenUpdating = oldScreenUpdating
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    On Error Resume Next
    If Not template Is Nothing Then template.Close SaveChanges:=False
    If appStateCaptured Then
        Application.Calculation = oldCalculation
        Application.EnableEvents = oldEvents
        Application.ScreenUpdating = oldScreenUpdating
    End If
    On Error GoTo 0
    If errNumber = 0 Then errNumber = vbObjectError + 542
    If Len(errDescription) = 0 Then errDescription = "Report contour bootstrap failed."
    Err.Raise errNumber, , "Stage [" & stage & "]: " & errDescription
End Sub

Public Sub SH_CalculateReportInputs(ByVal wb As Workbook)
    Dim order As Variant, item As Variant, ws As Worksheet
    order = Array(5, 6, 2, 3, 4, 7, 1)
    For Each item In order
        Set ws = SH_RequireSheet(wb, SH_InputSheetName(CLng(item)))
        ws.Calculate
    Next item
End Sub

Public Sub SH_ApplyCriticalFormulas(ByVal wb As Workbook)
    Dim main As Worksheet, state As Worksheet, works As Worksheet
    Dim groups As Collection, r As Long, lastRow As Long, i As Long
    Dim groupRow As Long, firstChild As Long, lastChild As Long, nextGroup As Long
    Dim col As Variant, q As String, prepName As String
    Dim stateGroup As String, stateAsset As String, stateStatus As String
    q = Chr$(34)
    prepName = SH_PrepSheetName()
    Set main = SH_RequireSheet(wb, SH_InputSheetName(1))
    Set state = SH_RequireSheet(wb, SH_InputSheetName(5))
    Set works = SH_RequireSheet(wb, SH_InputSheetName(6))
    SH_EnsureStatusColumn state

    main.Range("B1").Formula = "=" & q & SH_U("04200430043F043E044004420020041D042104210020043D04300020") & q & "&TEXT('" & prepName & "'!B3," & q & "dd.mm.yyyy" & q & ")&" & q & SH_U("0020041A043E0447044304310435043504320441043A0430044F00200412042D042100200028") & q & "&'" & prepName & "'!B7&" & q & SH_U("0029002E0020041F043E0441043B04350434043D04380435002004380437043C0435043D0435043D0438044F0020") & q & "&TEXT(NOW()," & q & "dd.mm.yyyy, hh:mm:ss" & q & ")"
    main.Range("B6").Formula = "=" & q & SH_U("00200421044004350434043D044F044F0020043D04300433044004430437043A04300020043704300020") & q & "&TEXT('" & prepName & "'!B3-1," & q & "dd.mm.yyyy" & q & ")&" & q & SH_U("002C0020041C04120442") & q
    main.Range("B7").Formula = "=" & q & SH_U("002004220435043A044304490430044F0020043D04300433044004430437043A04300020043D0430002000300037003A003000300020") & q & "&TEXT('" & prepName & "'!B3," & q & "dd.mm.yyyy" & q & ")&" & q & SH_U("002C0020041C04120442") & q
    main.Range("B10").Formula = "=" & q & SH_U("00200412044B044004300431043E0442043A04300020043704300020") & q & "&TEXT('" & prepName & "'!B3-1," & q & "dd.mm.yyyy" & q & ")&" & q & SH_U("002C0020043A04120442002A0447") & q
    main.Range("B12").Formula = "=" & q & SH_U("0020041F043B0430043D002004410020003000310020043F043E0020") & q & "&TEXT('" & prepName & "'!B3," & q & "dd.mm.yyyy" & q & ")&" & q & SH_U("002C0020043A04120442002A0447") & q
    main.Range("E9").Formula = "=" & q & SH_U("041F043E0433043E0434043D044B0435002004430441043B043E04320438044F0020043D0430002000300037003A003000300020") & q & "&TEXT('" & prepName & "'!B3," & q & "dd.mm.yyyy" & q & ")"
    main.Range("E14").Formula = "=" & q & SH_U("041F043004400430043C043504420440044B0020044104350442043800200412042D04210020043D0430002000300037003A003000300020") & q & "&TEXT('" & prepName & "'!B3," & q & "dd.mm.yyyy" & q & ")"
    main.Range("H3").Formula = "=" & q & SH_U("041F043B0430043D002F04240430043A04420020041A043E0447044304310435043504320441043A0430044F00200412042D04210020") & q & "&YEAR('" & prepName & "'!B3)"
    main.Range("H18").Formula = "=" & q & SH_U("041D043004400430044104420430044E044904380439002004380442043E04330020043D04300020") & q & "&TEXT('" & prepName & "'!B3," & q & "dd.mm.yyyy" & q & ")"

    main.Range("C6").Formula = "=IFERROR(C10/24000,0)"
    main.Range("C6").NumberFormat = "0.00"
    main.Range("C12").Formula = "=INDEX(I5:I16,MONTH('" & prepName & "'!B3))*(DAY('" & prepName & "'!B3)-1)/DAY(EOMONTH('" & prepName & "'!B3,0))"
    main.Range("C13").Formula = "=C11-C12"
    main.Range("C14").Formula = "=IFERROR(C11/C12,0)"
    main.Range("C15").Formula = "=IFERROR(IF(C13>=0,-1,(INDEX(I5:I16,MONTH('" & prepName & "'!B3))-C11)/((DAY(EOMONTH('" & prepName & "'!B3,0))-DAY('" & prepName & "'!B3)+1)*24)),0)"
    main.Range("C15").NumberFormat = "0.0"

    For r = 5 To 16
        main.Cells(r, 11).Formula = "=IF(J" & r & "=" & q & q & "," & q & q & ",J" & r & "-I" & r & ")"
        main.Cells(r, 12).Formula = "=IFERROR(J" & r & "/I" & r & "," & q & q & ")"
    Next r
    main.Range("I17").Formula = "=SUM(I5:I16)"
    main.Range("J17").Formula = "=SUM(J5:J16)"
    main.Range("K17").Formula = "=J17-I17"
    main.Range("L17").Formula = "=IFERROR(J17/I17," & q & q & ")"
    main.Range("I18").Formula = "=SUMPRODUCT(I5:I16,--(ROW(I5:I16)-ROW(I5)+1<MONTH('" & prepName & "'!B3)))+INDEX(I5:I16,MONTH('" & prepName & "'!B3))*(DAY('" & prepName & "'!B3)-1)/DAY(EOMONTH('" & prepName & "'!B3,0))"
    main.Range("J18").Formula = "=SUMPRODUCT(J5:J16,--(ROW(J5:J16)-ROW(J5)+1<=MONTH('" & prepName & "'!B3)))"
    main.Range("K18").Formula = "=J18-I18"
    main.Range("L18").Formula = "=IFERROR(J18/I18," & q & q & ")"

    Set groups = New Collection
    lastRow = Application.Max(SH_LastRow(state, 3), SH_LastRow(state, 4), 98)
    If lastRow > 5000 Then Err.Raise vbObjectError + 543, , "WTG state sheet has an implausible data boundary."
    For r = 4 To lastRow
        stateGroup = SH_ReportSafeText(state.Cells(r, 3).Value2)
        stateAsset = SH_ReportSafeText(state.Cells(r, 4).Value2)
        If Len(stateGroup) > 0 And Len(stateAsset) = 0 Then
            groups.Add r
        ElseIf Left$(stateAsset, 4) = SH_U("0412042D0423002D") Then
            state.Cells(r, 8).Formula = "=MAX(F" & r & "-G" & r & ",0)"
            stateStatus = SH_ReportSafeText(state.Cells(r, 12).Value2)
            If Not SH_ValidStatus(stateStatus) Then state.Cells(r, 12).Value = SH_InferStatus(state, r)
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
    main.Range("F4").Formula = "=COUNTIF('" & state.Name & "'!L4:L98," & q & SH_StatusText(2) & q & ")"
    main.Range("F5").Formula = "=COUNTIF('" & state.Name & "'!L4:L98," & q & SH_StatusText(1) & q & ")"
    main.Range("F6").Formula = "=COUNTIF('" & state.Name & "'!L4:L98," & q & SH_StatusText(3) & q & ")"
    main.Range("F7").Formula = "=COUNTIF('" & state.Name & "'!L4:L98," & q & SH_StatusText(4) & q & ")"

    lastRow = Application.Max(SH_LastRow(works, 4), SH_LastRow(works, 5), 200)
    If lastRow > 10000 Then Err.Raise vbObjectError + 544, , "Planned-work sheet has an implausible data boundary."
    For r = 4 To lastRow
        works.Cells(r, 7).Formula = "=IF(COUNTA(E" & r & ":F" & r & ")=0," & q & q & ",MAX(E" & r & "-F" & r & ",0))"
    Next r
End Sub

Private Sub SH_EnsureStatusColumn(ByVal state As Worksheet)
    Dim r As Long, lastRow As Long, assetText As String
    lastRow = Application.Max(SH_LastRow(state, 4), 98)
    If lastRow > 5000 Then Err.Raise vbObjectError + 545, , "WTG state sheet has an implausible status boundary."
    If SH_ReportSafeText(state.Cells(3, 12).Value2) <> SH_U("04210442043004420443044100200412042D0423") Then
        state.Range("K3:K" & lastRow).Copy
        state.Range("L3:L" & lastRow).PasteSpecial Paste:=xlPasteFormats
        Application.CutCopyMode = False
        state.Columns(12).ColumnWidth = 16
        state.Cells(3, 12).Value = SH_U("04210442043004420443044100200412042D0423")
    End If
    For r = 4 To lastRow
        assetText = SH_ReportSafeText(state.Cells(r, 4).Value2)
        If Left$(assetText, 4) <> SH_U("0412042D0423002D") Then state.Cells(r, 12).ClearContents
    Next r
End Sub

Private Function SH_ValidStatus(ByVal value As String) As Boolean
    Dim i As Long
    For i = 1 To 4
        If StrComp(Trim$(value), SH_StatusText(i), vbTextCompare) = 0 Then
            SH_ValidStatus = True
            Exit Function
        End If
    Next i
End Function

Private Function SH_InferStatus(ByVal state As Worksheet, ByVal r As Long) As String
    Dim reason As String, available As Double, repair As Double
    reason = LCase$(SH_ReportSafeText(state.Cells(r, 9).Value2))
    available = SH_ReportSafeDouble(state.Cells(r, 8).Value2)
    repair = SH_ReportSafeDouble(state.Cells(r, 7).Value2)
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
    Dim lastRow As Long, index As Long, outRow As Long, eventTime As Variant, endTime As Variant
    Dim description As String, reason As String, asset As String, data As Variant
    Set source = SH_RequireSheet(wb, SH_JournalSheetName())
    Set target = SH_RequireSheet(wb, SH_InputSheetName(2))
    reportDate = SH_ReportDate(wb)
    windowEnd = DateSerial(Year(reportDate), Month(reportDate), Day(reportDate)) + TimeSerial(7, 0, 0)
    windowStart = windowEnd - 1
    target.Range("B4:F" & Application.Max(200, SH_LastRow(target, 2))).ClearContents
    lastRow = Application.Max(SH_LastRow(source, 1), SH_LastRow(source, 2), SH_LastRow(source, 3))
    If lastRow < 2 Then Exit Function
    If lastRow > 250000 Then Err.Raise vbObjectError + 546, , "Journal data boundary is implausibly large."

    data = source.Range("B2:J" & lastRow).Value2
    outRow = 4
    For index = 1 To UBound(data, 1)
        eventTime = SH_CombineDateTime(data(index, 1), data(index, 2))
        If Not IsEmpty(eventTime) Then
            If CDbl(eventTime) >= CDbl(windowStart) And CDbl(eventTime) < CDbl(windowEnd) Then
                description = Trim$(SH_ReportSafeText(data(index, 4)))
                reason = Trim$(SH_ReportSafeText(data(index, 5)))
                If SH_SelectEmergency(description, reason) Then
                    asset = SH_ReportSafeText(data(index, 3))
                    target.Cells(outRow, 2).Value = SH_U("0412042D042300202116") & asset
                    target.Cells(outRow, 3).Value2 = CDbl(eventTime)
                    target.Cells(outRow, 3).NumberFormat = "dd.mm.yyyy hh:mm"
                    target.Cells(outRow, 4).Value = reason
                    target.Cells(outRow, 5).Value = description
                    endTime = SH_CombineDateTime(data(index, 8), data(index, 9))
                    If Not IsEmpty(endTime) Then
                        target.Cells(outRow, 6).Value2 = CDbl(endTime)
                        target.Cells(outRow, 6).NumberFormat = "dd.mm.yyyy hh:mm"
                    End If
                    outRow = outRow + 1
                End If
            End If
        End If
    Next index
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
    If InStr(1, eText, SH_U("043E044804380431043A0430002004320020044004300431043E04420435"), vbTextCompare) > 0 Then
        SH_SelectEmergency = True
        Exit Function
    End If
    If InStr(1, eText, SH_U("04320020044004300431043E04420435"), vbTextCompare) > 0 Then Exit Function
    SH_SelectEmergency = True
End Function

Private Function SH_CombineDateTime(ByVal dateValue As Variant, ByVal timeValue As Variant) As Variant
    Dim dateSerial As Double, timeSerial As Double
    If Not SH_ReportTrySerial(dateValue, dateSerial) Then
        SH_CombineDateTime = Empty
        Exit Function
    End If
    If Not SH_ReportTrySerial(timeValue, timeSerial) Then
        SH_CombineDateTime = Empty
        Exit Function
    End If
    SH_CombineDateTime = Int(dateSerial) + (timeSerial - Int(timeSerial))
End Function

Private Function SH_ReportTrySerial(ByVal value As Variant, ByRef serial As Double) As Boolean
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If VarType(value) = vbString Then
        If Len(Trim$(CStr(value))) = 0 Then Exit Function
    End If
    If IsNumeric(value) Then
        serial = CDbl(value)
        SH_ReportTrySerial = True
        Exit Function
    End If
    If IsDate(value) Then
        serial = CDbl(CDate(value))
        SH_ReportTrySerial = True
    End If
    Exit Function
Failed:
    SH_ReportTrySerial = False
End Function

Private Function SH_ReportSafeText(ByVal value As Variant) As String
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    SH_ReportSafeText = CStr(value)
    Exit Function
Failed:
    SH_ReportSafeText = ""
End Function

Private Function SH_ReportSafeDouble(ByVal value As Variant) As Double
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If IsNumeric(value) Then SH_ReportSafeDouble = CDbl(value)
    Exit Function
Failed:
    SH_ReportSafeDouble = 0#
End Function

Public Sub SH_GenerateFullReport()
    On Error GoTo Failed
    Dim wb As Workbook, outWb As Workbook, templatePath As String, i As Long
    Dim reportDate As Date, offsetHours As Double, suggested As String, outputPath As Variant, outputFolder As String
    Dim errDescription As String, errNumber As Long
    Set wb = SH_JournalBook()
    SH_EnsureReportContour wb
    reportDate = SH_ReportDate(wb)
    offsetHours = SH_ReportOffset(wb)
    SH_RefreshEmergencyOutages wb
    SH_CalculateReportInputs wb
    templatePath = SH_ExtractEmbeddedReportTemplate()
    Set outWb = Workbooks.Open(Filename:=templatePath, UpdateLinks:=0, ReadOnly:=False, AddToMru:=False)
    If outWb.Worksheets.Count <> SH_ReportSheetCount() Then Err.Raise vbObjectError + 540, , "Embedded report template sheet count mismatch."
    For i = 1 To SH_ReportSheetCount()
        If outWb.Worksheets(i).Name <> SH_ReportSheetName(i) Then Err.Raise vbObjectError + 541, , "Embedded report template sheet order mismatch."
        SH_CopyValuesIntoTemplate SH_RequireSheet(wb, SH_InputSheetName(i)), outWb.Worksheets(SH_ReportSheetName(i))
    Next i
    SH_ApplyReportOffset outWb, offsetHours
    outputFolder = wb.Path
    If Len(outputFolder) = 0 Then outputFolder = Application.DefaultFilePath
    suggested = outputFolder & Application.PathSeparator & "Shift-Helper-Report-" & Format$(reportDate, "yyyy-mm-dd") & ".xlsx"
    outputPath = Application.GetSaveAsFilename(suggested, "Excel Workbook (*.xlsx),*.xlsx", , SH_T("SAVE_REPORT"))
    If VarType(outputPath) = vbBoolean And outputPath = False Then
        outWb.Close SaveChanges:=False
        Exit Sub
    End If
    Application.DisplayAlerts = False
    outWb.SaveAs Filename:=CStr(outputPath), FileFormat:=xlOpenXMLWorkbook
    outWb.Close SaveChanges:=False
    Application.DisplayAlerts = True
    MsgBox SH_T("OK_REPORT") & CStr(outputPath), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    Application.DisplayAlerts = True
    On Error Resume Next
    If Not outWb Is Nothing Then outWb.Close SaveChanges:=False
    On Error GoTo 0
    If Len(errDescription) = 0 Then errDescription = "Report generation failed."
    MsgBox SH_T("ERR_REPORT") & "[#" & CStr(errNumber) & "] " & errDescription, vbExclamation, "Shift-Helper"
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
    Dim col As Variant, r As Long, lastRow As Long, value As Variant, serial As Double
    lastRow = ws.UsedRange.Row + ws.UsedRange.Rows.Count - 1
    For Each col In columns
        For r = firstRow To lastRow
            value = ws.Range(CStr(col) & r).Value2
            If SH_ReportTrySerial(value, serial) Then ws.Range(CStr(col) & r).Value2 = serial + offsetHours / 24#
        Next r
    Next col
End Sub
