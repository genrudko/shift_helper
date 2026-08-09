Attribute VB_Name = "modShiftHelperReportWindow"
Option Explicit

Public Sub SH_SyncReportWindow(ByVal wb As Workbook)
    Dim prep As Worksheet, raw As Variant, reportDate As Date
    Set prep = SH_EnsurePrepSheet(wb)
    raw = prep.Range("B3").Value2

    If IsError(raw) Or IsNull(raw) Or IsEmpty(raw) Then
        Err.Raise vbObjectError + 730, , "Report date is empty or invalid."
    End If
    If Not IsDate(raw) And Not IsNumeric(raw) Then
        Err.Raise vbObjectError + 731, , "Report date is invalid."
    End If

    On Error GoTo InvalidDate
    reportDate = DateValue(CDate(raw))
    On Error GoTo 0

    prep.Range("B3").Value = reportDate
    prep.Range("B3").NumberFormat = "dd.mm.yyyy"
    prep.Range("B4").Value = reportDate - 1 + TimeSerial(7, 0, 0)
    prep.Range("B4").NumberFormat = "dd.mm.yyyy hh:mm"
    prep.Range("B5").Value = reportDate + TimeSerial(7, 0, 0)
    prep.Range("B5").NumberFormat = "dd.mm.yyyy hh:mm"
    Exit Sub

InvalidDate:
    Err.Raise vbObjectError + 732, , "Report date is invalid."
End Sub

Public Sub SH_HandlePrepReportDateChange(ByVal Sh As Object, ByVal Target As Range)
    On Error GoTo Failed
    Dim wb As Workbook, hit As Range, oldEvents As Boolean, eventsCaptured As Boolean

    If TypeName(Sh) <> "Worksheet" Then Exit Sub
    If Target Is Nothing Then Exit Sub
    If Sh.Name <> SH_PrepSheetName() Then Exit Sub
    Set wb = Sh.Parent
    If wb Is ThisWorkbook Then Exit Sub
    If Not SH_HasSheet(wb, SH_JournalSheetName()) Then Exit Sub

    Set hit = Intersect(Target, Sh.Range("B3"))
    If hit Is Nothing Then Exit Sub

    oldEvents = Application.EnableEvents
    eventsCaptured = True
    Application.EnableEvents = False
    SH_SyncReportWindow wb
    Application.EnableEvents = oldEvents
    Exit Sub

Failed:
    On Error Resume Next
    If eventsCaptured Then Application.EnableEvents = oldEvents
    On Error GoTo 0
    MsgBox "Could not update report window [#" & CStr(Err.Number) & "]: " & Err.Description, _
        vbExclamation, "Shift-Helper"
End Sub
