Attribute VB_Name = "modShiftHelperCalendar"
Option Explicit

#If VBA7 Then
Private Declare PtrSafe Function InitCommonControlsEx Lib "comctl32.dll" (ByRef lpInitCtrls As SH_INITCOMMONCONTROLSEX) As Long
Private Declare PtrSafe Function CreateWindowExW Lib "user32" (ByVal dwExStyle As Long, ByVal lpClassName As LongPtr, ByVal lpWindowName As LongPtr, ByVal dwStyle As Long, ByVal x As Long, ByVal y As Long, ByVal nWidth As Long, ByVal nHeight As Long, ByVal hWndParent As LongPtr, ByVal hMenu As LongPtr, ByVal hInstance As LongPtr, ByVal lpParam As LongPtr) As LongPtr
Private Declare PtrSafe Function DestroyWindow Lib "user32" (ByVal hwnd As LongPtr) As Long
Private Declare PtrSafe Function MoveWindow Lib "user32" (ByVal hwnd As LongPtr, ByVal x As Long, ByVal y As Long, ByVal nWidth As Long, ByVal nHeight As Long, ByVal bRepaint As Long) As Long
Private Declare PtrSafe Function GetWindowRect Lib "user32" (ByVal hwnd As LongPtr, ByRef lpRect As SH_RECT) As Long
Private Declare PtrSafe Function IsWindow Lib "user32" (ByVal hwnd As LongPtr) As Long
Private Declare PtrSafe Function SetForegroundWindow Lib "user32" (ByVal hwnd As LongPtr) As Long
Private Declare PtrSafe Function SendMessageW Lib "user32" (ByVal hwnd As LongPtr, ByVal Msg As Long, ByVal wParam As LongPtr, ByRef lParam As Any) As LongPtr
Private Declare PtrSafe Function GetModuleHandleW Lib "kernel32" (ByVal lpModuleName As LongPtr) As LongPtr
Private Declare PtrSafe Function GetAsyncKeyState Lib "user32" (ByVal vKey As Long) As Integer
Private Declare PtrSafe Function GetCursorPos Lib "user32" (ByRef lpPoint As SH_POINT) As Long
Private Declare PtrSafe Sub Sleep Lib "kernel32" (ByVal dwMilliseconds As Long)
#End If

Private Type SH_INITCOMMONCONTROLSEX
    dwSize As Long
    dwICC As Long
End Type

Private Type SH_RECT
    Left As Long
    Top As Long
    Right As Long
    Bottom As Long
End Type

Private Type SH_POINT
    x As Long
    y As Long
End Type

Private Type SH_SYSTEMTIME
    wYear As Integer
    wMonth As Integer
    wDayOfWeek As Integer
    wDay As Integer
    wHour As Integer
    wMinute As Integer
    wSecond As Integer
    wMilliseconds As Integer
End Type

Private Const SH_ICC_DATE_CLASSES As Long = &H100
Private Const SH_WS_POPUP As Long = &H80000000
Private Const SH_WS_CHILD As Long = &H40000000
Private Const SH_WS_VISIBLE As Long = &H10000000
Private Const SH_WS_CAPTION As Long = &HC00000
Private Const SH_WS_SYSMENU As Long = &H80000
Private Const SH_WS_BORDER As Long = &H800000
Private Const SH_WS_EX_TOOLWINDOW As Long = &H80
Private Const SH_WS_EX_DLGMODALFRAME As Long = &H1
Private Const SH_MCM_FIRST As Long = &H1000
Private Const SH_MCM_GETCURSEL As Long = SH_MCM_FIRST + 1
Private Const SH_MCM_SETCURSEL As Long = SH_MCM_FIRST + 2
Private Const SH_MCM_GETMINREQRECT As Long = SH_MCM_FIRST + 9
Private Const SH_VK_LBUTTON As Long = &H1
Private Const SH_VK_RETURN As Long = &HD
Private Const SH_VK_ESCAPE As Long = &H1B

Public Sub SH_ShowCalendar()
    On Error GoTo Failed
    Dim wb As Workbook, prep As Worksheet, initialDate As Date, selectedDate As Date
    Dim currentValue As Variant, picked As Boolean, stage As String
    Dim errNumber As Long, errDescription As String

    stage = "resolve journal workbook"
    Set wb = SH_JournalBook()
    stage = "prepare report settings"
    Set prep = SH_EnsurePrepSheet(wb)
    currentValue = prep.Range(SH_ReportDateCell()).Value
    If SH_CalendarTryDate(currentValue, initialDate) Then
        initialDate = DateValue(initialDate)
    Else
        initialDate = Date
    End If

    stage = "show calendar"
    picked = SH_PickDateNative(initialDate, selectedDate)
    If picked Then
        stage = "apply selected report date"
        SH_ApplyReportCalendarDate wb, selectedDate
    End If
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    SH_ShowCalendarError "calendar / " & stage, errNumber, errDescription
End Sub

