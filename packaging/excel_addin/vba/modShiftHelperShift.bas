Attribute VB_Name = "modShiftHelperShift"
Option Explicit

Public Sub SH_GotoCurrentInspectionShift()
    On Error GoTo Failed
    Dim wb As Workbook, ws As Worksheet
    Dim effectiveDate As Date, wanted As String, shiftName As String
    Dim dayText As String, rowShift As String, raw As String, ktpText As String
    Dim r As Long, targetRow As Long, col As Long, assignments As Long
    Dim message As String

    Set wb = SH_JournalBook()
    Set ws = SH_RequireSheet(wb, SH_InspectionSheetName())

    ' Operational night shift spans 20:00-07:59. After midnight it still belongs
    ' to the preceding calendar day's schedule row.
    If Hour(Now) < 8 Then
        effectiveDate = DateAdd("d", -1, Date)
        wanted = SH_T("SHIFT_NIGHT")
        shiftName = SH_U("041D043E0447043D0430044F")
    ElseIf Hour(Now) < 20 Then
        effectiveDate = Date
        wanted = SH_T("SHIFT_DAY")
        shiftName = SH_U("0414043D04350432043D0430044F")
    Else
        effectiveDate = Date
        wanted = SH_T("SHIFT_NIGHT")
        shiftName = SH_U("041D043E0447043D0430044F")
    End If

    For r = 3 To Application.Min(66, ws.Rows.Count)
        dayText = SH_InspectionDayValue(ws, r)
        rowShift = UCase$(Trim$(CStr(ws.Cells(r, 2).Value2)))
        If IsNumeric(dayText) Then
            If CLng(CDbl(dayText)) = Day(effectiveDate) And Left$(rowShift, 1) = wanted Then
                targetRow = r
                Exit For
            End If
        End If
    Next r

    If targetRow = 0 Then
        MsgBox SH_T("SHIFT_NOT_FOUND"), vbInformation, "Shift-Helper"
        Exit Sub
    End If

    message = SH_U("0421043C0435043D0430003A0020") & Format$(effectiveDate, "dd.mm.yyyy") & _
        " - " & shiftName

    For col = 3 To 20
        raw = Trim$(CStr(ws.Cells(targetRow, col).Value2))
        If Len(raw) > 0 And Left$(raw, 1) = ChrW$(&H2116) Then
            assignments = assignments + 1
            ktpText = SH_InspectionKtpList(ws, col)
            If Len(ktpText) = 0 Then ktpText = "-"
            message = message & vbCrLf & vbCrLf & _
                SH_U("041C002E041A002E0020") & raw & vbCrLf & _
                SH_U("041A0422041F003A0020") & ktpText
        End If
    Next col

    If assignments = 0 Then
        message = message & vbCrLf & vbCrLf & _
            SH_U("041D0430002004420435043A044304490443044E00200441043C0435043D04430020043E0441043C043E04420440044B0020043D04350020043D04300437043D043004470435043D044B002E")
    End If

    MsgBox message, vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Private Function SH_InspectionDayValue(ByVal ws As Worksheet, ByVal rowNumber As Long) As String
    Dim r As Long, value As String
    For r = rowNumber To 3 Step -1
        value = Trim$(CStr(ws.Cells(r, 1).Value2))
        If Len(value) > 0 Then
            SH_InspectionDayValue = value
            Exit Function
        End If
    Next r
End Function

Private Function SH_InspectionKtpList(ByVal ws As Worksheet, ByVal columnNumber As Long) As String
    Dim r As Long, value As String, numericProbe As String

    ' Approved schedule stores each inspection card's KTP list above the day/night rows.
    ' Prefer row 2, then tolerate small historical layout shifts without hardcoding cards.
    value = Trim$(CStr(ws.Cells(2, columnNumber).Value2))
    If SH_LooksLikeKtpList(value) Then
        SH_InspectionKtpList = value
        Exit Function
    End If

    For r = 1 To 4
        value = Trim$(CStr(ws.Cells(r, columnNumber).Value2))
        If SH_LooksLikeKtpList(value) Then
            SH_InspectionKtpList = value
            Exit Function
        End If
    Next r
End Function

Private Function SH_LooksLikeKtpList(ByVal value As String) As Boolean
    Dim numericProbe As String
    If Len(value) = 0 Then Exit Function
    If Left$(value, 1) = ChrW$(&H2116) Then Exit Function
    numericProbe = Replace(Replace(Replace(value, ",", ""), " ", ""), ChrW$(160), "")
    If Len(numericProbe) = 0 Then Exit Function
    SH_LooksLikeKtpList = IsNumeric(numericProbe)
End Function
