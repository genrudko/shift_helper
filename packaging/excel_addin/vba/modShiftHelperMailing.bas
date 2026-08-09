Attribute VB_Name = "modShiftHelperMailing"
Option Explicit

Private Const SH_MAIL_MENU_NS As String = "http://schemas.microsoft.com/office/2009/07/customui"

Public Function SH_MailingMenuXml() As String
    On Error GoTo Failed
    Dim wb As Workbook, stationId As Long, xml As String
    Set wb = SH_JournalBook()
    stationId = SH_ReportStationId(wb, True)

    xml = "<menu xmlns=""" & SH_MAIL_MENU_NS & """>"
    xml = xml & SH_MailMenuButton("mailList1", SH_U("0421043F04380441043E043A00200440043004410441044B043B043A0438002021160031"), "list:1")
    xml = xml & SH_MailMenuButton("mailList2", SH_U("0421043F04380441043E043A00200440043004410441044B043B043A0438002021160032"), "list:2")
    xml = xml & SH_MailMenuButton("mailList3", SH_U("0421043F04380441043E043A00200440043004410441044B043B043A0438002021160033"), "list:3")
    xml = xml & SH_MailMenuButton("mailMorning", SH_U("0423044204400435043D043D04380439002004400430043F043E04400442"), "morning")

    If stationId = SH_STATION_KUZ Then
        xml = xml & "<menuSeparator id=""mailSepForeign""/>"
        xml = xml & SH_MailMenuButton("mailForeign1", SH_U("0417043004400443043104350436043D043504440442044C0020201400200441043F04380441043E043A002021160031"), "foreign-list:1")
        xml = xml & SH_MailMenuButton("mailForeign2", SH_U("0417043004400443043104350436043D043504440442044C0020201400200441043F04380441043E043A002021160032"), "foreign-list:2")
        xml = xml & SH_MailMenuButton("mailForeign3", SH_U("0417043004400443043104350436043D043504440442044C0020201400200441043F04380441043E043A002021160033"), "foreign-list:3")
        xml = xml & SH_MailMenuButton("mailForeignMorning", SH_U("0423044204400435043D043D04380439002004400430043F043E044004420020201400200417043004400443043104350436043D043504440442044C"), "foreign-morning")
        xml = xml & SH_MailMenuButton("mailForeignSheet", SH_U("041B043804410442002000AB0417043004400443043104350436043D043504440442044C00BB"), "foreign-sheet")
    End If

    SH_MailingMenuXml = xml & "</menu>"
    Exit Function
Failed:
    SH_MailingMenuXml = "<menu xmlns=""" & SH_MAIL_MENU_NS & """><button id=""mailUnavailable"" label=""Shift-Helper"" enabled=""false""/></menu>"
End Function

Private Function SH_MailMenuButton(ByVal idValue As String, ByVal labelValue As String, _
    ByVal tagValue As String) As String
    SH_MailMenuButton = "<button id=""" & idValue & """ label=""" & SH_XmlEscape(labelValue) & _
        """ tag=""" & tagValue & """ onAction=""SH_RibbonMailingDraft""/>"
End Function

Public Sub SH_CreateStationMailingDraft(ByVal tagValue As String)
    On Error GoTo Failed
    Dim wb As Workbook, stationId As Long, listNumber As Long
    Set wb = SH_JournalBook()
    stationId = SH_ReportStationId(wb, True)

    Select Case LCase$(Trim$(tagValue))
        Case "list:1", "list:2", "list:3"
            listNumber = CLng(Right$(tagValue, 1))
            If stationId = SH_STATION_KUZ Then
                SH_CreateKuzListDraft wb, listNumber, False
            Else
                SH_CreateKochListDraft wb, listNumber
            End If
        Case "morning"
            SH_CreateMorningDraft wb, stationId, False
        Case "foreign-list:1", "foreign-list:2", "foreign-list:3"
            If stationId <> SH_STATION_KUZ Then Err.Raise vbObjectError + 710, , "Foreign mailing is available only for Kuzminskaya."
            listNumber = CLng(Right$(tagValue, 1))
            SH_CreateKuzListDraft wb, listNumber, True
        Case "foreign-morning"
            If stationId <> SH_STATION_KUZ Then Err.Raise vbObjectError + 711, , "Foreign mailing is available only for Kuzminskaya."
            SH_CreateMorningDraft wb, stationId, True
        Case "foreign-sheet"
            If stationId <> SH_STATION_KUZ Then Err.Raise vbObjectError + 712, , "Foreign mailing is available only for Kuzminskaya."
            SH_CreateKuzForeignSheetDraft wb
        Case Else
            Err.Raise vbObjectError + 713, , "Unknown mailing action."
    End Select
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Private Sub SH_CreateKochListDraft(ByVal wb As Workbook, ByVal listNumber As Long)
    Dim ws As Worksheet, subjectCell As String, recipientCell As String
    Set ws = SH_MailRequireSheet(wb, SH_U("0420043004410441044B043B043A0430"))
    Select Case listNumber
        Case 1: subjectCell = "B2": recipientCell = "A8"
        Case 2: subjectCell = "B3": recipientCell = "B8"
        Case 3: subjectCell = "B4": recipientCell = "C8"
        Case Else: Err.Raise 5
    End Select
    SH_CreateMailDraft ws, "B1", recipientCell, "", subjectCell, "C2", "", "", True
End Sub

Private Sub SH_CreateKuzListDraft(ByVal wb As Workbook, ByVal listNumber As Long, _
    ByVal foreignCopy As Boolean)
    Dim ws As Worksheet, sheetName As String
    If listNumber < 1 Or listNumber > 3 Then Err.Raise 5
    sheetName = SH_U("0421043F04380441043E043A00200440043004410441044B043B043A043800202116") & CStr(listNumber)
    Set ws = SH_MailRequireSheet(wb, sheetName)

    If foreignCopy Then
        SH_CreateMailDraft ws, "B17", "B18", "B19", "B20", "B8", "B9", "B10", False
    Else
        SH_CreateMailDraft ws, "B4", "B5", "", "B7", "B8", "B9", "B10", False
    End If
End Sub

Private Sub SH_CreateMorningDraft(ByVal wb As Workbook, ByVal stationId As Long, _
    ByVal foreignCopy As Boolean)
    Dim ws As Worksheet
    Set ws = SH_MailRequireSheet(wb, SH_U("04200430043F043E044004420020044304420440043E"))
    If foreignCopy Then
        SH_CreateMailDraft ws, "B17", "B18", "B19", "B20", "B8", "B9", "B10", False
    Else
        SH_CreateMailDraft ws, "B4", "B5", "", "B7", "B8", "B9", "B10", False
    End If
End Sub

Private Sub SH_CreateKuzForeignSheetDraft(ByVal wb As Workbook)
    Dim ws As Worksheet
    Set ws = SH_MailRequireSheet(wb, SH_U("0417043004400443043104350436043D043504440442044C"))
    SH_CreateMailDraft ws, "B2", "B3", "B4", "B5", "B6", "B7", "B10", False
End Sub

Private Function SH_MailRequireSheet(ByVal wb As Workbook, ByVal sheetName As String) As Worksheet
    If Not SH_HasSheet(wb, sheetName) Then
        Err.Raise vbObjectError + 714, , SH_U("041D04350020043D0430043904340435043D0020043B04380441044200200440043004410441044B043B043A0438003A0020") & sheetName
    End If
    Set SH_MailRequireSheet = wb.Worksheets(sheetName)
End Function

Private Sub SH_CreateMailDraft(ByVal ws As Worksheet, ByVal senderCell As String, _
    ByVal toCell As String, ByVal ccCell As String, ByVal subjectCell As String, _
    ByVal bodyCell1 As String, ByVal bodyCell2 As String, ByVal attachmentCell As String, _
    ByVal insertBeforeSignature As Boolean)

    Dim outlook As Object, mail As Object
    Dim sender As String, recipient As String, ccValue As String
    Dim subjectValue As String, bodyValue As String, attachment As String

    sender = Trim$(SH_MailSafeText(ws.Range(senderCell).Value2))
    recipient = SH_MailNormalizeRecipients(SH_MailSafeText(ws.Range(toCell).Value2))
    If Len(ccCell) > 0 Then ccValue = SH_MailNormalizeRecipients(SH_MailSafeText(ws.Range(ccCell).Value2))
    subjectValue = Trim$(SH_MailSafeText(ws.Range(subjectCell).Value2))
    bodyValue = SH_MailSafeText(ws.Range(bodyCell1).Value2)
    If Len(bodyCell2) > 0 Then bodyValue = bodyValue & SH_MailSafeText(ws.Range(bodyCell2).Value2)
    If Len(attachmentCell) > 0 Then attachment = Trim$(SH_MailSafeText(ws.Range(attachmentCell).Value2))

    If Len(recipient) = 0 Then Err.Raise vbObjectError + 715, , SH_U("041D043500200443043A043004370430043D044B0020043F043E043B04430447043004420435043B0438002E")
    If Len(subjectValue) = 0 Then Err.Raise vbObjectError + 716, , SH_U("041D043500200443043A043004370430043D0430002004420435043C04300020043F04380441044C043C0430002E")

    On Error Resume Next
    Set outlook = GetObject(, "Outlook.Application")
    If outlook Is Nothing Then Set outlook = CreateObject("Outlook.Application")
    On Error GoTo Failed
    If outlook Is Nothing Then Err.Raise vbObjectError + 717, , SH_U("004F00750074006C006F006F006B0020043D04350434043E044104420443043F0435043D002E")
    Set mail = outlook.CreateItem(0)
    If mail Is Nothing Then Err.Raise vbObjectError + 718, , SH_U("041D04350020044304340430043B043E0441044C00200441043E0437043404300442044C0020043F04380441044C043C043E0020004F00750074006C006F006F006B002E")

    If Len(sender) > 0 Then mail.SentOnBehalfOfName = sender
    mail.To = recipient
    mail.CC = ccValue
    mail.BCC = ""
    mail.Subject = subjectValue
    mail.BodyFormat = 2

    If insertBeforeSignature Then
        mail.Display
        SH_MailInsertBodyArial12 mail, bodyValue
    Else
        mail.HTMLBody = bodyValue
        If Len(attachment) > 0 Then
            If Len(Dir$(attachment)) = 0 Then Err.Raise vbObjectError + 719, , "Attachment not found: " & attachment
            mail.Attachments.Add attachment
        End If
        mail.Display
    End If
    Exit Sub
Failed:
    Err.Raise Err.Number, , "Mail draft [" & ws.Name & "]: " & Err.Description
End Sub

Private Function SH_MailNormalizeRecipients(ByVal rawValue As String) As String
    Dim result As String
    result = Trim$(rawValue)
    result = Replace(result, vbCrLf, "; ")
    result = Replace(result, vbCr, "; ")
    result = Replace(result, vbLf, "; ")
    result = Replace(result, ",", ";")
    Do While InStr(result, ";;") > 0
        result = Replace(result, ";;", ";")
    Loop
    Do While InStr(result, "  ") > 0
        result = Replace(result, "  ", " ")
    Loop
    result = Trim$(result)
    Do While Len(result) > 0 And Left$(result, 1) = ";"
        result = Trim$(Mid$(result, 2))
    Loop
    Do While Len(result) > 0 And Right$(result, 1) = ";"
        result = Trim$(Left$(result, Len(result) - 1))
    Loop
    SH_MailNormalizeRecipients = result
End Function

Private Sub SH_MailInsertBodyArial12(ByVal mail As Object, ByVal bodyText As String)
    Dim wdDoc As Object, wdRange As Object, insertedRange As Object
    Dim insertText As String, insertLength As Long
    insertText = Replace(CStr(bodyText), vbCrLf, vbCr)
    insertText = Replace(insertText, vbLf, vbCr)
    If Len(Trim$(insertText)) > 0 Then insertText = insertText & vbCr & vbCr
    insertLength = Len(insertText)
    If insertLength = 0 Then Exit Sub
    Set wdDoc = mail.GetInspector.WordEditor
    Set wdRange = wdDoc.Range(0, 0)
    wdRange.Text = insertText
    Set insertedRange = wdDoc.Range(0, insertLength)
    insertedRange.Font.Name = "Arial"
    insertedRange.Font.Size = 12
End Sub

Private Function SH_MailSafeText(ByVal value As Variant) As String
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    SH_MailSafeText = CStr(value)
    Exit Function
Failed:
    SH_MailSafeText = ""
End Function

Public Sub SH_RegisterGeneratedReport(ByVal wb As Workbook, ByVal reportPath As String)
    On Error Resume Next
    Dim ws As Worksheet, stationId As Long
    stationId = SH_ReportStationId(wb, False)
    If SH_HasSheet(wb, SH_U("04200430043F043E044004420020044304420440043E")) Then
        Set ws = wb.Worksheets(SH_U("04200430043F043E044004420020044304420440043E"))
        ws.Range("B10").Value = reportPath
        If stationId = SH_STATION_KUZ Then ws.Range("B23").Value = reportPath
    End If
    On Error GoTo 0
End Sub
