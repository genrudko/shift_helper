Attribute VB_Name = "modShiftHelperEmbedded"
Option Explicit

Public Function SH_ExtractEmbeddedReportTemplate() As String
    On Error GoTo Failed
    Dim tempRoot As String, zipCopy As String, targetPath As String
    Dim shellApp As Object, zipFolder As Object, outFolder As Object, item As Object
    Dim startedAt As Date, errNumber As Long, errDescription As String
    tempRoot = Environ$("TEMP") & Application.PathSeparator & "ShiftHelper"
    If Dir$(tempRoot, vbDirectory) = vbNullString Then MkDir tempRoot
    zipCopy = tempRoot & Application.PathSeparator & "Shift-Helper-Excel-runtime.zip"
    targetPath = tempRoot & Application.PathSeparator & "shift_helper_report_template.xlsx"
    On Error Resume Next
    Kill zipCopy
    Kill targetPath
    On Error GoTo Failed
    FileCopy ThisWorkbook.FullName, zipCopy
    Set shellApp = CreateObject("Shell.Application")
    Set zipFolder = shellApp.NameSpace(zipCopy)
    Set outFolder = shellApp.NameSpace(tempRoot)
    If zipFolder Is Nothing Or outFolder Is Nothing Then Err.Raise vbObjectError + 570, , "Embedded package is unavailable."
    Set item = zipFolder.ParseName("shift_helper_report_template.xlsx")
    If item Is Nothing Then Err.Raise vbObjectError + 571, , "Embedded report template is missing."
    outFolder.CopyHere item, 20
    startedAt = Now
    Do While Dir$(targetPath) = vbNullString
        DoEvents
        If DateDiff("s", startedAt, Now) > 20 Then Err.Raise vbObjectError + 572, , "Embedded report template extraction timed out."
    Loop
    On Error Resume Next
    Kill zipCopy
    On Error GoTo 0
    SH_ExtractEmbeddedReportTemplate = targetPath
    Exit Function
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    On Error Resume Next
    Kill zipCopy
    On Error GoTo 0
    Err.Raise errNumber, , errDescription
End Function
