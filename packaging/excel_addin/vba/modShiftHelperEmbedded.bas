Attribute VB_Name = "modShiftHelperEmbedded"
Option Explicit

Public Function SH_ExtractEmbeddedReportTemplate() As String
    On Error GoTo Failed
    Dim tempRoot As String, targetPath As String, payload As String
    Dim xml As Object, node As Object, stream As Object, bytes As Variant
    Dim errNumber As Long, errDescription As String

    tempRoot = Environ$("TEMP") & Application.PathSeparator & "ShiftHelper"
    If Dir$(tempRoot, vbDirectory) = vbNullString Then MkDir tempRoot
    targetPath = tempRoot & Application.PathSeparator & "shift_helper_report_template.xlsx"
    payload = SH_EmbeddedTemplateBase64()
    If Len(payload) = 0 Then Err.Raise vbObjectError + 570, , "Embedded report template payload is empty."

    Set xml = CreateObject("MSXML2.DOMDocument.6.0")
    Set node = xml.createElement("base64")
    node.DataType = "bin.base64"
    node.Text = payload
    bytes = node.nodeTypedValue

    Set stream = CreateObject("ADODB.Stream")
    stream.Type = 1
    stream.Open
    stream.Write bytes
    stream.SaveToFile targetPath, 2
    stream.Close
    Set stream = Nothing

    If Dir$(targetPath) = vbNullString Then Err.Raise vbObjectError + 571, , "Embedded report template could not be written."
    If FileLen(targetPath) < 1000 Then Err.Raise vbObjectError + 572, , "Embedded report template is incomplete."
    SH_ExtractEmbeddedReportTemplate = targetPath
    Exit Function
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    On Error Resume Next
    If Not stream Is Nothing Then stream.Close
    On Error GoTo 0
    If Len(errDescription) = 0 Then errDescription = "Embedded report template extraction failed."
    Err.Raise errNumber, , errDescription
End Function
