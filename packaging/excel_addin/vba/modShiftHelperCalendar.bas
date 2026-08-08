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
Private Declare PtrSafe Function CallWindowProcW Lib "user32" (ByVal lpPrevWndFunc As LongPtr, ByVal hwnd As LongPtr, ByVal Msg As Long, ByVal wParam As LongPtr, ByVal lParam As LongPtr) As LongPtr
Private Declare PtrSafe Function SendMessageW Lib "user32" (ByVal hwnd As LongPtr, ByVal Msg As Long, ByVal wParam As LongPtr, ByRef lParam As Any) As LongPtr
Private Declare PtrSafe Function GetModuleHandleW Lib "kernel32" (ByVal lpModuleName As LongPtr) As LongPtr
Private Declare PtrSafe Sub Sleep Lib "kernel32" (ByVal dwMilliseconds As Long)
Private Declare PtrSafe Sub SH_CopyMemory Lib "kernel32" Alias "RtlMoveMemory" (ByRef Destination As Any, ByVal Source As LongPtr, ByVal Length As LongPtr)
#If Win64 Then
Private Declare PtrSafe Function SetWindowLongPtrW Lib "user32" (ByVal hwnd As LongPtr, ByVal nIndex As Long, ByVal dwNewLong As LongPtr) As LongPtr
#Else
Private Declare PtrSafe Function SetWindowLongPtrW Lib "user32" Alias "SetWindowLongW" (ByVal hwnd As LongPtr, ByVal nIndex As Long, ByVal dwNewLong As LongPtr) As LongPtr
#End If
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

Private Type SH_NMHDR
    hwndFrom As LongPtr
    idFrom As LongPtr
    code As Long
End Type

Private Const SH_ICC_DATE_CLASSES As Long = &H100
Private Const SH_WS_POPUP As Long = &H80000000
Private Const SH_WS_CHILD As Long = &H40000000
Private Const SH_WS_VISIBLE As Long = &H10000000
Private Const SH_WS_CAPTION As Long = &HC00000
Private Const SH_WS_SYSMENU As Long = &H80000
Private Const SH_WS_EX_TOOLWINDOW As Long = &H80
Private Const SH_WS_EX_DLGMODALFRAME As Long = &H1
Private Const SH_GWL_WNDPROC As Long = -4
Private Const SH_WM_CLOSE As Long = &H10
Private Const SH_WM_DESTROY As Long = &H2
Private Const SH_WM_NOTIFY As Long = &H4E
Private Const SH_MCM_FIRST As Long = &H1000
Private Const SH_MCM_GETCURSEL As Long = SH_MCM_FIRST + 1
Private Const SH_MCM_SETCURSEL As Long = SH_MCM_FIRST + 2
Private Const SH_MCM_GETMINREQRECT As Long = SH_MCM_FIRST + 9
Private Const SH_MCN_FIRST As Long = -750
Private Const SH_MCN_SELECT As Long = SH_MCN_FIRST - 4

Private mCalendarWindow As LongPtr
Private mCalendarControl As LongPtr
Private mCalendarOldProc As LongPtr
Private mCalendarDone As Boolean
Private mCalendarPicked As Boolean
Private mCalendarSelected As Date
Private mCalendarJournal As Workbook

Public Sub SH_ShowCalendar()
    On Error GoTo Failed
    Dim wb As Workbook, prep As Worksheet, currentValue As Variant, initialDate As Date
    Set wb = SH_JournalBook()
    SH_EnsureReportContour wb
    Set prep = SH_RequireSheet(wb, SH_PrepSheetName())
    currentValue = prep.Range(SH_ReportDateCell()).Value
    If IsDate(currentValue) Or IsNumeric(currentValue) Then
        initialDate = CDate(currentValue)
    Else
        initialDate = Date
    End If

    Set mCalendarJournal = wb
    mCalendarDone = False
    mCalendarPicked = False
    mCalendarSelected = 0
    SH_CreateCalendarWindow initialDate

    Do While Not mCalendarDone
        If mCalendarWindow = 0 Then Exit Do
        If IsWindow(mCalendarWindow) = 0 Then Exit Do
        DoEvents
        Sleep 15
    Loop

    If mCalendarPicked Then SH_ApplyCalendarDate mCalendarJournal, mCalendarSelected
    SetForegroundWindow CLngPtr(Application.hwnd)
    SH_ResetCalendarState
    Exit Sub
