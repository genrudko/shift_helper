Attribute VB_Name = "modShiftHelperQuickInput"
Option Explicit

Public SH_AppEvents As CShiftHelperAppEvents
Private mQuickEnabled As Boolean
Private mQuickGuard As Boolean
Private Const SH_QUICK_PREVIOUS_LIMIT As Long = 1000

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
    On Error Resume Next
    Application.EnableEvents = True
    On Error GoTo 0
    If Not Application.EnableEvents Then
        MsgBox "Quick input is enabled but unavailable: Excel events are off.", vbExclamation, "Shift-Helper"
    ElseIf TypeName(ActiveSheet) = "Worksheet" And Not SH_QuickInputEventAllowed(ActiveSheet) Then
        MsgBox "Quick input is enabled globally but unavailable in this legacy workbook.", vbExclamation, "Shift-Helper"
    Else
        MsgBox SH_U("0411044B044104420440044B0439002004320432043E043400200432043A043B044E04470451043D002E"), vbInformation, "Shift-Helper"
    End If
End Sub

Public Sub SH_DisableQuickInput()
    SH_InitializeAddin
    mQuickEnabled = False
    SaveSetting "Shift-Helper", "Journal", "QuickInput", "0"
    MsgBox SH_U("0411044B044104420440044B0439002004320432043E043400200432044B043A043B044E04470435043D002E"), vbInformation, "Shift-Helper"
End Sub

Public Sub SH_ShowQuickInputStatus()
    SH_InitializeAddin
    If mQuickEnabled And Application.EnableEvents And TypeName(ActiveSheet) = "Worksheet" And _
        SH_QuickInputEventAllowed(ActiveSheet) Then
        MsgBox SH_U("0411044B044104420440044B0439002004320432043E0434003A00200432043A043B044E04470451043D002E"), vbInformation, "Shift-Helper"
    ElseIf Not mQuickEnabled Then
        MsgBox SH_U("0411044B044104420440044B0439002004320432043E0434003A00200432044B043A043B044E04470435043D002E"), vbInformation, "Shift-Helper"
    ElseIf Not Application.EnableEvents Then
        MsgBox "Quick input is enabled but unavailable: Excel events are off.", vbExclamation, "Shift-Helper"
    Else
        MsgBox "Quick input is enabled globally but unavailable in this legacy workbook.", vbExclamation, "Shift-Helper"
    End If
End Sub

Public Sub SH_PrepareQuickInputSelection(ByVal Sh As Object, ByVal Target As Range)
    On Error GoTo SafeExit
    Dim cell As Range, col As Long
    SH_InitializeAddin
    If Not mQuickEnabled Or mQuickGuard Then Exit Sub
    If TypeName(Sh) <> "Worksheet" Then Exit Sub
    If Target Is Nothing Then Exit Sub
    If Target.Areas.Count <> 1 Then Exit Sub
    If Target.Cells.CountLarge > 256 Then Exit Sub
    For Each cell In Target.Cells
        col = cell.Column
        If SH_QuickFieldKind(Sh, col) <> 0 Then
            If cell.Row > 1 And Len(CStr(cell.Value2)) = 0 And Not cell.HasFormula Then cell.NumberFormat = "@"
        End If
    Next cell
SafeExit:
End Sub

