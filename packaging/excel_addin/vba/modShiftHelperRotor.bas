Attribute VB_Name = "modShiftHelperRotor"
Option Explicit

Public Sub SH_UpdateRotorLimits()
    On Error GoTo Failed
    Dim wb As Workbook, journal As Worksheet, state As Worksheet, reportDate As Date, endTime As Date
    Dim limits(1 To 84) As Double, eventTimes(1 To 84) As Double, active(1 To 84) As Boolean
    Dim lastRow As Long, r As Long, eventTime As Variant, asset As Long, sourceText As String, value As Double
    Set wb = SH_JournalBook()
    SH_EnsureReportContour wb
    Set journal = SH_RequireSheet(wb, SH_JournalSheetName())
    Set state = SH_RequireSheet(wb, SH_InputSheetName(5))
    reportDate = SH_ReportDate(wb)
    endTime = DateSerial(Year(reportDate), Month(reportDate), Day(reportDate)) + TimeSerial(7, 0, 0)
    lastRow = Application.Max(SH_LastRow(journal, 2), SH_LastRow(journal, 3))

    For r = 2 To lastRow
        eventTime = SH_CellDateTime(journal, r)
        If Not IsEmpty(eventTime) Then
            If CDbl(eventTime) < CDbl(endTime) And IsNumeric(journal.Cells(r, 4).Value2) Then
                asset = CLng(journal.Cells(r, 4).Value2)
                If asset >= 1 And asset <= 84 Then
                    sourceText = LCase$(CStr(journal.Cells(r, 7).Value2))
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
        End If
    Next r

    lastRow = Application.Max(SH_LastRow(state, 4), 98)
    For r = 4 To lastRow
        If Left$(CStr(state.Cells(r, 4).Value2), 4) = SH_U("0412042D0423002D") Then
            asset = Val(Mid$(CStr(state.Cells(r, 4).Value2), 5))
            If asset >= 1 And asset <= 84 Then
                If active(asset) Then
                    state.Cells(r, 7).Value2 = SH_RotorRepairPower(limits(asset))
                    state.Cells(r, 8).Formula = "=MAX(F" & r & "-G" & r & ",0)"
                    state.Cells(r, 9).Value = SH_T("LIMIT_REASON") & Replace(Format$(limits(asset), "0.00"), ".", ",")
                    state.Cells(r, 10).Value2 = eventTimes(asset)
                    state.Cells(r, 10).NumberFormat = "dd.mm.yyyy hh:mm"
                ElseIf InStr(1, CStr(state.Cells(r, 9).Value2), SH_T("LIMIT_REASON"), vbTextCompare) > 0 Then
                    state.Cells(r, 7).Value2 = 0#
                    state.Cells(r, 8).Formula = "=MAX(F" & r & "-G" & r & ",0)"
                    state.Cells(r, 9).ClearContents
                    state.Cells(r, 10).ClearContents
                End If
            End If
        End If
    Next r
    wb.Calculate
    MsgBox SH_T("ROTOR_OK"), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    MsgBox SH_T("ROTOR_BAD") & Err.Description, vbExclamation, "Shift-Helper"
End Sub

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
    If limitValue < 0.7 Then SH_RotorRepairPower = 2.5: Exit Function
    If limitValue >= 0.95 Then SH_RotorRepairPower = 0#: Exit Function
    If limitValue >= 0.9 Then SH_RotorRepairPower = 0.55: Exit Function
    If limitValue >= 0.85 Then SH_RotorRepairPower = 0.75: Exit Function
    If limitValue >= 0.8 Then SH_RotorRepairPower = 1#: Exit Function
    If limitValue >= 0.75 Then SH_RotorRepairPower = 1.2: Exit Function
    If limitValue >= 0.7 Then SH_RotorRepairPower = 1.4: Exit Function
    SH_RotorRepairPower = 0.45
End Function
