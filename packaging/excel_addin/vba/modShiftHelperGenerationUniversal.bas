Attribute VB_Name = "modShiftHelperGenerationUniversal"
Option Explicit

Public Sub SH_ImportGenerationUniversal()
    On Error GoTo Failed
    Dim wb As Workbook, main As Worksheet, reportDate As Date, sourcePath As String
    Dim daily As Double, own As Double, monthGeneration As Double, monthOwn As Double
    Dim oldDaily As Double, oldOwn As Double, oldDateValue As Variant, oldDate As Date
    Dim hasOldDate As Boolean, stage As String, errDescription As String, errNumber As Long
    Dim oldCalculation As XlCalculation, oldEvents As Boolean, oldScreenUpdating As Boolean
    Dim appStateCaptured As Boolean, manualFallback As Double, searchDiagnostic As String
    Dim stationHint As String, profileName As String

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
    manualFallback = SH_G2SafeDouble(SH_MetaValue(wb, SH_Label(7), SH_DefaultSetting(7)))
    stationHint = SH_G2StationHint(wb)

    stage = "search Outlook"
    sourcePath = SH_G2FindOutlookFile(wb, reportDate, stationHint, searchDiagnostic)
    If Len(sourcePath) = 0 And manualFallback <> 0 Then
        stage = "choose generation workbook"
        sourcePath = SH_G2PickFile()
    End If
    If Len(sourcePath) = 0 Then
        Application.Calculation = oldCalculation
        Application.EnableEvents = oldEvents
        Application.ScreenUpdating = oldScreenUpdating
        MsgBox SH_T("OUTLOOK_NOT_FOUND") & vbCrLf & vbCrLf & searchDiagnostic, _
            vbInformation, "Shift-Helper"
        Exit Sub
    End If
    If LCase$(Right$(sourcePath, 5)) <> ".xlsx" Then
        Err.Raise vbObjectError + 684, , "Only .xlsx generation attachments are allowed."
    End If

    stage = "read generation workbook"
    SH_G2ReadWorkbook sourcePath, DateAdd("d", -1, reportDate), daily, own, profileName

    stage = "update generation totals"
    monthGeneration = SH_G2SafeDouble(main.Range("C11").Value2)
    monthOwn = SH_G2SafeDouble(main.Range("C17").Value2)
    oldDaily = SH_G2SafeDouble(SH_MetaValue(wb, SH_Label(10), 0))
    oldOwn = SH_G2SafeDouble(SH_MetaValue(wb, SH_Label(11), 0))
    oldDateValue = SH_MetaValue(wb, SH_Label(9), Empty)
    hasOldDate = SH_G2TryDate(oldDateValue, oldDate)

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
    MsgBox SH_T("GEN_OK") & vbCrLf & _
        SH_U("0424043E0440043C0430003A0020") & SH_G2ProfileCaption(profileName) & vbCrLf & _
        Format$(daily, "0") & " kWh" & vbCrLf & _
        SH_U("0421043E04310441044204320435043D043D044B04350020043D044304360434044B003A0020") & _
        Format$(own, "0") & " kWh" & vbCrLf & _
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
    If errNumber = 0 Then errNumber = vbObjectError + 687
    If Len(errDescription) = 0 Then errDescription = "Generation import failed."
    MsgBox SH_T("GEN_BAD") & "[#" & CStr(errNumber) & "] Stage [" & stage & "]: " & _
        errDescription, vbExclamation, "Shift-Helper"
End Sub

Private Function SH_G2PickFile() As String
    Dim selected As Variant
    selected = Application.GetOpenFilename( _
        "Excel Workbook (*.xlsx),*.xlsx", , SH_T("GEN_PICK") _
    )
    If VarType(selected) <> vbBoolean Then SH_G2PickFile = CStr(selected)
End Function

Private Function SH_G2Setting(ByVal wb As Workbook, ByVal index As Long) As String
    Dim fallback As String, value As Variant
    fallback = GetSetting("Shift-Helper", "Outlook", SH_Label(index), SH_DefaultSetting(index))
    value = SH_MetaValue(wb, SH_Label(index), fallback)
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then
        SH_G2Setting = fallback
    Else
        SH_G2Setting = CStr(value)
    End If