Public Sub SH_HandleQuickInputChange(ByVal Sh As Object, ByVal Target As Range)
    On Error GoTo Failed
    Dim col As Long, rowOffset As Long, colOffset As Long, fieldKind As Long
    Dim cell As Range, raw As Variant, parsedDate As Date, parsedTime As Date, dayOffset As Long
    Dim parsedCombined As Date, previousDate As Date, previousTime As Date, hasPrevious As Boolean
    Dim errorText As String, firstError As String, errorCount As Long
    Dim paired As Range, pairedDate As Date, hadEvents As Boolean

    SH_InitializeAddin
    If Not mQuickEnabled Or mQuickGuard Then Exit Sub
    If TypeName(Sh) <> "Worksheet" Then Exit Sub
    If Target Is Nothing Then Exit Sub
    If Target.Areas.Count <> 1 Then Exit Sub
    If Target.Cells.CountLarge > 256 Then Exit Sub
    If Target.Row <= 1 Then Exit Sub

    mQuickGuard = True
    hadEvents = Application.EnableEvents
    Application.EnableEvents = False

    For rowOffset = 1 To Target.Rows.Count
      For colOffset = 1 To Target.Columns.Count
        Set cell = Target.Cells(rowOffset, colOffset)
        If cell.Row <= 1 Then GoTo NextCell
        col = cell.Column
        fieldKind = SH_QuickFieldKind(Sh, col)
        If fieldKind = 0 Then GoTo NextCell
        raw = SH_QuickRawValue(cell)
        If SH_QuickBlank(raw) Then GoTo NextCell
        errorText = ""
        If fieldKind = 1 Then
            hasPrevious = SH_FindPreviousDate(Sh, cell.Row - 1, col, previousDate)
            If SH_TryParseDate(raw, previousDate, hasPrevious, parsedDate, errorText) Then
                cell.Value2 = CDbl(parsedDate)
                cell.NumberFormat = "dd.mm.yyyy"
                previousDate = parsedDate
                hasPrevious = True
            Else
                SH_KeepInvalidToken cell, raw
                SH_RecordQuickError firstError, errorCount, cell.Address(False, False), errorText
            End If
        ElseIf fieldKind = 2 Then
            hasPrevious = SH_FindPreviousTime(Sh, cell.Row - 1, col, previousTime)
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
        Else
            hasPrevious = SH_FindPreviousCombined(Sh, cell.Row - 1, col, parsedCombined)
            If SH_TryParseCombined(raw, parsedCombined, hasPrevious, parsedCombined, errorText) Then
                cell.Value2 = CDbl(parsedCombined)
                If SH_QuickCombinedNeedsSeconds(Sh, col) Then
                    cell.NumberFormat = "dd.mm.yyyy hh:mm:ss"
                Else
                    cell.NumberFormat = "dd.mm.yyyy hh:mm"
                End If
            Else
                SH_KeepInvalidToken cell, raw
                SH_RecordQuickError firstError, errorCount, cell.Address(False, False), errorText
            End If
        End If
NextCell:
      Next colOffset
    Next rowOffset

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

Private Function SH_QuickFieldKind(ByVal Sh As Object, ByVal col As Long) As Long
    Dim columns As Variant, item As Variant
    If Sh.Name = SH_JournalSheetName() Then
        If col = 2 Or col = 9 Then SH_QuickFieldKind = 1
        If col = 3 Or col = 10 Then SH_QuickFieldKind = 2
        Exit Function
    End If
    columns = SH_QuickCombinedColumns(Sh.Name)
    If IsEmpty(columns) Then Exit Function
    For Each item In columns
        If col = CLng(item) Then SH_QuickFieldKind = 3: Exit Function
    Next item
End Function

Private Function SH_QuickCombinedColumns(ByVal sheetName As String) As Variant
    Select Case sheetName
        Case SH_InputSheetName(2): SH_QuickCombinedColumns = Array(3, 6)
        Case SH_InputSheetName(3): SH_QuickCombinedColumns = Array(5, 6)
        Case SH_InputSheetName(4): SH_QuickCombinedColumns = Array(4)
        Case SH_InputSheetName(5): SH_QuickCombinedColumns = Array(10, 11)
        Case SH_InputSheetName(6): SH_QuickCombinedColumns = Array(9, 10)
        Case SH_InputSheetName(7): SH_QuickCombinedColumns = Array(3, 10)
        Case Else: SH_QuickCombinedColumns = Empty
    End Select
End Function

Private Function SH_QuickCombinedNeedsSeconds(ByVal Sh As Object, ByVal col As Long) As Boolean
    SH_QuickCombinedNeedsSeconds = (Sh.Name = SH_InputSheetName(5) And (col = 10 Or col = 11))