Public Sub SH_InsertDateIntoSelection()
    On Error GoTo Failed
    Dim wb As Workbook, target As Range, initialDate As Date, selectedDate As Date, picked As Boolean
    Dim cell As Range, errNumber As Long, errDescription As String, stage As String

    stage = "resolve journal selection"
    Set wb = SH_JournalBook()
    Set target = SH_SelectionRange(wb)
    If SH_CalendarTryDate(target.Cells(1, 1).Value, initialDate) Then
        initialDate = DateValue(initialDate)
    Else
        initialDate = Date
    End If

    stage = "show calendar"
    picked = SH_PickDateNative(initialDate, selectedDate)
    If Not picked Then Exit Sub
    stage = "write selected date"
    For Each cell In target.Cells
        cell.Value = selectedDate
        cell.NumberFormat = "dd.mm.yyyy"
    Next cell
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    SH_ShowCalendarError "date / " & stage, errNumber, errDescription
End Sub

Private Function SH_PickDateNative(ByVal initialDate As Date, ByRef selectedDate As Date) As Boolean
    On Error GoTo Failed
    Dim controls As SH_INITCOMMONCONTROLSEX, ownerRect As SH_RECT, calendarRect As SH_RECT
    Dim parentRect As SH_RECT, point As SH_POINT, st As SH_SYSTEMTIME
    Dim ownerHwnd As LongPtr, parentHwnd As LongPtr, calendarHwnd As LongPtr, instanceHwnd As LongPtr
    Dim parentClass As String, calendarClass As String, titleText As String
    Dim width As Long, height As Long, x As Long, y As Long
    Dim currentDate As Date, mouseDown As Boolean, wasMouseDown As Boolean
    Dim errNumber As Long, errDescription As String

    controls.dwSize = LenB(controls)
    controls.dwICC = SH_ICC_DATE_CLASSES
    If InitCommonControlsEx(controls) = 0 Then Err.Raise vbObjectError + 550, , "Windows calendar control is unavailable."

    ownerHwnd = CLngPtr(Application.hwnd)
    instanceHwnd = GetModuleHandleW(0)
    parentClass = "STATIC"
    calendarClass = "SysMonthCal32"
    titleText = SH_U("041A0430043B0435043D043404300440044C0020201400200045006E007400650072003A00200432044B0431044004300442044C")

    If GetWindowRect(ownerHwnd, ownerRect) = 0 Then
        ownerRect.Left = 100
        ownerRect.Top = 100
        ownerRect.Right = 900
        ownerRect.Bottom = 700
    End If
    width = 300
    height = 250
    x = ownerRect.Left + ((ownerRect.Right - ownerRect.Left) - width) \ 2
    y = ownerRect.Top + ((ownerRect.Bottom - ownerRect.Top) - height) \ 2

    parentHwnd = CreateWindowExW( _
        SH_WS_EX_TOOLWINDOW Or SH_WS_EX_DLGMODALFRAME, StrPtr(parentClass), StrPtr(titleText), _
        SH_WS_POPUP Or SH_WS_CAPTION Or SH_WS_SYSMENU Or SH_WS_BORDER Or SH_WS_VISIBLE, _
        x, y, width, height, ownerHwnd, 0, instanceHwnd, 0)
    If parentHwnd = 0 Then Err.Raise vbObjectError + 551, , "Cannot create calendar window."

    calendarHwnd = CreateWindowExW( _
        0, StrPtr(calendarClass), 0, SH_WS_CHILD Or SH_WS_VISIBLE, _
        8, 8, 270, 190, parentHwnd, 1001, instanceHwnd, 0)
    If calendarHwnd = 0 Then Err.Raise vbObjectError + 552, , "Cannot create Windows month calendar."

    SH_DateToSystemTime initialDate, st
    SendMessageW calendarHwnd, SH_MCM_SETCURSEL, 0, st
    If SendMessageW(calendarHwnd, SH_MCM_GETMINREQRECT, 0, calendarRect) <> 0 Then
        width = calendarRect.Right + 28
        height = calendarRect.Bottom + 48
        MoveWindow calendarHwnd, 8, 8, calendarRect.Right + 8, calendarRect.Bottom + 8, 1
        MoveWindow parentHwnd, x, y, width, height, 1
    End If
    SetForegroundWindow parentHwnd

    Do While IsWindow(parentHwnd) <> 0
        DoEvents
        If GetAsyncKeyState(SH_VK_ESCAPE) < 0 Then Exit Do
        If GetAsyncKeyState(SH_VK_RETURN) < 0 Then
            If SH_ReadCalendarDate(calendarHwnd, selectedDate) Then SH_PickDateNative = True
            Exit Do
        End If
        If SH_ReadCalendarDate(calendarHwnd, currentDate) Then
            If DateValue(currentDate) <> DateValue(initialDate) Then
                selectedDate = currentDate
                SH_PickDateNative = True
                Exit Do
            End If
        End If
        mouseDown = (GetAsyncKeyState(SH_VK_LBUTTON) < 0)
        If wasMouseDown And Not mouseDown Then
            If GetCursorPos(point) <> 0 And GetWindowRect(calendarHwnd, parentRect) <> 0 Then
                If point.x >= parentRect.Left And point.x <= parentRect.Right And _
                   point.y >= parentRect.Top + 34 And point.y <= parentRect.Bottom - 12 Then
                    If SH_ReadCalendarDate(calendarHwnd, selectedDate) Then SH_PickDateNative = True
                    Exit Do
                End If
            End If
        End If
        wasMouseDown = mouseDown
        Sleep 15
    Loop