End Function

Private Function SH_G2StationHint(ByVal wb As Workbook) As String
    On Error Resume Next
    Dim text As String, main As Worksheet
    text = LCase$(wb.Name)
    If SH_HasSheet(wb, SH_InputSheetName(1)) Then
        Set main = wb.Worksheets(SH_InputSheetName(1))
        text = text & " " & LCase$(SH_G2SafeText(main.Range("B1").Value2))
    End If
    On Error GoTo 0
    SH_G2StationHint = SH_G2StationFromText(text)
End Function

Private Function SH_G2StationFromText(ByVal text As String) As String
    Dim normalized As String
    normalized = LCase$(text)
    If InStr(1, normalized, LCase$(SH_U("041A04430437044C043C0438043D")), vbTextCompare) > 0 Or _
        InStr(1, normalized, LCase$(SH_U("041A044304370412042D0421")), vbTextCompare) > 0 Then
        SH_G2StationFromText = "kuz"
        Exit Function
    End If
    If InStr(1, normalized, LCase$(SH_U("041A043E044704430431")), vbTextCompare) > 0 Or _
        InStr(1, normalized, LCase$(SH_U("041A0412042D0421")), vbTextCompare) > 0 Then
        SH_G2StationFromText = "kves"
    End If
End Function

Private Function SH_G2FindOutlookFile(ByVal wb As Workbook, ByVal reportDate As Date, _
    ByVal stationHint As String, ByRef diagnostic As String) As String
    On Error GoTo Unavailable
    Dim outlook As Object, ns As Object, folder As Object, items As Object
    Dim item As Object, att As Object, received As Variant, receivedDate As Date
    Dim mailbox As String, folderPath As String, pattern As String, patternTemplate As String
    Dim subjectFilter As String, senderFilter As String, senderText As String
    Dim depthDays As Long, cutoff As Date, expectedDate As Date
    Dim tempRoot As String, target As String, fileName As String, resolvedFolder As String
    Dim itemsScanned As Long, filteredMessages As Long, attachmentsSeen As Long, xlsxSeen As Long
    Dim sampleNames As String, errNumber As Long, errDescription As String

    mailbox = Trim$(SH_G2Setting(wb, 1))
    folderPath = Trim$(SH_G2Setting(wb, 2))
    patternTemplate = Trim$(SH_G2Setting(wb, 3))
    expectedDate = DateAdd("d", -1, DateValue(reportDate))
    pattern = Replace(patternTemplate, "{date}", Format$(expectedDate, "dd_mm_yyyy"))
    subjectFilter = LCase$(Trim$(SH_G2Setting(wb, 4)))
    senderFilter = LCase$(Trim$(SH_G2Setting(wb, 5)))
    depthDays = CLng(SH_G2SafeDouble(SH_G2Setting(wb, 6)))
    If depthDays < 1 Then depthDays = 1
    If depthDays > 60 Then depthDays = 60
    cutoff = DateAdd("d", -depthDays, DateValue(reportDate))

    diagnostic = SH_G2SearchDiagnostic( _
        mailbox, folderPath, pattern, cutoff, "", stationHint, 0, 0, 0, 0, "" _
    )

    On Error Resume Next
    Set outlook = GetObject(, "Outlook.Application")
    If outlook Is Nothing Then Set outlook = CreateObject("Outlook.Application")
    On Error GoTo Unavailable
    If outlook Is Nothing Then
        diagnostic = diagnostic & vbCrLf & "Outlook application is unavailable."
        Exit Function
    End If

    Set ns = outlook.GetNamespace("MAPI")
    Set folder = SH_G2OutlookFolder(ns, mailbox, folderPath)
    If folder Is Nothing Then
        diagnostic = diagnostic & vbCrLf & "Configured mailbox/folder could not be opened."
        Exit Function
    End If
    resolvedFolder = SH_G2FolderPath(folder)
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
        If SH_G2TryDate(received, receivedDate) Then
            If receivedDate < cutoff Then Exit For
        End If
        itemsScanned = itemsScanned + 1

        If Len(subjectFilter) > 0 Then
            If InStr(1, LCase$(SH_G2SafeText(item.Subject)), subjectFilter, vbTextCompare) = 0 Then _
                GoTo NextItem
        End If
        senderText = LCase$(SH_G2SafeText(item.SenderName) & " " & _
            SH_G2SafeText(item.SenderEmailAddress))
        If Len(senderFilter) > 0 Then
            If InStr(1, senderText, senderFilter, vbTextCompare) = 0 Then GoTo NextItem
        End If
        filteredMessages = filteredMessages + 1

        For Each att In item.Attachments
            attachmentsSeen = attachmentsSeen + 1
            fileName = SH_G2SafeText(att.FileName)
            If Len(fileName) > 0 And LCase$(Right$(fileName, 5)) = ".xlsx" Then
                xlsxSeen = xlsxSeen + 1
                SH_G2AddSample sampleNames, fileName
                If SH_G2AttachmentMatches(fileName, pattern, expectedDate, stationHint) Then
                    target = tempRoot & Application.PathSeparator & SH_G2SafeFileName(fileName)
                    On Error Resume Next
                    Err.Clear
                    If Len(Dir$(target)) > 0 Then Kill target
                    Err.Clear
                    att.SaveAsFile target
                    If Err.Number = 0 And Len(Dir$(target)) > 0 Then
                        SH_G2FindOutlookFile = target
                        diagnostic = SH_G2SearchDiagnostic( _
                            mailbox, folderPath, pattern, cutoff, resolvedFolder, stationHint, _
                            itemsScanned, filteredMessages, attachmentsSeen, xlsxSeen, sampleNames _
                        )
                        On Error GoTo 0
                        Exit Function
                    End If
                    Err.Clear
                    On Error GoTo Unavailable
                End If
            End If
        Next att
NextItem:
    Next item

    diagnostic = SH_G2SearchDiagnostic( _
        mailbox, folderPath, pattern, cutoff, resolvedFolder, stationHint, itemsScanned, _
        filteredMessages, attachmentsSeen, xlsxSeen, sampleNames _
    )
    Exit Function
Unavailable:
    errNumber = Err.Number
    errDescription = Err.Description
    diagnostic = SH_G2SearchDiagnostic( _
        mailbox, folderPath, pattern, cutoff, resolvedFolder, stationHint, itemsScanned, _
        filteredMessages, attachmentsSeen, xlsxSeen, sampleNames _
    )
    If errNumber <> 0 Or Len(errDescription) > 0 Then
        diagnostic = diagnostic & vbCrLf & "Outlook error [" & CStr(errNumber) & "]: " & errDescription
    End If
    SH_G2FindOutlookFile = ""
End Function

Private Function SH_G2OutlookFolder(ByVal ns As Object, ByVal mailbox As String, _
    ByVal folderPath As String) As Object
    On Error Resume Next
    Dim root As Object, inbox As Object, recipient As Object, folder As Object
    Dim parts As Variant, firstIndex As Long, token As String

    If Len(mailbox) > 0 Then Set root = ns.Folders.Item(mailbox)
    If Len(mailbox) > 0 Then
        Set recipient = ns.CreateRecipient(mailbox)
        If Not recipient Is Nothing Then
            recipient.Resolve
            If recipient.Resolved Then Set inbox = ns.GetSharedDefaultFolder(recipient, 6)
        End If
    End If

    If inbox Is Nothing And Not root Is Nothing Then Set inbox = root.Store.GetDefaultFolder(6)
    If inbox Is Nothing Then Set inbox = ns.GetDefaultFolder(6)
    If inbox Is Nothing Then Exit Function

    If Len(Trim$(folderPath)) = 0 Then
        Set SH_G2OutlookFolder = inbox
        Exit Function
    End If

    parts = Split(Replace(folderPath, "/", "\"), "\")
    firstIndex = LBound(parts)
    Do While firstIndex <= UBound(parts) And Len(Trim$(CStr(parts(firstIndex)))) = 0
        firstIndex = firstIndex + 1
    Loop
    If firstIndex > UBound(parts) Then
        Set SH_G2OutlookFolder = inbox
        Exit Function
    End If

    token = Trim$(CStr(parts(firstIndex)))
    If SH_G2IsInboxToken(token, inbox) Then
        Set folder = SH_G2WalkFolder(inbox, parts, firstIndex + 1)
    Else
        Set folder = SH_G2WalkFolder(inbox, parts, firstIndex)
        If folder Is Nothing And Not root Is Nothing Then
            Set folder = SH_G2WalkFolder(root, parts, firstIndex)
        End If
    End If
    Set SH_G2OutlookFolder = folder
End Function

Private Function SH_G2WalkFolder(ByVal startFolder As Object, ByVal parts As Variant, _
    ByVal firstIndex As Long) As Object
    On Error Resume Next
    Dim folder As Object, index As Long, token As String
    Set folder = startFolder
    If folder Is Nothing Then Exit Function
    If firstIndex > UBound(parts) Then
        Set SH_G2WalkFolder = folder
        Exit Function
    End If
    For index = firstIndex To UBound(parts)
        token = Trim$(CStr(parts(index)))
        If Len(token) > 0 Then
            Set folder = folder.Folders.Item(token)
            If folder Is Nothing Then Exit Function
        End If
    Next index
    Set SH_G2WalkFolder = folder
End Function

Private Function SH_G2IsInboxToken(ByVal token As String, ByVal inbox As Object) As Boolean
    Dim normalized As String, inboxName As String
    normalized = LCase$(Trim$(token))
    inboxName = LCase$(Trim$(SH_G2SafeText(inbox.Name)))
    SH_G2IsInboxToken = ( _
        normalized = LCase$(SH_DefaultSetting(2)) Or _
        normalized = "inbox" Or _
        (Len(inboxName) > 0 And normalized = inboxName) _
    )
End Function

Private Function SH_G2AttachmentMatches(ByVal fileName As String, ByVal pattern As String, _
    ByVal expectedDate As Date, ByVal stationHint As String) As Boolean
    Dim normalizedName As String, expectedToken As String, patternStation As String
    If LCase$(Right$(fileName, 5)) <> ".xlsx" Then Exit Function

    patternStation = SH_G2StationFromText(pattern)
    If LCase$(fileName) Like LCase$(pattern) Then
        If Len(stationHint) = 0 Or Len(patternStation) = 0 Or patternStation = stationHint Then
            SH_G2AttachmentMatches = True
            Exit Function
        End If
    End If

    normalizedName = SH_G2NormalizeFileKey(fileName)
    expectedToken = Format$(expectedDate, "dd_mm_yyyy")
    If InStr(1, normalizedName, expectedToken, vbTextCompare) = 0 Then Exit Function
    If InStr(1, normalizedName, LCase$(SH_U("04330435043D0435044004300446")), vbTextCompare) = 0 Then Exit Function
    If Not SH_G2FileMatchesStation(normalizedName, stationHint) Then Exit Function
    SH_G2AttachmentMatches = True
End Function

Private Function SH_G2FileMatchesStation(ByVal normalizedName As String, _
    ByVal stationHint As String) As Boolean
    If Len(stationHint) = 0 Then
        SH_G2FileMatchesStation = True
        Exit Function
    End If
    If stationHint = "kuz" Then
        SH_G2FileMatchesStation = ( _
            InStr(1, normalizedName, LCase$(SH_U("041A044304370412042D0421")), vbTextCompare) > 0 Or _
            InStr(1, normalizedName, LCase$(SH_U("041A04430437044C043C0438043D")), vbTextCompare) > 0 _
        )
    ElseIf stationHint = "kves" Then
        SH_G2FileMatchesStation = ( _
            InStr(1, normalizedName, LCase$(SH_U("041A0412042D0421")), vbTextCompare) > 0 Or _
            InStr(1, normalizedName, LCase$(SH_U("041A043E044704430431")), vbTextCompare) > 0 _
        )
    Else
        SH_G2FileMatchesStation = True
    End If
End Function

Private Function SH_G2NormalizeFileKey(ByVal fileName As String) As String
    Dim value As String
    value = LCase$(Trim$(fileName))
    If LCase$(Right$(value, 5)) = ".xlsx" Then value = Left$(value, Len(value) - 5)
    value = Replace(value, ChrW$(160), " ")
    value = Replace(value, ".", "_")
    value = Replace(value, "-", "_")
    value = Replace(value, " ", "_")
    Do While InStr(value, "__") > 0
        value = Replace(value, "__", "_")
    Loop
    SH_G2NormalizeFileKey = value
End Function

Private Sub SH_G2AddSample(ByRef samples As String, ByVal fileName As String)
    If Len(samples) >= 700 Then Exit Sub
    If Len(samples) > 0 Then samples = samples & "; "
    samples = samples & fileName
End Sub

Private Function SH_G2FolderPath(ByVal folder As Object) As String
    On Error GoTo Failed
    SH_G2FolderPath = SH_G2SafeText(folder.FolderPath)
    Exit Function
Failed:
    SH_G2FolderPath = ""
End Function

Private Function SH_G2SearchDiagnostic(ByVal mailbox As String, ByVal configuredFolder As String, _
    ByVal pattern As String, ByVal cutoff As Date, ByVal resolvedFolder As String, _
    ByVal stationHint As String, ByVal itemsScanned As Long, ByVal filteredMessages As Long, _
    ByVal attachmentsSeen As Long, ByVal xlsxSeen As Long, ByVal sampleNames As String) As String
    Dim result As String
    result = "Mailbox: " & mailbox & vbCrLf & _
        "Configured folder: " & configuredFolder & vbCrLf & _
        "Resolved folder: " & resolvedFolder & vbCrLf & _
        "Station: " & SH_G2ProfileCaption(stationHint) & vbCrLf & _
        "Attachment mask: " & pattern & vbCrLf & _
        "Search from: " & Format$(cutoff, "dd.mm.yyyy") & vbCrLf & _
        "Messages scanned: " & CStr(itemsScanned) & vbCrLf & _
        "Messages after filters: " & CStr(filteredMessages) & vbCrLf & _
        "Attachments seen: " & CStr(attachmentsSeen) & vbCrLf & _
        "XLSX attachments: " & CStr(xlsxSeen)
    If Len(sampleNames) > 0 Then result = result & vbCrLf & "XLSX samples: " & sampleNames
    SH_G2SearchDiagnostic = result
End Function

Private Sub SH_G2ReadWorkbook(ByVal path As String, ByVal expectedDate As Date, _
    ByRef daily As Double, ByRef own As Double, ByRef profileName As String)
    On Error GoTo Failed
    Dim source As Workbook, ws As Worksheet, sumSheet As Worksheet
    Dim pass As Long, errNumber As Long, errDescription As String, sourceDate As Date
    Dim sumName As String
    sumName = SH_U("04210443043C043C043000200412042D0421")

    Set source = Workbooks.Open(Filename:=path, UpdateLinks:=0, ReadOnly:=True, AddToMru:=False)

    For pass = 1 To 2
        For Each ws In source.Worksheets
            ws.Calculate
        Next ws
    Next pass

    If Not SH_HasSheet(source, sumName) Then
        Err.Raise vbObjectError + 685, , "Generation workbook has no 'Sum WES' sheet."
    End If
    Set sumSheet = source.Worksheets(sumName)

    If SH_G2TryKuzProfile(sumSheet, daily, own) Then
        profileName = "kuz"
    ElseIf SH_G2TryKvesProfile(sumSheet, daily, own) Then
        profileName = "kves"
    Else
        Err.Raise vbObjectError + 686, , _
            "Generation workbook does not match the Kochubeevskaya or Kuzminskaya contract."
    End If

    If SH_G2TryDate(sumSheet.Range("A2").Value2, sourceDate) Then
        If DateValue(sourceDate) <> DateValue(expectedDate) Then
            Err.Raise vbObjectError + 688, , _
                "Generation workbook date does not match the report day."
        End If
    End If

    daily = SH_G2RoundKwh(daily)
    own = SH_G2RoundKwh(own)
    If daily < 0 Or daily > 20000000# Then
        Err.Raise vbObjectError + 689, , "Daily generation is outside the accepted range."
    End If
    If own < 0 Or own > 5000000# Then
        Err.Raise vbObjectError + 690, , "Own-use generation value is outside the accepted range."
    End If

    source.Close SaveChanges:=False
    Set source = Nothing
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    On Error Resume Next
    If Not source Is Nothing Then source.Close SaveChanges:=False
    On Error GoTo 0
    If errNumber = 0 Then errNumber = vbObjectError + 691
    If Len(errDescription) = 0 Then errDescription = "Could not read generation workbook."
    Err.Raise errNumber, , errDescription
End Sub

Private Function SH_G2TryKuzProfile(ByVal ws As Worksheet, _
    ByRef daily As Double, ByRef own As Double) As Boolean
    Dim headerGeneration As String, headerOwn As String
    headerGeneration = LCase$(SH_G2SafeText(ws.Range("J1").Value2))
    headerOwn = LCase$(SH_G2SafeText(ws.Range("Z1").Value2))

    If InStr(1, headerGeneration, LCase$(SH_U("04210443043C043C04300020043F043E00200412042D0421")), _
        vbTextCompare) = 0 Then Exit Function
    If InStr(1, headerOwn, LCase$(SH_U("043F043E0442044004350431043B0435043D04380435")), _
        vbTextCompare) = 0 Then Exit Function
    If Not SH_G2IsNumericValue(ws.Range("J26").Value2) Then Exit Function
    If Not SH_G2IsNumericValue(ws.Range("Z26").Value2) Then Exit Function

    daily = CDbl(ws.Range("J26").Value2)
    own = CDbl(ws.Range("Z26").Value2)
    SH_G2TryKuzProfile = True
End Function

Private Function SH_G2TryKvesProfile(ByVal ws As Worksheet, _
    ByRef daily As Double, ByRef own As Double) As Boolean
    Dim rowNumber As Long, numericOwnRows As Long
    If SH_G2TryKuzProfile(ws, daily, own) Then Exit Function
    If Not SH_G2IsNumericValue(ws.Range("G26").Value2) Then Exit Function
    If Not SH_G2IsNumericValue(ws.Range("Q26").Value2) Then Exit Function

    For rowNumber = 2 To 25
        If SH_G2IsNumericValue(ws.Range("Q" & CStr(rowNumber)).Value2) Then
            numericOwnRows = numericOwnRows + 1
        End If
    Next rowNumber
    If numericOwnRows < 20 Then Exit Function

    daily = CDbl(ws.Range("G26").Value2)
    own = CDbl(ws.Range("Q26").Value2)
    SH_G2TryKvesProfile = True
End Function

Private Function SH_G2RoundKwh(ByVal value As Double) As Double
    SH_G2RoundKwh = Application.WorksheetFunction.Round(value, 0)
End Function

Private Function SH_G2ProfileCaption(ByVal profileName As String) As String
    Select Case LCase$(profileName)
        Case "kves": SH_G2ProfileCaption = SH_U("041A043E0447044304310435043504320441043A0430044F")
        Case "kuz": SH_G2ProfileCaption = SH_U("041A04430437044C043C0438043D0441043A0430044F")
        Case Else: SH_G2ProfileCaption = SH_U("041004320442043E")
    End Select
End Function

Private Function SH_G2IsNumericValue(ByVal value As Variant) As Boolean
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If VarType(value) = vbString Then
        If Len(Trim$(CStr(value))) = 0 Then Exit Function
    End If
    SH_G2IsNumericValue = IsNumeric(value)
    Exit Function
Failed:
    SH_G2IsNumericValue = False
End Function

Private Function SH_G2SafeText(ByVal value As Variant) As String
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    SH_G2SafeText = CStr(value)
    Exit Function
Failed:
    SH_G2SafeText = ""
End Function

Private Function SH_G2SafeDouble(ByVal value As Variant) As Double
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If IsNumeric(value) Then SH_G2SafeDouble = CDbl(value)
    Exit Function
Failed:
    SH_G2SafeDouble = 0#
End Function

Private Function SH_G2TryDate(ByVal value As Variant, ByRef result As Date) As Boolean
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    If IsDate(value) Or IsNumeric(value) Then
        result = CDate(value)
        SH_G2TryDate = True
    End If
    Exit Function
Failed:
    SH_G2TryDate = False
End Function

Private Function SH_G2SafeFileName(ByVal name As String) As String
    Dim bad As Variant
    SH_G2SafeFileName = name
    For Each bad In Array("<", ">", ":", Chr$(34), "/", "\", "|", "?", "*")
        SH_G2SafeFileName = Replace(SH_G2SafeFileName, CStr(bad), "_")
    Next bad
End Function
