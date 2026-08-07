Attribute VB_Name = "modShiftHelperOutlook"
Option Explicit

Private mSettingsBook As Workbook
Private mSettingsJournal As Workbook

Public Sub SH_ShowOutlookSettings()
    On Error GoTo Failed
    Dim ws As Worksheet, i As Long, area As Range, shape As Shape, captions As Variant
    Set mSettingsJournal = SH_JournalBook()
    If Not mSettingsBook Is Nothing Then
        Application.DisplayAlerts = False
        mSettingsBook.Close SaveChanges:=False
        Application.DisplayAlerts = True
    End If
    Set mSettingsBook = Workbooks.Add(xlWBATWorksheet)
    Set ws = mSettingsBook.Worksheets(1)
    ws.Name = "Outlook"
    ActiveWindow.DisplayGridlines = False
    ActiveWindow.Zoom = 100
    ws.Columns("A").ColumnWidth = 42
    ws.Columns("B").ColumnWidth = 54
    ws.Range("A1:B1").Merge
    ws.Range("A1").Value = SH_U("041D0430044104420440043E0439043A04380020004F00750074006C006F006F006B")
    ws.Range("A1").Font.Bold = True
    ws.Range("A1").HorizontalAlignment = xlCenter
    captions = Array( _
        SH_U("041F043E04470442043E0432044B04390020044F04490438043A"), _
        SH_U("041F0430043F043A0430"), _
        SH_U("041C04300441043A043000200432043B043E04360435043D0438044F00200028007B0064006100740065007D0020003D0020043F044004350434044B043404430449043804350020044104430442043A04380029"), _
        SH_U("04220435043C04300020043F04380441044C043C043000200441043E043404350440043604380442"), _
        SH_U("041E0442043F044004300432043804420435043B044C00200441043E043404350440043604380442"), _
        SH_U("0413043B044304310438043D04300020043F043E04380441043A0430002C00200434043D04350439"), _
        SH_U("042004430447043D043E043900200432044B0431043E04400020044404300439043B04300020043F044004380020043E0442044104430442044104420432043804380020043F04380441044C043C0430"))
    For i = 1 To 7
        ws.Cells(i + 2, 1).Value = captions(i - 1)
        ws.Cells(i + 2, 2).Value = SH_MetaValue(mSettingsJournal, SH_Label(i), SH_DefaultSetting(i))
    Next i
    ws.Cells(8, 2).NumberFormat = "0"
    ws.Cells(9, 2).NumberFormat = "0"
    Set area = ws.Range("A11:A12")
    Set shape = ws.Shapes.AddShape(msoShapeRoundedRectangle, area.Left + 2, area.Top + 2, area.Width - 4, area.Height - 4)
    shape.TextFrame2.TextRange.Text = SH_U("0421043E044504400430043D04380442044C")
    shape.OnAction = SH_QualifiedMacro("SH_SaveOutlookSettings")
    Set area = ws.Range("B11:B12")
    Set shape = ws.Shapes.AddShape(msoShapeRoundedRectangle, area.Left + 2, area.Top + 2, area.Width - 4, area.Height - 4)
    shape.TextFrame2.TextRange.Text = SH_U("041E0442043C0435043D0430")
    shape.OnAction = SH_QualifiedMacro("SH_CancelOutlookSettings")
    mSettingsBook.Windows(1).Caption = "Shift-Helper - Outlook"
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_SaveOutlookSettings()
    On Error GoTo Failed
    Dim i As Long, value As String
    If mSettingsBook Is Nothing Or mSettingsJournal Is Nothing Then Exit Sub
    For i = 1 To 7
        value = Trim$(CStr(mSettingsBook.Worksheets(1).Cells(i + 2, 2).Value2))
        If i = 1 And Len(value) = 0 Then Err.Raise vbObjectError + 580, , "Mailbox is required."
        If i = 3 And Len(value) = 0 Then Err.Raise vbObjectError + 581, , "Attachment mask is required."
        If i = 6 Then
            If Not IsNumeric(value) Then Err.Raise vbObjectError + 582, , "Search depth must be numeric."
            If CLng(value) < 1 Or CLng(value) > 60 Then Err.Raise vbObjectError + 583, , "Search depth: 1..60."
        End If
        If i = 7 Then value = IIf(Val(value) <> 0, "1", "0")
        SH_SetMetaValue mSettingsJournal, SH_Label(i), value
        SaveSetting "Shift-Helper", "Outlook", SH_Label(i), value
    Next i
    SH_CloseSettings
    MsgBox SH_U("041D0430044104420440043E0439043A04380020004F00750074006C006F006F006B00200441043E044504400430043D0435043D044B002E"), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_CancelOutlookSettings()
    SH_CloseSettings