CleanExit:
    On Error Resume Next
    If parentHwnd <> 0 Then DestroyWindow parentHwnd
    SetForegroundWindow CLngPtr(Application.hwnd)
    On Error GoTo 0
    Exit Function
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    On Error Resume Next
    If parentHwnd <> 0 Then DestroyWindow parentHwnd
    SetForegroundWindow CLngPtr(Application.hwnd)
    On Error GoTo 0
    If errNumber = 0 Then errNumber = vbObjectError + 553
    If Len(errDescription) = 0 Then errDescription = "Native calendar failed."
    Err.Raise errNumber, , errDescription
End Function

Private Function SH_ReadCalendarDate(ByVal calendarHwnd As LongPtr, ByRef value As Date) As Boolean
    Dim st As SH_SYSTEMTIME
    If calendarHwnd = 0 Then Exit Function
    If SendMessageW(calendarHwnd, SH_MCM_GETCURSEL, 0, st) = 0 Then Exit Function
    On Error GoTo InvalidDate
    value = DateSerial(CLng(st.wYear), CLng(st.wMonth), CLng(st.wDay))
    SH_ReadCalendarDate = True
    Exit Function
InvalidDate:
    SH_ReadCalendarDate = False
End Function

Private Sub SH_ApplyReportCalendarDate(ByVal wb As Workbook, ByVal selectedDate As Date)
    On Error GoTo Failed
    Dim prep As Worksheet, stage As String, errDescription As String, errNumber As Long
    Dim oldCalculation As XlCalculation, oldEvents As Boolean, oldScreenUpdating As Boolean
    Dim appStateCaptured As Boolean

    stage = "capture Excel state"
    oldCalculation = Application.Calculation
    oldEvents = Application.EnableEvents
    oldScreenUpdating = Application.ScreenUpdating
    appStateCaptured = True
    Application.Calculation = xlCalculationManual
    Application.EnableEvents = False
    Application.ScreenUpdating = False

    stage = "write report date"
    Set prep = SH_EnsurePrepSheet(wb)
    prep.Range(SH_ReportDateCell()).Value = DateValue(selectedDate)
    prep.Range(SH_ReportDateCell()).NumberFormat = "dd.mm.yyyy"
    prep.Range("B4").Value = DateValue(selectedDate) - 1 + TimeSerial(7, 0, 0)
    prep.Range("B4").NumberFormat = "dd.mm.yyyy hh:mm"
    prep.Range("B5").Value = DateValue(selectedDate) + TimeSerial(7, 0, 0)
    prep.Range("B5").NumberFormat = "dd.mm.yyyy hh:mm"

    If SH_ReportInputsReady(wb) Then
        stage = "apply report formulas"
        SH_ApplyCriticalFormulas wb
        stage = "refresh emergency outages"
        SH_RefreshEmergencyOutages wb
        stage = "calculate report inputs"
        SH_CalculateReportInputs wb
    End If

    Application.Calculation = oldCalculation
    Application.EnableEvents = oldEvents
    Application.ScreenUpdating = oldScreenUpdating
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
    If errNumber = 0 Then errNumber = vbObjectError + 554
    If Len(errDescription) = 0 Then errDescription = "Could not apply selected report date."
    Err.Raise errNumber, , "Stage [" & stage & "]: " & errDescription
End Sub

Private Function SH_ReportInputsReady(ByVal wb As Workbook) As Boolean
    Dim i As Long
    For i = 1 To SH_ReportSheetCount()
        If Not SH_HasSheet(wb, SH_InputSheetName(i)) Then Exit Function
    Next i
    SH_ReportInputsReady = True
End Function

Private Function SH_CalendarTryDate(ByVal value As Variant, ByRef result As Date) As Boolean
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If VarType(value) = vbString Then
        If Len(Trim$(CStr(value))) = 0 Then Exit Function
    End If
    If IsDate(value) Or IsNumeric(value) Then
        result = CDate(value)
        SH_CalendarTryDate = True
    End If
    Exit Function
Failed:
    SH_CalendarTryDate = False
End Function

Private Sub SH_DateToSystemTime(ByVal value As Date, ByRef st As SH_SYSTEMTIME)
    st.wYear = CInt(Year(value))
    st.wMonth = CInt(Month(value))
    st.wDay = CInt(Day(value))
End Sub

Private Sub SH_ShowCalendarError(ByVal operationName As String, ByVal errNumber As Long, ByVal errDescription As String)
    Dim message As String
    message = errDescription
    If Len(message) = 0 Then message = "Calendar operation failed."
    MsgBox "[#" & CStr(errNumber) & "] " & operationName & ": " & message, vbExclamation, "Shift-Helper"
End Sub
