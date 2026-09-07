Attribute VB_Name = "modShiftHelperStationImport"
Option Explicit

Public Sub SH_ImportStationGenerationSelected()
    On Error GoTo Failed
    Dim wb As Workbook, main As Worksheet, stationId As Long
    Dim reportDate As Date, factDate As Date, oldReportDate As Date, oldFactDate As Date
    Dim oldDateValue As Variant, hasOldDate As Boolean
    Dim priorMonthGeneration As Double, priorMonthOwn As Double
    Dim priorDaily As Double, priorOwn As Double, daily As Double, own As Double
    Dim monthGeneration As Double, monthOwn As Double
    Dim correctRow As Long, wrongRow As Long, wrongRowWasEmpty As Boolean
    Dim wrongRowFormula As Variant
    Dim oldPattern As Variant, changed As Boolean
    Dim errNumber As Long, errDescription As String

    Set wb = SH_JournalBook()
    stationId = SH_ReportStationId(wb, True)
    SH_EnsureStationReportContour wb
    Set main = SH_RequireSheet(wb, SH_InputSheetName(1))

    reportDate = SH_ReportDate(wb)
    factDate = DateAdd("d", -1, DateValue(reportDate))
    priorMonthGeneration = SH_StationImportSafeDouble(main.Range("C11").Value2)
    priorMonthOwn = SH_StationImportSafeDouble(main.Range("C17").Value2)
    priorDaily = SH_StationImportSafeDouble(SH_MetaValue(wb, SH_Label(10), 0))
    priorOwn = SH_StationImportSafeDouble(SH_MetaValue(wb, SH_Label(11), 0))
    oldDateValue = SH_MetaValue(wb, SH_Label(9), Empty)
    hasOldDate = SH_StationImportTryDate(oldDateValue, oldReportDate)
    If hasOldDate Then oldFactDate = DateAdd("d", -1, DateValue(oldReportDate))

    correctRow = Month(factDate) + 4
    wrongRow = Month(reportDate) + 4
    wrongRowWasEmpty = IsEmpty(main.Cells(wrongRow, 10).Value2) And _
        Not main.Cells(wrongRow, 10).HasFormula
    wrongRowFormula = main.Cells(wrongRow, 10).Formula

    If stationId = SH_STATION_KUZ Then
        oldPattern = SH_MetaValue(wb, SH_Label(3), SH_DefaultSetting(3))
        SH_SetMetaValue wb, SH_Label(3), "*" & SH_U("041A04430437") & "*{date}*.xlsx"
        changed = True
    End If

    SH_ImportGenerationUniversal

    If changed Then SH_SetMetaValue wb, SH_Label(3), oldPattern
    SH_EnsureStationReportContour wb
    Set main = SH_RequireSheet(wb, SH_InputSheetName(1))

    daily = SH_StationImportSafeDouble(main.Range("C10").Value2)
    own = SH_StationImportSafeDouble(main.Range("C16").Value2)

    If hasOldDate And DateValue(oldReportDate) = DateValue(reportDate) Then
        monthGeneration = priorMonthGeneration + daily - priorDaily
        monthOwn = priorMonthOwn + own - priorOwn
    ElseIf hasOldDate And Year(oldFactDate) = Year(factDate) And _
        Month(oldFactDate) = Month(factDate) Then
        monthGeneration = priorMonthGeneration + daily
        monthOwn = priorMonthOwn + own
    Else
        monthGeneration = daily
        monthOwn = own
    End If

    main.Range("C11").Value2 = monthGeneration
    main.Range("C17").Value2 = monthOwn

    If wrongRow <> correctRow Then
        If wrongRowWasEmpty Then
            main.Cells(wrongRow, 10).ClearContents
        Else
            main.Cells(wrongRow, 10).Formula = wrongRowFormula
        End If
    End If
    main.Cells(correctRow, 10).Value2 = monthGeneration

    SH_StoreStationMonthFact wb, stationId, factDate, monthGeneration
    SH_ApplyStationHistoricalFacts wb
    SH_ApplyCriticalFormulas wb
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

Private Function SH_StationImportSafeDouble(ByVal value As Variant) As Double
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If IsNumeric(value) Then SH_StationImportSafeDouble = CDbl(value)
    Exit Function
Failed:
    SH_StationImportSafeDouble = 0#
End Function

Private Function SH_StationImportTryDate(ByVal value As Variant, ByRef result As Date) As Boolean
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If IsDate(value) Or IsNumeric(value) Then
        result = CDate(value)
        SH_StationImportTryDate = True
    End If
    Exit Function
Failed:
    SH_StationImportTryDate = False
End Function
