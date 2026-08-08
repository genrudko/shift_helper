Attribute VB_Name = "modShiftHelperStationImport"
Option Explicit

Public Sub SH_ImportStationGenerationSelected()
    On Error GoTo Failed
    Dim wb As Workbook, stationId As Long
    Dim oldPattern As Variant, changed As Boolean
    Dim errNumber As Long, errDescription As String

    Set wb = SH_JournalBook()
    stationId = SH_ReportStationId(wb, True)
    SH_EnsureStationReportContour wb

    If stationId = SH_STATION_KUZ Then
        oldPattern = SH_MetaValue(wb, SH_Label(3), SH_DefaultSetting(3))
        SH_SetMetaValue wb, SH_Label(3), "*" & SH_U("041A04430437") & "*{date}*.xlsx"
        changed = True
    End If

    SH_ImportGenerationUniversal

    If changed Then SH_SetMetaValue wb, SH_Label(3), oldPattern
    SH_EnsureStationReportContour wb
    SH_ApplyStationHistoricalFacts wb
    SH_CalculateReportInputs wb
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
