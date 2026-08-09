Attribute VB_Name = "modShiftHelperQuickInput"
Option Explicit

Public SH_AppEvents As CShiftHelperAppEvents
Private mQuickEnabled As Boolean
Private mQuickGuard As Boolean

Public Sub SH_InitializeAddin()
    On Error Resume Next
    If SH_AppEvents Is Nothing Then
        Set SH_AppEvents = New CShiftHelperAppEvents
        Set SH_AppEvents.App = Application
    End If
    mQuickEnabled = (GetSetting("Shift-Helper", "Journal", "QuickInput", "1") <> "0")
    On Error GoTo 0
End Sub

Public Sub SH_EnableQuickInput()
    SH_InitializeAddin
    mQuickEnabled = True
    SaveSetting "Shift-Helper", "Journal", "QuickInput", "1"
    MsgBox SH_U("0411044B044104420440044B0439002004320432043E043400200432043A043B044E04470451043D002E"), vbInformation, "Shift-Helper"
End Sub

Public Sub SH_DisableQuickInput()
    SH_InitializeAddin
    mQuickEnabled = False
    SaveSetting "Shift-Helper", "Journal", "QuickInput", "0"
    MsgBox SH_U("0411044B044104420440044B0439002004320432043E043400200432044B043A043B044E04470435043D002E"), vbInformation, "Shift-Helper"
End Sub

Public Sub SH_ShowQuickInputStatus()
    SH_InitializeAddin
    If mQuickEnabled Then
        MsgBox SH_U("0411044B044104420440044B0439002004320432043E0434003A00200432043A043B044E04470451043D002E"), vbInformation, "Shift-Helper"
    Else
        MsgBox SH_U("0411044B044104420440044B0439002004320432043E0434003A00200432044B043A043B044E04470435043D002E"), vbInformation, "Shift-Helper"
    End If
End Sub

Public Sub SH_PrepareQuickInputSelection(ByVal Sh As Object, ByVal Target As Range)
    On Error GoTo SafeExit
    Dim cell As Range, col As Long
    SH_InitializeAddin
    If Not mQuickEnabled Or mQuickGuard Then Exit Sub
    If TypeName(Sh) <> "Worksheet" Then Exit Sub
    If Sh.Name <> SH_JournalSheetName() Then Exit Sub
    If Target Is Nothing Then Exit Sub
    If Target.Areas.Count <> 1 Or Target.Columns.Count <> 1 Then Exit Sub
    If Target.Cells.CountLarge > 256 Then Exit Sub
    col = Target.Column
    If Not SH_IsQuickColumn(col) Then Exit Sub
    For Each cell In Target.Cells
        If cell.Row > 1 And Len(CStr(cell.Value2)) = 0 And Not cell.HasFormula Then cell.NumberFormat = "@"
    Next cell
SafeExit:
End Sub

Public Sub SH_HandleQuickInputChange(ByVal Sh As Object, ByVal Target As Range)
    On Error GoTo Failed
    Dim col As Long, previousDate As Date, previousTime As Date, hasPrevious As Boolean
    Dim cell As Range, raw As Variant, parsedDate As Date, parsedTime As Date, dayOffset As Long
    Dim errorText As String, firstError As String, errorCount As Long
    Dim paired As Range, pairedDate As Date, hadEvents As Boolean

    SH_InitializeAddin
    If Not mQuickEnabled Or mQuickGuard Then Exit Sub
    If TypeName(Sh) <> "Worksheet" Then Exit Sub
    If Sh.Name <> SH_JournalSheetName() Then Exit Sub
    If Target Is Nothing Then Exit Sub
    If Target.Areas.Count <> 1 Or Target.Columns.Count <> 1 Then Exit Sub
    If Target.Cells.CountLarge > 256 Then Exit Sub
    col = Target.Column
    If Not SH_IsQuickColumn(col) Then Exit Sub
    If Target.Row <= 1 Then Exit Sub

    mQuickGuard = True
    hadEvents = Application.EnableEvents
    Application.EnableEvents = False

    If col = 2 Or col = 9 Then
        hasPrevious = SH_ReadDateCell(Sh.Cells(Target.Row - 1, col), previousDate)
    Else
        hasPrevious = SH_ReadTimeCell(Sh.Cells(Target.Row - 1, col), previousTime)
    End If

    For Each cell In Target.Cells
        If cell.Row <= 1 Then GoTo NextCell
        raw = SH_QuickRawValue(cell)
        If SH_QuickBlank(raw) Then GoTo NextCell
        errorText = ""
        If col = 2 Or col = 9 Then
            If SH_TryParseDate(raw, previousDate, hasPrevious, parsedDate, errorText) Then
                cell.Value2 = CDbl(parsedDate)
                cell.NumberFormat = "dd.mm.yyyy"
                previousDate = parsedDate
                hasPrevious = True
            Else
                SH_KeepInvalidToken cell, raw
                SH_RecordQuickError firstError, errorCount, cell.Address(False, False), errorText
            End If
        Else
            dayOffset = 0
            If SH_TryParseTime(raw, previousTime, hasPrevious, parsedTime, dayOffset, errorText) Then
                cell.Value2 = CDbl(parsedTime) - Int(CDbl(parsedTime))
                cell.NumberFormat = "hh:mm"
                previousTime = parsedTime
                hasPrevious = True
                If dayOffset <> 0 Then
                    Set paired = Sh.Cells(cell.Row, IIf(col = 3, 2, 9))
                    If SH_ReadDateCell(paired, pairedDate) Then
                        paired.Value2 = CDbl(DateAdd("d", dayOffset, pairedDate))
                        paired.NumberFormat = "dd.mm.yyyy"
                    Else
                        SH_RecordQuickError firstError, errorCount, paired.Address(False, False), _
                            SH_U("04220440043504310443043504420441044F0020043F04300440043D0430044F0020043404300442043000200434043B044F0020043F0435044004350445043E043404300020044704350440043504370020043F043E043B043D043E0447044C002E")
                    End If
                End If
            Else
                SH_KeepInvalidToken cell, raw
                SH_RecordQuickError firstError, errorCount, cell.Address(False, False), errorText
            End If
        End If
NextCell:
    Next cell

SafeExit:
    On Error Resume Next
    Application.EnableEvents = hadEvents
    mQuickGuard = False
    On Error GoTo 0
    If errorCount > 0 Then
        If errorCount > 1 Then firstError = firstError & vbCrLf & "... +" & CStr(errorCount - 1)
        MsgBox firstError, vbExclamation, "Shift-Helper"
    End If
    Exit Sub
Failed:
    If Len(firstError) = 0 Then firstError = Err.Description
    If Len(firstError) = 0 Then firstError = "Quick input failed (" & CStr(Err.Number) & ")."
    errorCount = Application.Max(1, errorCount)
    Resume SafeExit
End Sub

Private Function SH_IsQuickColumn(ByVal col As Long) As Boolean
    SH_IsQuickColumn = (col = 2 Or col = 3 Or col = 9 Or col = 10)
End Function

Private Function SH_QuickRawValue(ByVal cell As Range) As Variant
    Dim formulaText As String
    If cell.HasFormula Then
        formulaText = CStr(cell.Formula)
        If Left$(formulaText, 2) = "=+" And IsNumeric(Mid$(formulaText, 3)) Then
            SH_QuickRawValue = Mid$(formulaText, 2)
        Else
            SH_QuickRawValue = cell.Value2
        End If
    Else
        SH_QuickRawValue = cell.Value2
    End If
End Function

Private Function SH_QuickBlank(ByVal value As Variant) As Boolean
    SH_QuickBlank = IsEmpty(value) Or (VarType(value) = vbString And Len(Trim$(CStr(value))) = 0)
End Function

Private Sub SH_KeepInvalidToken(ByVal cell As Range, ByVal raw As Variant)
    cell.NumberFormat = "@"
    cell.Value2 = CStr(raw)
End Sub

Private Sub SH_RecordQuickError(ByRef firstError As String, ByRef count As Long, ByVal addressText As String, ByVal detail As String)
    count = count + 1
    If Len(firstError) = 0 Then firstError = addressText & ": " & detail
