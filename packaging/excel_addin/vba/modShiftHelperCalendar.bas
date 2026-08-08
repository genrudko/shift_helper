Attribute VB_Name = "modShiftHelperCalendar"
Option Explicit

Private Const SH_MENU_NS As String = "http://schemas.microsoft.com/office/2009/07/customui"

Public Function SH_CalendarMenuXml() As String
    On Error GoTo Failed
    Dim wb As Workbook, prep As Worksheet, currentValue As Variant, selectedDate As Date
    Dim xml As String, offset As Long, monthStart As Date, monthEnd As Date
    Dim weekStart As Date, weekEnd As Date, daySerial As Long, d As Date, token As String
    Set wb = SH_JournalBook()
    If SH_HasSheet(wb, SH_PrepSheetName()) Then
        Set prep = wb.Worksheets(SH_PrepSheetName())
        currentValue = prep.Range(SH_ReportDateCell()).Value
        If IsDate(currentValue) Or IsNumeric(currentValue) Then selectedDate = CDate(currentValue)
    End If
    If selectedDate = 0 Then selectedDate = Date

    xml = "<menu xmlns=""" & SH_MENU_NS & """>"
    xml = xml & "<button id=""calToday"" label=""" & SH_XmlEscape(SH_T("CAL_TODAY")) & _
        """ tag=""" & Format$(Date, "yyyymmdd") & """ onAction=""SH_RibbonCalendarPick""/>"
    xml = xml & "<menuSeparator id=""calSep""/>"

    For offset = -1 To 1
        monthStart = DateSerial(Year(selectedDate), Month(selectedDate) + offset, 1)
        monthEnd = DateSerial(Year(monthStart), Month(monthStart) + 1, 0)
        token = SH_CalendarMonthToken(offset)
        xml = xml & "<menu id=""calMonth" & token & """ label=""" & _
            SH_XmlEscape(Format$(monthStart, "mmmm yyyy")) & """>"
        weekStart = monthStart
        Do While weekStart <= monthEnd
            weekEnd = DateAdd("d", 6, weekStart)
            If weekEnd > monthEnd Then weekEnd = monthEnd
            xml = xml & "<menu id=""calWeek" & token & Format$(weekStart, "dd") & _
                """ label=""" & SH_XmlEscape(SH_T("CAL_WEEK") & Format$(weekStart, "d") & _
                "-" & Format$(weekEnd, "d")) & """>"
            For daySerial = CLng(weekStart) To CLng(weekEnd)
                d = CDate(daySerial)
                xml = xml & SH_CalendarDayXml(d, selectedDate)
            Next daySerial
            xml = xml & "</menu>"
            weekStart = DateAdd("d", 7, weekStart)
        Loop
        xml = xml & "</menu>"
    Next offset
    SH_CalendarMenuXml = xml & "</menu>"
    Exit Function
Failed:
    SH_CalendarMenuXml = "<menu xmlns=""" & SH_MENU_NS & """><button id=""calUnavailable"" label=""" & _
        SH_XmlEscape(SH_T("ERR_JOURNAL")) & """ enabled=""false""/></menu>"
End Function

Private Function SH_CalendarDayXml(ByVal value As Date, ByVal selectedDate As Date) As String
    Dim labelText As String
    labelText = Format$(value, "d") & " " & Format$(value, "ddd")
    If DateValue(value) = DateValue(selectedDate) Then labelText = "* " & labelText
    SH_CalendarDayXml = "<button id=""calD" & Format$(value, "yyyymmdd") & """ label=""" & _
        SH_XmlEscape(labelText) & """ tag=""" & Format$(value, "yyyymmdd") & _
        """ onAction=""SH_RibbonCalendarPick""/>"
End Function

Private Function SH_CalendarMonthToken(ByVal offset As Long) As String
    Select Case offset
        Case -1: SH_CalendarMonthToken = "Prev"
        Case 0: SH_CalendarMonthToken = "Current"
        Case Else: SH_CalendarMonthToken = "Next"
    End Select
End Function

Public Sub SH_CalendarPickTag(ByVal tagValue As String)
    On Error GoTo Failed
    Dim wb As Workbook, prep As Worksheet, selectedDate As Date
    If Len(tagValue) <> 8 Or Not IsNumeric(tagValue) Then Err.Raise vbObjectError + 550, , "Invalid calendar date."
    selectedDate = DateSerial(CInt(Left$(tagValue, 4)), CInt(Mid$(tagValue, 5, 2)), CInt(Right$(tagValue, 2)))
    Set wb = SH_JournalBook()
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
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub
