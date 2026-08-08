Attribute VB_Name = "modShiftHelperGeneration"
Option Explicit

Public Sub SH_ImportGenerationSafe()
    On Error GoTo Failed
    Dim wb As Workbook, main As Worksheet, reportDate As Date, sourcePath As String
    Dim daily As Double, own As Double, monthGeneration As Double, monthOwn As Double
    Dim oldDaily As Double, oldOwn As Double, oldDateValue As Variant, oldDate As Date
    Dim hasOldDate As Boolean, stage As String, errDescription As String, errNumber As Long
    Dim oldCalculation As XlCalculation, oldEvents As Boolean, oldScreenUpdating As Boolean
    Dim appStateCaptured As Boolean, manualFallback As Double

    stage = "capture Excel state"
    oldCalculation = Application.Calculation
    oldEvents = Application.EnableEvents
    oldScreenUpdating = Application.ScreenUpdating
    appStateCaptured = True
    Application.Calculation = xlCalculationManual
    Application.EnableEvents = False
    Application.ScreenUpdating = False

    stage = "prepare report contour"
    Set wb = SH_JournalBook()
    SH_EnsureReportContour wb

    stage = "read report settings"
    Set main = SH_RequireSheet(wb, SH_InputSheetName(1))
    reportDate = SH_ReportDate(wb)
    manualFallback = SH_GenSafeDouble(SH_MetaValue(wb, SH_Label(7), SH_DefaultSetting(7)))

    stage = "search Outlook"
    sourcePath = SH_GenFindOutlookFile(wb, reportDate)
    If Len(sourcePath) = 0 And manualFallback <> 0 Then
        stage = "choose generation workbook"
        sourcePath = SH_GenPickFile()
    End If
    If Len(sourcePath) = 0 Then
        Application.Calculation = oldCalculation
        Application.EnableEvents = oldEvents
        Application.ScreenUpdating = oldScreenUpdating
        MsgBox SH_T("OUTLOOK_NOT_FOUND"), vbInformation, "Shift-Helper"
        Exit Sub
    End If
    If LCase$(Right$(sourcePath, 5)) <> ".xlsx" Then
        Err.Raise vbObjectError + 584, , "Only .xlsx generation attachments are allowed."
    End If

    stage = "read generation workbook"
    SH_GenReadWorkbook sourcePath, daily, own

    stage = "update generation totals"
    monthGeneration = SH_GenSafeDouble(main.Range("C11").Value2)
    monthOwn = SH_GenSafeDouble(main.Range("C17").Value2)
    oldDaily = SH_GenSafeDouble(SH_MetaValue(wb, SH_Label(10), 0))
    oldOwn = SH_GenSafeDouble(SH_MetaValue(wb, SH_Label(11), 0))
    oldDateValue = SH_MetaValue(wb, SH_Label(9), Empty)
    hasOldDate = SH_GenTryDate(oldDateValue, oldDate)

    If hasOldDate And DateValue(oldDate) = DateValue(reportDate) Then
        monthGeneration = monthGeneration + daily - oldDaily
        monthOwn = monthOwn + own - oldOwn
    ElseIf hasOldDate And Year(oldDate) = Year(reportDate) And Month(oldDate) = Month(reportDate) Then
        monthGeneration = monthGeneration + daily
        monthOwn = monthOwn + own
    ElseIf Day(reportDate) <= 2 Then
        monthGeneration = daily
        monthOwn = own
    Else
        monthGeneration = monthGeneration + daily
        monthOwn = monthOwn + own
    End If

    main.Range("C10").Value2 = daily
    main.Range("C11").Value2 = monthGeneration
    main.Range("C16").Value2 = own
    main.Range("C17").Value2 = monthOwn
    main.Cells(Month(reportDate) + 4, 10).Value2 = monthGeneration
    SH_SetMetaValue wb, SH_Label(8), sourcePath
    SH_SetMetaValue wb, SH_Label(9), reportDate
    SH_SetMetaValue wb, SH_Label(10), daily
    SH_SetMetaValue wb, SH_Label(11), own

    stage = "recalculate report inputs"
    SH_ApplyCriticalFormulas wb
    SH_CalculateReportInputs wb

    Application.Calculation = oldCalculation
    Application.EnableEvents = oldEvents
    Application.ScreenUpdating = oldScreenUpdating
    MsgBox SH_T("GEN_OK") & vbCrLf & Format$(daily, "0") & " kWh" & vbCrLf & _
        Format$(daily / 24000#, "0.00") & " MW", vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    On Error Resume Next
    If appStateCaptured Then
        Application.Calculation = oldCalculation
        Application.EnableEvents = oldEvents
        Application.ScreenUpdating = oldScreenUpdating
    End If
    On Error GoTo 0
    If errNumber = 0 Then errNumber = vbObjectError + 587
    If Len(errDescription) = 0 Then errDescription = "Generation import failed."
    MsgBox SH_T("GEN_BAD") & "[#" & CStr(errNumber) & "] Stage [" & stage & "]: " & _
        errDescription, vbExclamation, "Shift-Helper"
End Sub

Private Function SH_GenPickFile() As String
    Dim selected As Variant
    selected = Application.GetOpenFilename( _
        "Excel Workbook (*.xlsx),*.xlsx", , SH_T("GEN_PICK") _
    )
    If VarType(selected) <> vbBoolean Then SH_GenPickFile = CStr(selected)
End Function

Private Function SH_GenSetting(ByVal wb As Workbook, ByVal index As Long) As String
    Dim fallback As String, value As Variant
    fallback = GetSetting("Shift-Helper", "Outlook", SH_Label(index), SH_DefaultSetting(index))
    value = SH_MetaValue(wb, SH_Label(index), fallback)
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then
        SH_GenSetting = fallback
    Else
        SH_GenSetting = CStr(value)
    End If
End Function

Private Function SH_GenFindOutlookFile(ByVal wb As Workbook, ByVal reportDate As Date) As String
    On Error GoTo Unavailable
    Dim outlook As Object, ns As Object, folder As Object, items As Object
    Dim item As Object, att As Object, received As Variant, receivedDate As Date
    Dim mailbox As String, folderPath As String, pattern As String
    Dim subjectFilter As String, senderFilter As String, senderText As String
    Dim depthDays As Long, cutoff As Date, tempRoot As String, target As String
    Dim fileName As String

    mailbox = SH_GenSetting(wb, 1)
    folderPath = SH_GenSetting(wb, 2)
    pattern = SH_GenSetting(wb, 3)
    pattern = Replace(pattern, "{date}", Format$(DateAdd("d", -1, reportDate), "dd_mm_yyyy"))
    subjectFilter = LCase$(SH_GenSetting(wb, 4))
    senderFilter = LCase$(SH_GenSetting(wb, 5))
    depthDays = CLng(SH_GenSafeDouble(SH_GenSetting(wb, 6)))
    If depthDays < 1 Then depthDays = 1
    If depthDays > 60 Then depthDays = 60
    cutoff = DateAdd("d", -depthDays, reportDate)

    On Error Resume Next
    Set outlook = GetObject(, "Outlook.Application")
    If outlook Is Nothing Then Set outlook = CreateObject("Outlook.Application")
    On Error GoTo Unavailable
    If outlook Is Nothing Then Exit Function

    Set ns = outlook.GetNamespace("MAPI")
    Set folder = SH_GenOutlookFolder(ns, mailbox, folderPath)
    If folder Is Nothing Then Exit Function
    Set items = folder.Items
    items.Sort "[ReceivedTime]", True

    tempRoot = Environ$("TEMP") & Application.PathSeparator & "ShiftHelper"
    If Dir$(tempRoot, vbDirectory) = vbNullString Then MkDir tempRoot

    For Each item In items
        received = Empty
        On Error Resume Next
        Err.Clear
        received = item.ReceivedTime
        If Err.Number <> 0 Then
            Err.Clear
            On Error GoTo Unavailable
            GoTo NextItem
        End If
        On Error GoTo Unavailable
        If SH_GenTryDate(received, receivedDate) Then
            If receivedDate < cutoff Then Exit For
        End If

        If Len(subjectFilter) > 0 Then
            If InStr(1, LCase$(SH_GenSafeText(item.Subject)), subjectFilter, vbTextCompare) = 0 Then _
                GoTo NextItem
        End If
        senderText = LCase$(SH_GenSafeText(item.SenderName) & " " & _
            SH_GenSafeText(item.SenderEmailAddress))
        If Len(senderFilter) > 0 Then
            If InStr(1, senderText, senderFilter, vbTextCompare) = 0 Then GoTo NextItem
        End If

        For Each att In item.Attachments
            fileName = SH_GenSafeText(att.FileName)
            If Len(fileName) > 0 Then
                If LCase$(fileName) Like LCase$(pattern) Then
                    If LCase$(Right$(fileName, 5)) = ".xlsx" Then
                        target = tempRoot & Application.PathSeparator & SH_GenSafeFileName(fileName)
                        On Error Resume Next
                        Err.Clear
                        If Len(Dir$(target)) > 0 Then Kill target
                        Err.Clear
                        att.SaveAsFile target
                        If Err.Number = 0 And Len(Dir$(target)) > 0 Then
                            SH_GenFindOutlookFile = target
                            On Error GoTo 0
                            Exit Function
                        End If
                        Err.Clear
                        On Error GoTo Unavailable
                    End If
                End If
            End If
        Next att
NextItem:
    Next item
    Exit Function
Unavailable:
    SH_GenFindOutlookFile = ""
End Function

Private Function SH_GenOutlookFolder(ByVal ns As Object, ByVal mailbox As String, _
    ByVal folderPath As String) As Object
    On Error Resume Next
    Dim folder As Object, recipient As Object, part As Variant, parts As Variant
    Set folder = ns.Folders.Item(mailbox)
    If folder Is Nothing Then
        Set recipient = ns.CreateRecipient(mailbox)
        recipient.Resolve
        Set folder = ns.GetSharedDefaultFolder(recipient, 6)
    End If
    If folder Is Nothing Then Exit Function
    parts = Split(Replace(folderPath, "/", "\"), "\")
    For Each part In parts
        If Len(Trim$(CStr(part))) > 0 Then
            If LCase$(Trim$(CStr(part))) <> LCase$(SH_DefaultSetting(2)) Or _
                folder.DefaultItemType <> 0 Then
                Set folder = folder.Folders.Item(Trim$(CStr(part)))
                If folder Is Nothing Then Exit Function
            End If
        End If
    Next part
    Set SH_GenOutlookFolder = folder
End Function

Private Sub SH_GenReadWorkbook(ByVal path As String, ByRef daily As Double, ByRef own As Double)
    On Error GoTo Failed
    Dim source As Workbook, ws As Worksheet, data As Variant, used As Range
    Dim rowsCount As Long, colsCount As Long, r As Long, c As Long, text As String
    Dim value As Variant, foundDaily As Boolean, foundOwn As Boolean
    Dim errNumber As Long, errDescription As String

    Set source = Workbooks.Open(Filename:=path, UpdateLinks:=0, ReadOnly:=True, AddToMru:=False)
    For Each ws In source.Worksheets
        Set used = ws.UsedRange
        rowsCount = Application.Min(used.Rows.Count, 250)
        colsCount = Application.Min(used.Columns.Count, 80)
        If rowsCount > 0 And colsCount > 0 Then
            data = used.Resize(rowsCount, colsCount).Value2
            If rowsCount = 1 And colsCount = 1 Then
                ReDim data(1 To 1, 1 To 1)
                data(1, 1) = used.Cells(1, 1).Value2
            End If
            For r = 1 To rowsCount
                For c = 1 To colsCount
                    text = LCase$(SH_GenSafeText(data(r, c)))
                    If Not foundDaily Then
                        If InStr(1, text, SH_U("0432044B044004300431043E0442043A0430"), vbTextCompare) > 0 And _
                            (InStr(1, text, SH_U("044104430442"), vbTextCompare) > 0 Or _
                            InStr(1, text, SH_U("04320447043504400430"), vbTextCompare) > 0) And _
                            InStr(1, text, SH_U("043C04350441044F0446"), vbTextCompare) = 0 Then
                            value = SH_GenNearNumeric(data, r, c, rowsCount, colsCount)
                            If Not IsEmpty(value) Then daily = CDbl(value): foundDaily = True
                        End If
                    End If
                    If Not foundOwn Then
                        If InStr(1, text, SH_U("0441043E04310441044204320435043D"), vbTextCompare) > 0 And _
                            InStr(1, text, SH_U("043D044304360434"), vbTextCompare) > 0 And _
                            (InStr(1, text, SH_U("044104430442"), vbTextCompare) > 0 Or _
                            InStr(1, text, SH_U("04320447043504400430"), vbTextCompare) > 0) And _
                            InStr(1, text, SH_U("043C04350441044F0446"), vbTextCompare) = 0 Then
                            value = SH_GenNearNumeric(data, r, c, rowsCount, colsCount)
                            If Not IsEmpty(value) Then own = CDbl(value): foundOwn = True
                        End If
                    End If
                    If foundDaily And foundOwn Then Exit For
                Next c
                If foundDaily And foundOwn Then Exit For
            Next r
        End If
        If foundDaily And foundOwn Then Exit For
    Next ws
    source.Close SaveChanges:=False
    Set source = Nothing
    If Not foundDaily Or Not foundOwn Then
        Err.Raise vbObjectError + 585, , "Expected generation fields were not found in the workbook."
    End If
    If daily < 0 Or own < 0 Then
        Err.Raise vbObjectError + 586, , "Generation values must be non-negative."
    End If
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    On Error Resume Next
    If Not source Is Nothing Then source.Close SaveChanges:=False
    On Error GoTo 0
    If errNumber = 0 Then errNumber = vbObjectError + 588
    If Len(errDescription) = 0 Then errDescription = "Could not read generation workbook."
    Err.Raise errNumber, , errDescription
End Sub

Private Function SH_GenNearNumeric(ByVal data As Variant, ByVal rowIndex As Long, _
    ByVal colIndex As Long, ByVal rowCount As Long, ByVal colCount As Long) As Variant
    Dim offset As Long, value As Variant
    For offset = 1 To 8
        If colIndex + offset <= colCount Then
            value = data(rowIndex, colIndex + offset)
            If SH_GenIsNumericValue(value) Then
                SH_GenNearNumeric = CDbl(value)
                Exit Function
            End If
        End If
    Next offset
    For offset = 1 To 4
        If rowIndex + offset <= rowCount Then
            value = data(rowIndex + offset, colIndex)
            If SH_GenIsNumericValue(value) Then
                SH_GenNearNumeric = CDbl(value)
                Exit Function
            End If
        End If
    Next offset
    SH_GenNearNumeric = Empty
End Function

Private Function SH_GenIsNumericValue(ByVal value As Variant) As Boolean
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If VarType(value) = vbString Then
        If Len(Trim$(CStr(value))) = 0 Then Exit Function
    End If
    SH_GenIsNumericValue = IsNumeric(value)
    Exit Function
Failed:
    SH_GenIsNumericValue = False
End Function

Private Function SH_GenSafeText(ByVal value As Variant) As String
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    SH_GenSafeText = CStr(value)
    Exit Function
Failed:
    SH_GenSafeText = ""
End Function

Private Function SH_GenSafeDouble(ByVal value As Variant) As Double
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If IsNumeric(value) Then SH_GenSafeDouble = CDbl(value)
    Exit Function
Failed:
    SH_GenSafeDouble = 0#
End Function

Private Function SH_GenTryDate(ByVal value As Variant, ByRef result As Date) As Boolean
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If IsDate(value) Or IsNumeric(value) Then
        result = CDate(value)
        SH_GenTryDate = True
    End If
    Exit Function
Failed:
    SH_GenTryDate = False
End Function

Private Function SH_GenSafeFileName(ByVal name As String) As String
    Dim bad As Variant
    SH_GenSafeFileName = name
    For Each bad In Array("<", ">", ":", Chr$(34), "/", "\", "|", "?", "*")
        SH_GenSafeFileName = Replace(SH_GenSafeFileName, CStr(bad), "_")
    Next bad
End Function
