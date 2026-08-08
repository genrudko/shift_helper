Attribute VB_Name = "modShiftHelperRotor"
Option Explicit

Public Sub SH_UpdateRotorLimits()
    On Error GoTo Failed
    Dim wb As Workbook, journal As Worksheet, state As Worksheet, reportDate As Date, endTime As Date
    Dim limits(1 To 84) As Double, eventTimes(1 To 84) As Double, active(1 To 84) As Boolean
    Dim lastRow As Long, r As Long, eventTime As Variant, asset As Long, sourceText As String, value As Double
    Dim data As Variant, rowIndex As Long, stateAsset As String, stateReason As String
    Dim oldCalculation As XlCalculation, oldEvents As Boolean, oldScreenUpdating As Boolean
    Dim appStateCaptured As Boolean, stage As String, errNumber As Long, errDescription As String

    stage = "resolve journal workbook"
    Set wb = SH_JournalBook()
    stage = "prepare report contour"
    SH_EnsureReportContour wb
    Set journal = SH_RequireSheet(wb, SH_JournalSheetName())
    Set state = SH_RequireSheet(wb, SH_InputSheetName(5))
    reportDate = SH_ReportDate(wb)
    endTime = DateSerial(Year(reportDate), Month(reportDate), Day(reportDate)) + TimeSerial(7, 0, 0)

    stage = "capture Excel state"
    oldCalculation = Application.Calculation
    oldEvents = Application.EnableEvents
    oldScreenUpdating = Application.ScreenUpdating
    appStateCaptured = True
    Application.Calculation = xlCalculationManual
    Application.EnableEvents = False
    Application.ScreenUpdating = False

    stage = "read journal events"
    lastRow = Application.Max(SH_LastRow(journal, 2), SH_LastRow(journal, 3))
    If lastRow > 1 Then data = journal.Range("B2:J" & lastRow).Value2

    If lastRow > 1 Then
        For rowIndex = 1 To UBound(data, 1)
            eventTime = SH_RotorCombineDateTime(data(rowIndex, 1), data(rowIndex, 2))
            If Not IsEmpty(eventTime) Then
                If CDbl(eventTime) < CDbl(endTime) And SH_RotorTryAsset(data(rowIndex, 3), asset) Then
                    sourceText = LCase$(SH_RotorSafeText(data(rowIndex, 6)))
                    If CDbl(eventTime) >= eventTimes(asset) Then
                        If InStr(1, sourceText, SH_U("0441043D044F0442043E"), vbTextCompare) > 0 And _
                           InStr(1, sourceText, SH_U("043E043304400430043D04380447"), vbTextCompare) > 0 Then
                            active(asset) = False
                            limits(asset) = 0#
                            eventTimes(asset) = CDbl(eventTime)
                        ElseIf InStr(1, sourceText, SH_U("0443044104420430043D043E0432043B0435043D043E0020043E043304400430043D043804470435043D04380435"), vbTextCompare) > 0 And _
                               InStr(1, sourceText, SH_U("043E0431043E0440043E"), vbTextCompare) > 0 Then
                            value = SH_ParseRotorLimit(sourceText)
                            If value > 0 Then
                                active(asset) = True
                                limits(asset) = value
                                eventTimes(asset) = CDbl(eventTime)
                            End If
                        End If
                    End If
                End If
            End If
        Next rowIndex
    End If

    stage = "update WTG state"
    lastRow = Application.Max(SH_LastRow(state, 4), 98)
    If lastRow > 5000 Then Err.Raise vbObjectError + 600, , "WTG state sheet has an implausible data boundary."
    For r = 4 To lastRow
        stateAsset = SH_RotorSafeText(state.Cells(r, 4).Value2)
        If Left$(stateAsset, 4) = SH_U("0412042D0423002D") Then
            asset = Val(Mid$(stateAsset, 5))
            If asset >= 1 And asset <= 84 Then
                If active(asset) Then
                    state.Cells(r, 7).Value2 = SH_RotorRepairPower(limits(asset))
                    state.Cells(r, 8).Formula = "=MAX(F" & r & "-G" & r & ",0)"
                    state.Cells(r, 9).Value = SH_T("LIMIT_REASON") & Replace(Format$(limits(asset), "0.00"), ".", ",")
                    state.Cells(r, 10).Value2 = eventTimes(asset)
                    state.Cells(r, 10).NumberFormat = "dd.mm.yyyy hh:mm"
                Else
                    stateReason = SH_RotorSafeText(state.Cells(r, 9).Value2)
                    If InStr(1, stateReason, SH_T("LIMIT_REASON"), vbTextCompare) > 0 Then
                        state.Cells(r, 7).Value2 = 0#
                        state.Cells(r, 8).Formula = "=MAX(F" & r & "-G" & r & ",0)"
                        state.Cells(r, 9).ClearContents
                        state.Cells(r, 10).ClearContents
                    End If
                End If
            End If
        End If
    Next r

    stage = "calculate report inputs"
    SH_CalculateReportInputs wb

    Application.Calculation = oldCalculation
    Application.EnableEvents = oldEvents
    Application.ScreenUpdating = oldScreenUpdating
    MsgBox SH_T("ROTOR_OK"), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    On Error Resume Next
    If appStateCaptured Then
        Application.Calculation = oldCalculation
        Application.EnableEvents = oldEvents
        Application.ScreenUpdating = oldScreenUpdating
    End If
    On Error GoTo 0
    If errNumber = 0 Then errNumber = vbObjectError + 601
    If Len(errDescription) = 0 Then errDescription = "WTG rotor-limit refresh failed."
    MsgBox SH_T("ROTOR_BAD") & "[#" & CStr(errNumber) & "] Stage [" & stage & "]: " & _
        errDescription, vbExclamation, "Shift-Helper"