End Function

Private Function SH_FindPreviousDate(ByVal Sh As Object, ByVal startRow As Long, ByVal col As Long, ByRef result As Date) As Boolean
    Dim scanRow As Long
    For scanRow = startRow To Application.Max(2, startRow - SH_QUICK_PREVIOUS_LIMIT) Step -1
        If SH_ReadDateCell(Sh.Cells(scanRow, col), result) Then SH_FindPreviousDate = True: Exit Function
    Next scanRow
End Function

Private Function SH_FindPreviousTime(ByVal Sh As Object, ByVal startRow As Long, ByVal col As Long, ByRef result As Date) As Boolean
    Dim scanRow As Long
    For scanRow = startRow To Application.Max(2, startRow - SH_QUICK_PREVIOUS_LIMIT) Step -1
        If SH_ReadTimeCell(Sh.Cells(scanRow, col), result) Then SH_FindPreviousTime = True: Exit Function
    Next scanRow
End Function

Private Function SH_FindPreviousCombined(ByVal Sh As Object, ByVal startRow As Long, ByVal col As Long, ByRef result As Date) As Boolean
    Dim scanRow As Long, value As Variant
    For scanRow = startRow To Application.Max(2, startRow - SH_QUICK_PREVIOUS_LIMIT) Step -1
        value = Sh.Cells(scanRow, col).Value2
        If IsNumeric(value) And CDbl(value) >= 20000# And CDbl(value) < 80000# Then
            result = CDate(CDbl(value)): SH_FindPreviousCombined = True: Exit Function
        End If
    Next scanRow
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
        If CDbl(value) = Int(CDbl(value)) Then Exit Function
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
    Dim token As String, normalized As String, parts As Variant, n As Double, candidate As String
    Dim dayValue As Long, monthValue As Long, yearValue As Long, amount As Long

    If VarType(raw) <> vbString And IsNumeric(raw) Then
        n = CDbl(raw)
        ' Numeric coercion loses provenance. A compact DDMMYY integer inside this
        ' operational window is indistinguishable from a real serial; serial wins.
        If SH_IsPlausibleOperationalDateSerial(n) Then
            result = CDate(n)
            SH_TryParseDate = True
            Exit Function
        End If
        If n = Int(n) Then
            candidate = Right$("000000" & CStr(CLng(n)), 6)
            If Len(CStr(CLng(n))) <= 6 Then
                If SH_StrictDate(2000 + CLng(Right$(candidate, 2)), CLng(Mid$(candidate, 3, 2)), _
                    CLng(Left$(candidate, 2)), result) Then SH_TryParseDate = True: Exit Function
            End If
        End If
        If n >= 20000# And n < 80000# Then
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
    If SH_StrictPositiveIncrement(token, amount) Then
        If Not hasPrevious Then GoTo NeedPrevious
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

Private Function SH_IsPlausibleOperationalDateSerial(ByVal value As Double) As Boolean
    If value <> Int(value) Then Exit Function
    SH_IsPlausibleOperationalDateSerial = _
        (value >= CDbl(DateSerial(1990, 1, 1)) And _
         value <= CDbl(DateAdd("yyyy", 10, Date)))
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
    Dim hourValue As Long, minuteValue As Long, secondValue As Long, amount As Long

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
    If SH_StrictPositiveIncrement(token, amount) Then
        If Not hasPrevious Then GoTo NeedPrevious
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
        If Not SH_IsDigits(CStr(parts(0))) Then GoTo InvalidValue
        If Not SH_IsDigits(CStr(parts(1))) Then GoTo InvalidValue
        hourValue = CLng(parts(0)): minuteValue = CLng(parts(1))
        If UBound(parts) = 2 Then
            If Not SH_IsDigits(CStr(parts(2))) Then GoTo InvalidValue
            secondValue = CLng(parts(2))
            If secondValue < 0 Or secondValue > 59 Then GoTo InvalidValue
        End If
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
    result = TimeSerial(hourValue, minuteValue, secondValue)
    SH_TryParseTime = True
    Exit Function
