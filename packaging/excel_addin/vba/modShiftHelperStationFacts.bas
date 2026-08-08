Attribute VB_Name = "modShiftHelperStationFacts"
Option Explicit

Public Sub SH_ApplyStationHistoricalFacts(ByVal wb As Workbook)
    On Error GoTo Failed
    Dim stationId As Long, reportDate As Date, main As Worksheet
    Dim monthIndex As Long, lastKnownMonth As Long, value As Double

    stationId = SH_ReportStationId(wb, False)
    If stationId = 0 Then Exit Sub
    reportDate = SH_ReportDate(wb)
    If Year(reportDate) <> 2026 Then Exit Sub

    Set main = SH_RequireSheet(wb, SH_InputSheetName(1))
    lastKnownMonth = Application.Min(7, Month(reportDate) - 1)
    If lastKnownMonth < 1 Then Exit Sub

    For monthIndex = 1 To lastKnownMonth
        value = SH_StationHistoricalFact2026(stationId, monthIndex)
        If value >= 0 Then main.Cells(monthIndex + 4, 10).Value2 = value
    Next monthIndex
    Exit Sub
Failed:
    Err.Raise Err.Number, , "Could not apply station historical facts: " & Err.Description
End Sub

Public Sub SH_PrepareStationReportForRibbon()
    On Error GoTo Failed
    Dim wb As Workbook
    Set wb = SH_JournalBook()
    SH_EnsureStationReportContour wb
    SH_ApplyStationHistoricalFacts wb
    SH_CalculateReportInputs wb
    MsgBox SH_T("OK_PREP") & vbCrLf & SH_T("NO_TEMPLATE_PICK"), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    MsgBox SH_T("ERR_PREP") & "[#" & CStr(Err.Number) & "] " & Err.Description, _
        vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_SelectStationForRibbon(ByVal stationId As Long)
    SH_SetReportStation stationId
    Dim wb As Workbook
    Set wb = SH_JournalBook()
    SH_ApplyStationHistoricalFacts wb
    SH_CalculateReportInputs wb
End Sub

Public Sub SH_ShowStationCalendarForRibbon()
    Dim wb As Workbook
    SH_ShowStationCalendar
    Set wb = SH_JournalBook()
    SH_ApplyStationHistoricalFacts wb
    SH_CalculateReportInputs wb
End Sub

Private Function SH_StationHistoricalFact2026(ByVal stationId As Long, _
    ByVal monthIndex As Long) As Double
    SH_StationHistoricalFact2026 = -1#
    If stationId = SH_STATION_KUZ Then
        Select Case monthIndex
            Case 1: SH_StationHistoricalFact2026 = 30154342#
            Case 2: SH_StationHistoricalFact2026 = 33176283#
            Case 3: SH_StationHistoricalFact2026 = 33173000#
            Case 4: SH_StationHistoricalFact2026 = 21151677#
            Case 5: SH_StationHistoricalFact2026 = 29470109#
            Case 6: SH_StationHistoricalFact2026 = 11951418#
            Case 7: SH_StationHistoricalFact2026 = 13003670#
        End Select
    ElseIf stationId = SH_STATION_KOCH Then
        Select Case monthIndex
            Case 1: SH_StationHistoricalFact2026 = 49433027#
            Case 2: SH_StationHistoricalFact2026 = 60472425#
            Case 3: SH_StationHistoricalFact2026 = 47415807#
            Case 4: SH_StationHistoricalFact2026 = 30086974#
            Case 5: SH_StationHistoricalFact2026 = 33242664#
            Case 6: SH_StationHistoricalFact2026 = 12914362#
            Case 7: SH_StationHistoricalFact2026 = 14234957#
        End Select
    End If
End Function