End Sub

Private Function SH_ReadDateCell(ByVal cell As Range, ByRef result As Date) As Boolean
    On Error GoTo InvalidValue
    Dim value As Variant
    value = cell.Value2
    If IsNumeric(value) Then
        If CDbl(value) > 10000 Then
            result = CDate(CDbl(value))
            SH_ReadDateCell = True
        End If
    ElseIf IsDate(value) Then
        result = CDate(value)
        SH_ReadDateCell = True
    End If
InvalidValue:
End Function

Private Function SH_ReadTimeCell(ByVal cell As Range, ByRef result As Date) As Boolean
    On Error GoTo InvalidValue
    Dim value As Variant, fraction As Double
    value = cell.Value2
    If IsNumeric(value) Then
        fraction = CDbl(value) - Int(CDbl(value))
        If fraction >= 0 And fraction < 1 Then
            result = CDate(fraction)
            SH_ReadTimeCell = True
        End If
    ElseIf IsDate(value) Then
        result = TimeValue(CDate(value))
        SH_ReadTimeCell = True
    End If
InvalidValue:
End Function

Private Function SH_TryParseDate(ByVal raw As Variant, ByVal previousDate As Date, ByVal hasPrevious As Boolean, ByRef result As Date, ByRef errorText As String) As Boolean
    On Error GoTo InvalidValue
    Dim token As String, normalized As String, parts As Variant, n As Double
    Dim dayValue As Long, monthValue As Long, yearValue As Long, amount As Long

    If VarType(raw) <> vbString And IsNumeric(raw) Then
        n = CDbl(raw)
        If n > 10000 Then
            result = CDate(n)
            SH_TryParseDate = True
            Exit Function
        End If
        token = CStr(CLng(n))
    Else
        token = Trim$(CStr(raw))
    End If
    If Len(token) = 0 Then Exit Function
    If token = "." Then
        If Not hasPrevious Then GoTo NeedPrevious
        result = previousDate
        SH_TryParseDate = True
        Exit Function
    End If
    If token = "!" Then
        result = Date
        SH_TryParseDate = True
        Exit Function
    End If
    If Left$(token, 1) = "+" And Len(token) > 1 And IsNumeric(Mid$(token, 2)) Then
        If Not hasPrevious Then GoTo NeedPrevious
        amount = CLng(Mid$(token, 2))
        result = DateAdd("d", amount, previousDate)
        SH_TryParseDate = True
        Exit Function
    End If

    If InStr(token, ".") > 0 Or InStr(token, "/") > 0 Or InStr(token, "-") > 0 Then
        normalized = Replace(Replace(token, "/", "."), "-", ".")
        parts = Split(normalized, ".")
        If UBound(parts) <> 2 Then GoTo InvalidValue
        If Len(parts(0)) = 4 Then
            yearValue = CLng(parts(0)): monthValue = CLng(parts(1)): dayValue = CLng(parts(2))
        Else
            dayValue = CLng(parts(0)): monthValue = CLng(parts(1)): yearValue = CLng(parts(2))
            If yearValue < 100 Then yearValue = 2000 + yearValue
        End If
        If SH_StrictDate(yearValue, monthValue, dayValue, result) Then SH_TryParseDate = True: Exit Function
        GoTo InvalidValue
    End If

    If Not IsNumeric(token) Then GoTo InvalidValue
    Select Case Len(token)
        Case 1, 2
            dayValue = CLng(token): monthValue = Month(Date): yearValue = Year(Date)
        Case 4
            dayValue = CLng(Left$(token, 2)): monthValue = CLng(Right$(token, 2)): yearValue = Year(Date)
        Case 6
            dayValue = CLng(Left$(token, 2)): monthValue = CLng(Mid$(token, 3, 2)): yearValue = 2000 + CLng(Right$(token, 2))
        Case 8
            dayValue = CLng(Left$(token, 2)): monthValue = CLng(Mid$(token, 3, 2)): yearValue = CLng(Right$(token, 4))
        Case Else
            GoTo InvalidValue
    End Select
    If SH_StrictDate(yearValue, monthValue, dayValue, result) Then SH_TryParseDate = True: Exit Function
