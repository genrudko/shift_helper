Attribute VB_Name = "modShiftHelperStationImport"
Option Explicit

Public Sub SH_ImportStationGenerationSelected()
    On Error GoTo Failed
    Dim wb As Workbook, main As Worksheet, stationId As Long, stationHint As String
    Dim factDate As Date
    Dim oldPattern As Variant, changed As Boolean
    Dim errNumber As Long, errDescription As String

    Set wb = SH_JournalBook()
    stationId = SH_ReportStationId(wb, True)
    If stationId = SH_STATION_KUZ Then
        stationHint = "kuz"
        oldPattern = SH_MetaValue(wb, SH_Label(3), SH_DefaultSetting(3))
        SH_SetMetaValue wb, SH_Label(3), "*" & SH_U("041A04430437") & "*{date}*.xlsx"
        changed = True
    Else
        stationHint = "kves"
    End If

    If Not SH_ImportGenerationUniversalCore(stationHint) Then GoTo CleanExit

    SH_EnsureStationReportContour wb
    Set main = SH_RequireSheet(wb, SH_InputSheetName(1))
    factDate = DateAdd("d", -1, DateValue(SH_ReportDate(wb)))
    SH_StoreStationMonthFact wb, stationId, factDate, CDbl(main.Range("C11").Value2)
    SH_ApplyStationHistoricalFacts wb
CleanExit:
    If changed Then
        SH_SetMetaValue wb, SH_Label(3), oldPattern
        changed = False
    End If
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    On Error Resume Next
    If changed Then SH_SetMetaValue wb, SH_Label(3), oldPattern
    On Error GoTo 0
    If Len(errDescription) = 0 Then errDescription = "Station generation import failed."
    MsgBox SH_T("GEN_BAD") & "[#" & CStr(errNumber) & "]: " & errDescription, vbExclamation, "Shift-Helper"
End Sub
