Attribute VB_Name = "modShiftHelperCalendar"
Option Explicit

Private mCalendarBook As Workbook
Private mCalendarTarget As Range
Private mCalendarMonth As Date

Public Sub SH_ShowCalendar()
    On Error GoTo Failed
    Dim wb As Workbook, currentValue As Variant
    Set wb = SH_JournalBook()
    Set mCalendarTarget = wb.Worksheets(SH_PrepSheetName()).Range(SH_ReportDateCell())
    currentValue = mCalendarTarget.Value
    If IsDate(currentValue) Then
        mCalendarMonth = DateSerial(Year(CDate(currentValue)), Month(CDate(currentValue)), 1)
    Else
        mCalendarMonth = DateSerial(Year(Date), Month(Date), 1)
    End If
    SH_BuildCalendar
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Private Sub SH_BuildCalendar()
    Dim ws As Worksheet, d As Date, firstOffset As Long, dayNumber As Long
    Dim rowNumber As Long, colNumber As Long, shape As Shape, i As Long, names As Variant
    If Not mCalendarBook Is Nothing Then
        Application.DisplayAlerts = False
        mCalendarBook.Close SaveChanges:=False
        Application.DisplayAlerts = True
    End If
    Set mCalendarBook = Workbooks.Add(xlWBATWorksheet)
    Set ws = mCalendarBook.Worksheets(1)
    ws.Name = "Calendar"
    ActiveWindow.DisplayGridlines = False
    ActiveWindow.Zoom = 110
    ws.Columns("A:G").ColumnWidth = 5.2
    ws.Rows("1:10").RowHeight = 24
    ws.Range("A1:G1").Merge
    ws.Range("A1").Value = Format$(mCalendarMonth, "mmmm yyyy")
    ws.Range("A1").HorizontalAlignment = xlCenter
    ws.Range("A1").Font.Bold = True
    names = Array(SH_U("041F043D"), SH_U("04120442"), SH_U("04210440"), SH_U("04270442"), SH_U("041F0442"), SH_U("04210431"), SH_U("04120441"))
    For i = 0 To 6
        ws.Cells(2, i + 1).Value = names(i)
        ws.Cells(2, i + 1).HorizontalAlignment = xlCenter
    Next i

    firstOffset = Weekday(mCalendarMonth, vbMonday) - 1
    dayNumber = 1
    For rowNumber = 3 To 8
        For colNumber = 1 To 7
            If (rowNumber - 3) * 7 + colNumber - 1 >= firstOffset Then
                d = DateSerial(Year(mCalendarMonth), Month(mCalendarMonth), dayNumber)
                If Month(d) <> Month(mCalendarMonth) Then Exit For
                Set shape = ws.Shapes.AddShape(msoShapeRoundedRectangle, ws.Cells(rowNumber, colNumber).Left + 1, ws.Cells(rowNumber, colNumber).Top + 1, ws.Cells(rowNumber, colNumber).Width - 2, ws.Cells(rowNumber, colNumber).Height - 2)
                shape.TextFrame2.TextRange.Text = CStr(dayNumber)
                shape.AlternativeText = CStr(CDbl(d))
                shape.OnAction = SH_QualifiedMacro("SH_CalendarPick")
                dayNumber = dayNumber + 1
            End If
        Next colNumber
    Next rowNumber
    SH_AddCalendarButton ws, "PrevMonth", "<", "A9:B9", "SH_CalendarPrevious"
    SH_AddCalendarButton ws, "Today", SH_U("042104350433043E0434043D044F"), "C9:E9", "SH_CalendarToday"
    SH_AddCalendarButton ws, "NextMonth", ">", "F9:G9", "SH_CalendarNext"
    SH_AddCalendarButton ws, "Cancel", SH_U("041E0442043C0435043D0430"), "C10:E10", "SH_CalendarCancel"
    mCalendarBook.Windows(1).Caption = "Shift-Helper - Calendar"
End Sub

Private Sub SH_AddCalendarButton(ByVal ws As Worksheet, ByVal shapeName As String, ByVal caption As String, ByVal address As String, ByVal macroName As String)
    Dim area As Range, shape As Shape
    Set area = ws.Range(address)
    Set shape = ws.Shapes.AddShape(msoShapeRoundedRectangle, area.Left + 1, area.Top + 1, area.Width - 2, area.Height - 2)
    shape.Name = shapeName
    shape.TextFrame2.TextRange.Text = caption
    shape.OnAction = SH_QualifiedMacro(macroName)
End Sub

Public Sub SH_CalendarPick()
    On Error GoTo Failed
    Dim shape As Shape, selectedDate As Double, wb As Workbook
    Set shape = ActiveSheet.Shapes(CStr(Application.Caller))
    selectedDate = CDbl(shape.AlternativeText)
    Set wb = mCalendarTarget.Worksheet.Parent
    mCalendarTarget.Value = selectedDate
    mCalendarTarget.NumberFormat = "dd.mm.yyyy"
    SH_ApplyCriticalFormulas wb
    SH_RefreshEmergencyOutages wb
    wb.Calculate
    SH_CloseCalendar
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_CalendarPrevious()
    mCalendarMonth = DateAdd("m", -1, mCalendarMonth)
    SH_BuildCalendar
End Sub

Public Sub SH_CalendarNext()
    mCalendarMonth = DateAdd("m", 1, mCalendarMonth)
    SH_BuildCalendar
End Sub

Public Sub SH_CalendarToday()
    Dim wb As Workbook
    Set wb = mCalendarTarget.Worksheet.Parent
    mCalendarTarget.Value = Date
    mCalendarTarget.NumberFormat = "dd.mm.yyyy"
    SH_ApplyCriticalFormulas wb
    SH_RefreshEmergencyOutages wb
    wb.Calculate
    SH_CloseCalendar
End Sub

Public Sub SH_CalendarCancel()
    SH_CloseCalendar
End Sub

Private Sub SH_CloseCalendar()
    If mCalendarBook Is Nothing Then Exit Sub
    Application.DisplayAlerts = False
    mCalendarBook.Close SaveChanges:=False
    Application.DisplayAlerts = True
    Set mCalendarBook = Nothing
    Set mCalendarTarget = Nothing
End Sub