InvalidValue:
    errorText = SH_U("041D0435043A043E044004400435043A0442043D0430044F00200434043004420430002E")
    Exit Function
NeedPrevious:
    errorText = SH_U("0422043E043A0435043D002004420440043504310443043504420020043F044004350434044B043404430449043504350433043E0020043A043E044004400435043A0442043D043E0433043E00200437043D043004470435043D0438044F00200432044B04480435002E")
End Function

Private Function SH_StrictDate(ByVal yearValue As Long, ByVal monthValue As Long, ByVal dayValue As Long, ByRef result As Date) As Boolean
    On Error GoTo InvalidValue
    result = DateSerial(yearValue, monthValue, dayValue)
    SH_StrictDate = (Year(result) = yearValue And Month(result) = monthValue And Day(result) = dayValue)
InvalidValue:
End Function

Private Function SH_TryParseTime(ByVal raw As Variant, ByVal previousTime As Date, ByVal hasPrevious As Boolean, ByRef result As Date, ByRef dayOffset As Long, ByRef errorText As String) As Boolean
    On Error GoTo InvalidValue
    Dim token As String, parts As Variant, n As Double, total As Long
    Dim hourValue As Long, minuteValue As Long, amount As Long

    dayOffset = 0
    If VarType(raw) <> vbString And IsNumeric(raw) Then
        n = CDbl(raw)
        If n >= 0 And n < 1 Then
            result = CDate(n)
            SH_TryParseTime = True
            Exit Function
        End If
        token = CStr(CLng(n))
    Else
        token = Trim$(CStr(raw))
    End If
    If Len(token) = 0 Then Exit Function
    If token = "." Then
        If Not hasPrevious Then GoTo NeedPrevious
        result = previousTime
        SH_TryParseTime = True
        Exit Function
    End If
    If token = "!" Then
        result = TimeSerial(Hour(Now), Minute(Now), 0)
        SH_TryParseTime = True
        Exit Function
    End If
    If Left$(token, 1) = "+" And Len(token) > 1 And IsNumeric(Mid$(token, 2)) Then
        If Not hasPrevious Then GoTo NeedPrevious
        amount = CLng(Mid$(token, 2))
        total = Hour(previousTime) * 60 + Minute(previousTime) + amount
        dayOffset = total \ 1440
        total = total Mod 1440
        result = TimeSerial(total \ 60, total Mod 60, 0)
        SH_TryParseTime = True
        Exit Function
    End If
    If InStr(token, ":") > 0 Then
        parts = Split(token, ":")
        If UBound(parts) < 1 Or UBound(parts) > 2 Then GoTo InvalidValue
        hourValue = CLng(parts(0)): minuteValue = CLng(parts(1))
        If UBound(parts) = 2 Then If CLng(parts(2)) > 59 Then GoTo InvalidValue
    Else
        If Not IsNumeric(token) Then GoTo InvalidValue
        Select Case Len(token)
            Case 1, 2
                hourValue = CLng(token): minuteValue = 0
            Case 3
                hourValue = CLng(Left$(token, 1)): minuteValue = CLng(Right$(token, 2))
            Case 4
                hourValue = CLng(Left$(token, 2)): minuteValue = CLng(Right$(token, 2))
            Case Else
                GoTo InvalidValue
        End Select
    End If
    If hourValue < 0 Or hourValue > 23 Or minuteValue < 0 Or minuteValue > 59 Then GoTo InvalidValue
    result = TimeSerial(hourValue, minuteValue, 0)
    SH_TryParseTime = True
    Exit Function
InvalidValue:
    errorText = SH_U("041D0435043A043E044004400435043A0442043D043E04350020043204400435043C044F002E")
    Exit Function
NeedPrevious:
    errorText = SH_U("0422043E043A0435043D002004420440043504310443043504420020043F044004350434044B043404430449043504350433043E0020043A043E044004400435043A0442043D043E0433043E00200437043D043004470435043D0438044F00200432044B04480435002E")
End Function