InvalidValue:
    errorText = SH_U("041D0435043A043E044004400435043A0442043D043E04350020043204400435043C044F002E")
    Exit Function
NeedPrevious:
    errorText = SH_U("0422043E043A0435043D002004420440043504310443043504420020043F044004350434044B043404430449043504350433043E0020043A043E044004400435043A0442043D043E0433043E00200437043D043004470435043D0438044F00200432044B04480435002E")
End Function

Private Function SH_IsDigits(ByVal token As String) As Boolean
    Dim i As Long, ch As String
    If Len(token) = 0 Then Exit Function
    For i = 1 To Len(token)
        ch = Mid$(token, i, 1)
        If ch < "0" Or ch > "9" Then Exit Function
    Next i
    SH_IsDigits = True
End Function

Private Function SH_StrictPositiveIncrement(ByVal token As String, ByRef amount As Long) As Boolean
    Dim i As Long, ch As String
    If Len(token) < 2 Or Left$(token, 1) <> "+" Then Exit Function
    For i = 2 To Len(token)
        ch = Mid$(token, i, 1)
        If ch < "0" Or ch > "9" Then Exit Function
    Next i
    On Error GoTo InvalidValue
    amount = CLng(Mid$(token, 2))
    SH_StrictPositiveIncrement = (amount > 0)
InvalidValue:
End Function

Private Function SH_TryParseCombined(ByVal raw As Variant, ByVal previousValue As Date, _
    ByVal hasPrevious As Boolean, ByRef result As Date, ByRef errorText As String) As Boolean
    On Error GoTo InvalidValue
    Dim token As String, pieces As Variant, parsedDate As Date, parsedTime As Date
    Dim ignoredOffset As Long, amount As Long, hasSeconds As Boolean
    If VarType(raw) <> vbString And IsNumeric(raw) Then
        If CDbl(raw) >= 20000# And CDbl(raw) < 80000# Then
            result = CDate(CDbl(raw)): SH_TryParseCombined = True: Exit Function
        End If
    End If
    token = Trim$(CStr(raw))
    If token = "!" Then result = Now: SH_TryParseCombined = True: Exit Function
    If token = "." Then
        If Not hasPrevious Then GoTo NeedPrevious
        result = previousValue: SH_TryParseCombined = True: Exit Function
    End If
    If SH_StrictPositiveIncrement(token, amount) Then
        If Not hasPrevious Then GoTo NeedPrevious
        result = DateAdd("n", amount, previousValue): SH_TryParseCombined = True: Exit Function
    End If
    pieces = Split(token, " ")
    If UBound(pieces) = 0 Then
        If Not hasPrevious Then GoTo NeedPrevious
        If SH_TryParseTime(pieces(0), 0, False, parsedTime, ignoredOffset, errorText) Then
            result = DateValue(previousValue) + TimeValue(parsedTime)
            SH_TryParseCombined = True
            Exit Function
        End If
        GoTo InvalidValue
    End If
    If UBound(pieces) <> 1 Then GoTo InvalidValue
    If Not SH_TryParseDate(pieces(0), 0, False, parsedDate, errorText) Then GoTo InvalidValue
    If Not SH_TryParseTime(pieces(1), 0, False, parsedTime, ignoredOffset, errorText) Then GoTo InvalidValue
    hasSeconds = (Len(pieces(1)) - Len(Replace(pieces(1), ":", "")) = 2)
    If hasSeconds Then parsedTime = TimeSerial(Hour(parsedTime), Minute(parsedTime), CLng(Split(pieces(1), ":")(2)))
    result = DateValue(parsedDate) + TimeValue(parsedTime)
    SH_TryParseCombined = True
    Exit Function
InvalidValue:
    errorText = "Invalid combined date/time."
    Exit Function
NeedPrevious:
    errorText = "A previous valid combined date/time is required."
End Function
