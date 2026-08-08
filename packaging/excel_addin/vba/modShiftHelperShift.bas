Attribute VB_Name = "modShiftHelperShift"
Option Explicit

Public Sub SH_GotoCurrentInspectionShift()
    On Error GoTo Failed
    Dim wb As Workbook, ws As Worksheet, wanted As String, dayText As String, rowShift As String
    Dim r As Long, targetRow As Long, col As Long, endCol As Long, raw As String, assignments As Long
    Set wb = SH_JournalBook()
    Set ws = SH_RequireSheet(wb, SH_InspectionSheetName())
    If Hour(Now) >= 8 And Hour(Now) < 20 Then wanted = SH_T("SHIFT_DAY") Else wanted = SH_T("SHIFT_NIGHT")

    For r = 5 To Application.Min(66, ws.Rows.Count)
        dayText = SH_InspectionDayValue(ws, r)
        rowShift = UCase$(Trim$(CStr(ws.Cells(r, 2).Value2)))
        If IsNumeric(dayText) Then
            If CLng(CDbl(dayText)) = Day(Date) And Left$(rowShift, 1) = wanted Then
                targetRow = r
                Exit For
            End If
        End If
    Next r
    If targetRow = 0 Then
        MsgBox SH_U("0414043B044F0020044104350433043E0434043D044F0448043D04350433043E00200434043D044F0020043800200441043C0435043D044B002004370430043F0438044104380020043D04350020043D0430043904340435043D044B002E0020041F0440043E043204350440044C04420435002004410442043E043B04310446044B002000410020043800200042002E"), vbInformation, "Shift-Helper"
        Exit Sub
    End If

    endCol = 2
    For col = 3 To 20
        raw = Trim$(CStr(ws.Cells(targetRow, col).Value2))
        If Len(raw) > 0 And Left$(raw, 1) = ChrW$(&H2116) Then
            assignments = assignments + 1
            endCol = col
        End If
    Next col
    ws.Activate
    ws.Range(ws.Cells(targetRow, 1), ws.Cells(targetRow, endCol)).Select
    Application.Goto ws.Cells(targetRow, 1), True
    If assignments = 0 Then
        MsgBox SH_U("042104420440043E043A0430002004420435043A0443044904350433043E00200434043D044F0020043800200441043C0435043D044B00200432044B04340435043B0435043D0430002E0020041D04300437043D043004470435043D043D044B04450020043E0441043C043E04420440043E0432002004320020043D043504390020043D04350442002E"), vbInformation, "Shift-Helper"
    End If
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Private Function SH_InspectionDayValue(ByVal ws As Worksheet, ByVal rowNumber As Long) As String
    Dim r As Long, value As String
    For r = rowNumber To 5 Step -1
        value = Trim$(CStr(ws.Cells(r, 1).Value2))
        If Len(value) > 0 Then
            SH_InspectionDayValue = value
            Exit Function
        End If
    Next r
End Function