Failed:
    On Error Resume Next
    If mCalendarWindow <> 0 Then DestroyWindow mCalendarWindow
    SH_ResetCalendarState
    On Error GoTo 0
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Private Sub SH_CreateCalendarWindow(ByVal initialDate As Date)
    Dim controls As SH_INITCOMMONCONTROLSEX, ownerRect As SH_RECT, calendarRect As SH_RECT
    Dim st As SH_SYSTEMTIME, ownerHwnd As LongPtr, instanceHwnd As LongPtr
    Dim parentClass As String, calendarClass As String, titleText As String
    Dim width As Long, height As Long, x As Long, y As Long

    controls.dwSize = LenB(controls)
    controls.dwICC = SH_ICC_DATE_CLASSES
    If InitCommonControlsEx(controls) = 0 Then Err.Raise vbObjectError + 550, , "Windows calendar control is unavailable."

    ownerHwnd = CLngPtr(Application.hwnd)
    instanceHwnd = GetModuleHandleW(0)
    parentClass = "STATIC"
    calendarClass = "SysMonthCal32"
    titleText = SH_U("0414043004420430002004400430043F043E044004420430")

    If GetWindowRect(ownerHwnd, ownerRect) = 0 Then
        ownerRect.Left = 100
        ownerRect.Top = 100
        ownerRect.Right = 900
        ownerRect.Bottom = 700
    End If
    width = 282
    height = 238
    x = ownerRect.Left + ((ownerRect.Right - ownerRect.Left) - width) \ 2
    y = ownerRect.Top + ((ownerRect.Bottom - ownerRect.Top) - height) \ 2

    mCalendarWindow = CreateWindowExW( _
        SH_WS_EX_TOOLWINDOW Or SH_WS_EX_DLGMODALFRAME, StrPtr(parentClass), StrPtr(titleText), _
        SH_WS_POPUP Or SH_WS_CAPTION Or SH_WS_SYSMENU Or SH_WS_VISIBLE, _
        x, y, width, height, ownerHwnd, 0, instanceHwnd, 0)
    If mCalendarWindow = 0 Then Err.Raise vbObjectError + 551, , "Cannot create calendar window."

    mCalendarOldProc = SetWindowLongPtrW(mCalendarWindow, SH_GWL_WNDPROC, AddressOf SH_CalendarWndProc)
    If mCalendarOldProc = 0 Then
        DestroyWindow mCalendarWindow
        mCalendarWindow = 0
        Err.Raise vbObjectError + 552, , "Cannot attach calendar window procedure."
    End If

    mCalendarControl = CreateWindowExW( _
        0, StrPtr(calendarClass), 0, SH_WS_CHILD Or SH_WS_VISIBLE, _
        10, 10, 250, 180, mCalendarWindow, 1001, instanceHwnd, 0)
    If mCalendarControl = 0 Then
        DestroyWindow mCalendarWindow
        mCalendarWindow = 0
        Err.Raise vbObjectError + 553, , "Cannot create Windows month calendar."
    End If

    SH_DateToSystemTime initialDate, st
    SendMessageW mCalendarControl, SH_MCM_SETCURSEL, 0, st
    If SendMessageW(mCalendarControl, SH_MCM_GETMINREQRECT, 0, calendarRect) <> 0 Then
        width = calendarRect.Right + 28
        height = calendarRect.Bottom + 54
        MoveWindow mCalendarControl, 10, 10, calendarRect.Right + 6, calendarRect.Bottom + 6, 1
        MoveWindow mCalendarWindow, x, y, width, height, 1
    End If
    SetForegroundWindow mCalendarWindow
End Sub

Public Function SH_CalendarWndProc(ByVal hwnd As LongPtr, ByVal Msg As Long, ByVal wParam As LongPtr, ByVal lParam As LongPtr) As LongPtr
    On Error Resume Next
    Dim header As SH_NMHDR, st As SH_SYSTEMTIME
    If Msg = SH_WM_NOTIFY And lParam <> 0 Then
        SH_CopyMemory header, lParam, LenB(header)
        If header.hwndFrom = mCalendarControl And header.code = SH_MCN_SELECT Then
            If SendMessageW(mCalendarControl, SH_MCM_GETCURSEL, 0, st) <> 0 Then
                mCalendarSelected = DateSerial(CLng(st.wYear), CLng(st.wMonth), CLng(st.wDay))
                mCalendarPicked = True
            End If
            mCalendarDone = True
            DestroyWindow hwnd
            SH_CalendarWndProc = 0
            Exit Function
        End If
    ElseIf Msg = SH_WM_CLOSE Then
        mCalendarDone = True
        DestroyWindow hwnd
        SH_CalendarWndProc = 0
        Exit Function
    ElseIf Msg = SH_WM_DESTROY Then
        mCalendarDone = True
    End If
    If mCalendarOldProc <> 0 Then SH_CalendarWndProc = CallWindowProcW(mCalendarOldProc, hwnd, Msg, wParam, lParam)
End Function

Private Sub SH_ApplyCalendarDate(ByVal wb As Workbook, ByVal selectedDate As Date)
    Dim prep As Worksheet
    SH_EnsureReportContour wb
    Set prep = SH_RequireSheet(wb, SH_PrepSheetName())
    prep.Range(SH_ReportDateCell()).Value = selectedDate
    prep.Range(SH_ReportDateCell()).NumberFormat = "dd.mm.yyyy"
    prep.Range("B4").Value = selectedDate - 1 + TimeSerial(7, 0, 0)
    prep.Range("B4").NumberFormat = "dd.mm.yyyy hh:mm"
    prep.Range("B5").Value = selectedDate + TimeSerial(7, 0, 0)
    prep.Range("B5").NumberFormat = "dd.mm.yyyy hh:mm"
    SH_ApplyCriticalFormulas wb
    SH_RefreshEmergencyOutages wb
    wb.Calculate
End Sub

Private Sub SH_DateToSystemTime(ByVal value As Date, ByRef st As SH_SYSTEMTIME)
    st.wYear = CInt(Year(value))
    st.wMonth = CInt(Month(value))
    st.wDay = CInt(Day(value))
End Sub

Private Sub SH_ResetCalendarState()
    mCalendarWindow = 0
    mCalendarControl = 0
    mCalendarOldProc = 0
    mCalendarDone = False
    mCalendarPicked = False
    mCalendarSelected = 0
    Set mCalendarJournal = Nothing
End Sub