End Sub

Private Sub SH_CloseSettings()
    If mSettingsBook Is Nothing Then Exit Sub
    Application.DisplayAlerts = False
    mSettingsBook.Close SaveChanges:=False
    Application.DisplayAlerts = True
    Set mSettingsBook = Nothing
    Set mSettingsJournal = Nothing
End Sub

Public Sub SH_ImportGeneration()
    On Error GoTo Failed
    Dim wb As Workbook, main As Worksheet, reportDate As Date, sourcePath As String
    Dim daily As Double, own As Double, monthGeneration As Double, monthOwn As Double
    Dim oldDaily As Double, oldOwn As Double, oldDateValue As Variant, oldDate As Date, hasOldDate As Boolean
    Set wb = SH_JournalBook()
    If Not SH_HasSheet(wb, SH_InputSheetName(1)) Then SH_PrepareReportContour
    Set main = wb.Worksheets(SH_InputSheetName(1))
    reportDate = SH_ReportDate(wb)
    sourcePath = SH_FindOutlookGeneration(wb, reportDate)
    If Len(sourcePath) = 0 And Val(CStr(SH_MetaValue(wb, SH_Label(7), SH_DefaultSetting(7)))) <> 0 Then
        sourcePath = SH_PickGenerationFile()
    End If
    If Len(sourcePath) = 0 Then
        MsgBox SH_U("041F043E04340445043E0434044F0449043504350020043F04380441044C043C043E0020004F00750074006C006F006F006B0020043D04350020043D0430043904340435043D043E002E"), vbInformation, "Shift-Helper"
        Exit Sub
    End If
    If LCase$(Right$(sourcePath, 5)) <> ".xlsx" Then Err.Raise vbObjectError + 584, , "Only .xlsx generation attachments are allowed."
    SH_ReadGeneration sourcePath, daily, own

    monthGeneration = CDbl(Val(CStr(main.Range("C11").Value2)))
    monthOwn = CDbl(Val(CStr(main.Range("C17").Value2)))
    oldDaily = CDbl(Val(CStr(SH_MetaValue(wb, SH_Label(10), 0))))
    oldOwn = CDbl(Val(CStr(SH_MetaValue(wb, SH_Label(11), 0))))
    oldDateValue = SH_MetaValue(wb, SH_Label(9), Empty)
    If IsDate(oldDateValue) Or IsNumeric(oldDateValue) Then
        On Error Resume Next
        oldDate = CDate(oldDateValue)
        hasOldDate = (Err.Number = 0)
        Err.Clear
        On Error GoTo Failed
    End If

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
    SH_ApplyCriticalFormulas wb
    wb.Calculate
    MsgBox SH_U("04130435043D04350440043004460438044F00200438043C043F043E0440044204380440043E04320430043D0430002E") & vbCrLf & _
        Format$(daily, "0") & " kWh" & vbCrLf & Format$(daily / 24000#, "0.00") & " MW", vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    MsgBox SH_U("041D04350020044304340430043B043E0441044C00200438043C043F043E0440044204380440043E043204300442044C002004330435043D04350440043004460438044E003A0020") & Err.Description, vbExclamation, "Shift-Helper"
End Sub

Private Function SH_PickGenerationFile() As String
    Dim selected As Variant
    selected = Application.GetOpenFilename("Excel Workbook (*.xlsx),*.xlsx", , SH_U("0412044B0431043504400438044204350020044404300439043B002004330435043D043504400430044604380438"))
    If VarType(selected) <> vbBoolean Then SH_PickGenerationFile = CStr(selected)
End Function

Private Function SH_FindOutlookGeneration(ByVal wb As Workbook, ByVal reportDate As Date) As String
    On Error GoTo Unavailable
    Dim outlook As Object, ns As Object, folder As Object, items As Object, item As Object, att As Object
    Dim mailbox As String, folderPath As String, pattern As String, subjectFilter As String, senderFilter As String
    Dim depthDays As Long, cutoff As Date, tempRoot As String, target As String, senderText As String
    mailbox = CStr(SH_MetaValue(wb, SH_Label(1), GetSetting("Shift-Helper", "Outlook", SH_Label(1), SH_DefaultSetting(1))))
    folderPath = CStr(SH_MetaValue(wb, SH_Label(2), GetSetting("Shift-Helper", "Outlook", SH_Label(2), SH_DefaultSetting(2))))
    pattern = CStr(SH_MetaValue(wb, SH_Label(3), GetSetting("Shift-Helper", "Outlook", SH_Label(3), SH_DefaultSetting(3))))
    pattern = Replace(pattern, "{date}", Format$(DateAdd("d", -1, reportDate), "dd_mm_yyyy"))
    subjectFilter = LCase$(CStr(SH_MetaValue(wb, SH_Label(4), GetSetting("Shift-Helper", "Outlook", SH_Label(4), ""))))
    senderFilter = LCase$(CStr(SH_MetaValue(wb, SH_Label(5), GetSetting("Shift-Helper", "Outlook", SH_Label(5), ""))))
    depthDays = CLng(Val(CStr(SH_MetaValue(wb, SH_Label(6), GetSetting("Shift-Helper", "Outlook", SH_Label(6), "7")))))
    If depthDays < 1 Then depthDays = 1
    If depthDays > 60 Then depthDays = 60
    cutoff = DateAdd("d", -depthDays, reportDate)

    On Error Resume Next
    Set outlook = GetObject(, "Outlook.Application")
    If outlook Is Nothing Then Set outlook = CreateObject("Outlook.Application")
    On Error GoTo Unavailable
    If outlook Is Nothing Then GoTo Unavailable
    Set ns = outlook.GetNamespace("MAPI")
    Set folder = SH_OutlookFolder(ns, mailbox, folderPath)
    If folder Is Nothing Then GoTo Unavailable
    Set items = folder.Items
    items.Sort "[ReceivedTime]", True

    tempRoot = Environ$("TEMP") & Application.PathSeparator & "ShiftHelper"
    If Dir$(tempRoot, vbDirectory) = vbNullString Then MkDir tempRoot
    For Each item In items
        On Error Resume Next
        If item.ReceivedTime < cutoff Then Exit For
        If Len(subjectFilter) > 0 Then
            If InStr(1, LCase$(CStr(item.Subject)), subjectFilter, vbTextCompare) = 0 Then GoTo NextItem
        End If
        senderText = LCase$(CStr(item.SenderName) & " " & CStr(item.SenderEmailAddress))
        If Len(senderFilter) > 0 Then
            If InStr(1, senderText, senderFilter, vbTextCompare) = 0 Then GoTo NextItem
        End If
        For Each att In item.Attachments
            If LCase$(CStr(att.FileName)) Like LCase$(pattern) Then
                If LCase$(Right$(CStr(att.FileName), 5)) <> ".xlsx" Then GoTo NextAttachment
                target = tempRoot & Application.PathSeparator & SH_SafeFileName(CStr(att.FileName))
                Err.Clear
                Kill target
                Err.Clear
                att.SaveAsFile target
                If Err.Number = 0 And Len(Dir$(target)) > 0 Then
                    SH_FindOutlookGeneration = target
                    On Error GoTo 0
                    Exit Function
                End If
NextAttachment:
            End If
        Next att
NextItem:
        Err.Clear
        On Error GoTo Unavailable
    Next item
    Exit Function
Unavailable:
    SH_FindOutlookGeneration = ""
End Function

Private Function SH_OutlookFolder(ByVal ns As Object, ByVal mailbox As String, ByVal folderPath As String) As Object
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
            If LCase$(Trim$(CStr(part))) <> LCase$(SH_DefaultSetting(2)) Or folder.DefaultItemType <> 0 Then
                Set folder = folder.Folders.Item(Trim$(CStr(part)))
                If folder Is Nothing Then Exit Function
            End If
        End If
    Next part
    Set SH_OutlookFolder = folder
End Function

Private Function SH_SafeFileName(ByVal name As String) As String
    Dim bad As Variant
    SH_SafeFileName = name
    For Each bad In Array("<", ">", ":", Chr$(34), "/", "\", "|", "?", "*")
        SH_SafeFileName = Replace(SH_SafeFileName, CStr(bad), "_")
    Next bad
End Function

Private Sub SH_ReadGeneration(ByVal path As String, ByRef daily As Double, ByRef own As Double)
    Dim source As Workbook, ws As Worksheet, scan As Range, cell As Range, text As String, value As Variant
    Dim foundDaily As Boolean, foundOwn As Boolean, maxRows As Long, maxCols As Long
    Set source = Workbooks.Open(Filename:=path, UpdateLinks:=0, ReadOnly:=True, AddToMru:=False)
    On Error GoTo Failed
    For Each ws In source.Worksheets
        maxRows = Application.Min(ws.UsedRange.Rows.Count, 250)
        maxCols = Application.Min(ws.UsedRange.Columns.Count, 80)
        If maxRows > 0 And maxCols > 0 Then
            Set scan = ws.Range(ws.UsedRange.Cells(1, 1), ws.UsedRange.Cells(maxRows, maxCols))
            For Each cell In scan.Cells
                text = LCase$(CStr(cell.Text))
                If Not foundDaily Then
                    If InStr(1, text, SH_U("0432044B044004300431043E0442043A0430"), vbTextCompare) > 0 And _
                       (InStr(1, text, SH_U("044104430442"), vbTextCompare) > 0 Or InStr(1, text, SH_U("04320447043504400430"), vbTextCompare) > 0) And _
                       InStr(1, text, SH_U("043C04350441044F0446"), vbTextCompare) = 0 Then
                        value = SH_NearNumeric(cell)
                        If Not IsEmpty(value) Then daily = CDbl(value): foundDaily = True
                    End If
                End If
                If Not foundOwn Then
                    If InStr(1, text, SH_U("0441043E04310441044204320435043D"), vbTextCompare) > 0 And _
                       InStr(1, text, SH_U("043D044304360434"), vbTextCompare) > 0 And _
                       (InStr(1, text, SH_U("044104430442"), vbTextCompare) > 0 Or InStr(1, text, SH_U("04320447043504400430"), vbTextCompare) > 0) And _
                       InStr(1, text, SH_U("043C04350441044F0446"), vbTextCompare) = 0 Then
                        value = SH_NearNumeric(cell)
                        If Not IsEmpty(value) Then own = CDbl(value): foundOwn = True
                    End If
                End If
                If foundDaily And foundOwn Then Exit For
            Next cell
        End If
        If foundDaily And foundOwn Then Exit For
    Next ws
    source.Close SaveChanges:=False
    If Not foundDaily Or Not foundOwn Then Err.Raise vbObjectError + 585, , "Expected generation fields were not found in the workbook."
    If daily < 0 Or own < 0 Then Err.Raise vbObjectError + 586, , "Generation values must be non-negative."
    Exit Sub
Failed:
    source.Close SaveChanges:=False
    Err.Raise Err.Number, , Err.Description
End Sub

Private Function SH_NearNumeric(ByVal labelCell As Range) As Variant
    Dim offset As Long, value As Variant
    For offset = 1 To 8
        value = labelCell.Offset(0, offset).Value2
        If IsNumeric(value) And Len(CStr(value)) > 0 Then SH_NearNumeric = CDbl(value): Exit Function
    Next offset
    For offset = 1 To 4
        value = labelCell.Offset(offset, 0).Value2
        If IsNumeric(value) And Len(CStr(value)) > 0 Then SH_NearNumeric = CDbl(value): Exit Function
    Next offset
    SH_NearNumeric = Empty
End Function
