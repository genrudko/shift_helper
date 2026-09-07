Attribute VB_Name = "modShiftHelperStationFacts"
Option Explicit

Private Const SH_MONTH_FACT_PREFIX As String = "report.generation.month_fact."

Public Sub SH_ApplyStationHistoricalFacts(ByVal wb As Workbook)
    On Error GoTo Failed
    Dim stationId As Long, reportDate As Date, main As Worksheet
    Dim monthIndex As Long, lastKnownMonth As Long, value As Double
    Dim raw As Variant, found As Boolean

    stationId = SH_ReportStationId(wb, False)
    If stationId = 0 Then Exit Sub
    reportDate = SH_ReportDate(wb)

    Set main = SH_RequireSheet(wb, SH_InputSheetName(1))
    lastKnownMonth = Month(reportDate) - 1
    If lastKnownMonth < 1 Then Exit Sub

    For monthIndex = 1 To lastKnownMonth
        value = -1#
        found = SH_TryStoredStationMonthFact( _
            wb, stationId, Year(reportDate), monthIndex, value)

        If Not found Then
            raw = main.Cells(monthIndex + 4, 10).Value2
            If SH_StationFactsTryDouble(raw, value) Then
                found = True
                SH_SetMetaValue wb, _
                    SH_StationMonthFactKey(stationId, Year(reportDate), monthIndex), value
            ElseIf Year(reportDate) = 2026 Then
                value = SH_StationHistoricalFact2026(stationId, monthIndex)
                found = (value >= 0#)
            End If
        End If

        If found Then main.Cells(monthIndex + 4, 10).Value2 = value
    Next monthIndex
    Exit Sub
Failed:
    Err.Raise Err.Number, , "Could not apply station historical facts: " & Err.Description
End Sub

Public Sub SH_StoreStationMonthFact(ByVal wb As Workbook, ByVal stationId As Long, _
    ByVal factDate As Date, ByVal value As Double)
    If stationId <> SH_STATION_KOCH And stationId <> SH_STATION_KUZ Then Exit Sub
    SH_SetMetaValue wb, _
        SH_StationMonthFactKey(stationId, Year(factDate), Month(factDate)), value
End Sub

Private Function SH_TryStoredStationMonthFact(ByVal wb As Workbook, ByVal stationId As Long, _
    ByVal factYear As Long, ByVal factMonth As Long, ByRef value As Double) As Boolean
    Dim raw As Variant
    raw = SH_MetaValue(wb, SH_StationMonthFactKey(stationId, factYear, factMonth), Empty)
    If SH_StationFactsTryDouble(raw, value) Then
        SH_TryStoredStationMonthFact = True
    End If
End Function

Private Function SH_StationMonthFactKey(ByVal stationId As Long, ByVal factYear As Long, _
    ByVal factMonth As Long) As String
    SH_StationMonthFactKey = SH_MONTH_FACT_PREFIX & CStr(stationId) & "." & _
        Format$(factYear, "0000") & "." & Format$(factMonth, "00")
End Function

Private Function SH_StationFactsTryDouble(ByVal raw As Variant, ByRef value As Double) As Boolean
    On Error GoTo Failed
    If IsError(raw) Or IsNull(raw) Or IsEmpty(raw) Then Exit Function
    If VarType(raw) = vbString Then
        If Len(Trim$(CStr(raw))) = 0 Then Exit Function
    End If
    If Not IsNumeric(raw) Then Exit Function
    value = CDbl(raw)
    SH_StationFactsTryDouble = True
    Exit Function
Failed:
    SH_StationFactsTryDouble = False
End Function

Public Sub SH_PrepareStationReportForRibbon()
    On Error GoTo Failed
    Dim wb As Workbook
    Set wb = SH_JournalBook()
    SH_ApplyNssForCurrentStation wb
    SH_SyncReportWindow wb
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
    SH_ApplyNssForStation wb, stationId
    SH_SyncReportWindow wb
    SH_ApplyStationHistoricalFacts wb
    SH_CalculateReportInputs wb
End Sub

Public Sub SH_ShowStationCalendarForRibbon()
    Dim wb As Workbook
    SH_ShowStationCalendar
    Set wb = SH_JournalBook()
    SH_ApplyNssForCurrentStation wb
    SH_SyncReportWindow wb
    SH_ApplyStationHistoricalFacts wb
    SH_CalculateReportInputs wb
End Sub

Public Sub SH_GenerateStationReportForRibbon()
    Dim wb As Workbook
    Set wb = SH_JournalBook()
    SH_ApplyNssForCurrentStation wb
    SH_SyncReportWindow wb
    SH_EnsureStationReportContour wb
    SH_ApplyStationHistoricalFacts wb
    SH_CalculateReportInputs wb
    SH_GeneratePreparedReport
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