End Sub

Private Function SH_RotorCombineDateTime(ByVal dateValue As Variant, ByVal timeValue As Variant) As Variant
    Dim dateSerial As Double, timeSerial As Double
    If Not SH_RotorTrySerial(dateValue, dateSerial) Then
        SH_RotorCombineDateTime = Empty
        Exit Function
    End If
    If Not SH_RotorTrySerial(timeValue, timeSerial) Then
        SH_RotorCombineDateTime = Empty
        Exit Function
    End If
    SH_RotorCombineDateTime = Int(dateSerial) + (timeSerial - Int(timeSerial))
End Function

Private Function SH_RotorTrySerial(ByVal raw As Variant, ByRef serial As Double) As Boolean
    On Error GoTo Failed
    If IsError(raw) Or IsNull(raw) Or IsEmpty(raw) Then Exit Function
    If VarType(raw) = vbString Then
        If Len(Trim$(CStr(raw))) = 0 Then Exit Function
    End If
    If IsNumeric(raw) Then
        serial = CDbl(raw)
        SH_RotorTrySerial = True
    ElseIf IsDate(raw) Then
        serial = CDbl(CDate(raw))
        SH_RotorTrySerial = True
    End If
    Exit Function
Failed:
    SH_RotorTrySerial = False
End Function

Private Function SH_RotorTryAsset(ByVal raw As Variant, ByRef asset As Long) As Boolean
    On Error GoTo Failed
    If IsError(raw) Or IsNull(raw) Or IsEmpty(raw) Then Exit Function
    If Not IsNumeric(raw) Then Exit Function
    asset = CLng(raw)
    SH_RotorTryAsset = (asset >= 1 And asset <= 84)
    Exit Function
Failed:
    SH_RotorTryAsset = False
End Function

Private Function SH_RotorSafeText(ByVal raw As Variant) As String
    On Error GoTo Failed
    If IsError(raw) Or IsNull(raw) Or IsEmpty(raw) Then Exit Function
    SH_RotorSafeText = CStr(raw)
    Exit Function
Failed:
    SH_RotorSafeText = ""
End Function

Private Function SH_ParseRotorLimit(ByVal text As String) As Double
    Dim i As Long, token As String, ch As String, value As Double
    For i = 1 To Len(text)
        ch = Mid$(text, i, 1)
        If (ch >= "0" And ch <= "9") Or ch = "." Or ch = "," Then
            token = token & ch
        ElseIf Len(token) > 0 Then
            token = Replace(token, ",", ".")
            If IsNumeric(token) Then
                value = Val(token)
                If value >= 0.5 And value <= 1.2 Then SH_ParseRotorLimit = value: Exit Function
            End If
            token = ""
        End If
    Next i
    If Len(token) > 0 Then
        token = Replace(token, ",", ".")
        If IsNumeric(token) Then SH_ParseRotorLimit = Val(token)
    End If
End Function

Private Function SH_RotorRepairPower(ByVal limitValue As Double) As Double
    Dim value As Double
    value = Round(limitValue, 2)
    If value < 0.7 Then SH_RotorRepairPower = 2.5: Exit Function
    If value >= 0.95 Then SH_RotorRepairPower = 0#: Exit Function
    If value = 0.9 Then SH_RotorRepairPower = 0.55: Exit Function
    If value = 0.85 Then SH_RotorRepairPower = 0.75: Exit Function
    If value = 0.8 Then SH_RotorRepairPower = 1#: Exit Function
    If value = 0.75 Then SH_RotorRepairPower = 1.2: Exit Function
    If value = 0.7 Then SH_RotorRepairPower = 1.4: Exit Function
    SH_RotorRepairPower = 0.45
End Function
