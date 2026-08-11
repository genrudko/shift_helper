Attribute VB_Name = "modShiftHelperNSS"
Option Explicit

Private Const SH_NSS_LIST_PREFIX As String = "report.nss.list."
Private Const SH_NSS_SELECTED_PREFIX As String = "report.nss.selected."
Private Const SH_NSS_CELL As String = "B7"

Public Function SH_NssMenuXml() As String
    On Error GoTo Fallback
    Dim wb As Workbook, stationId As Long, listText As String, selected As String
    Dim xml As String, i As Long, itemCount As Long, itemText As String, labelText As String

    Set wb = SH_JournalBook()
    stationId = SH_ReportStationId(wb, True)
    SH_ApplyNssForStation wb, stationId
    listText = SH_NssListText(wb, stationId)
    selected = SH_NssSelected(wb, stationId)

    xml = "<menu xmlns=""http://schemas.microsoft.com/office/2009/07/customui"">"
    xml = xml & "<button id=""nssStationInfo"" label=""" & _
        SH_XmlEscape(SH_U("042104420430043D04460438044F003A0020") & _
        SH_ReportStationName(stationId)) & """ enabled=""false""/>"
    If Len(selected) > 0 Then
        labelText = SH_U("041D04210421003A0020") & selected
    Else
        labelText = SH_U("041D04210421003A0020") & SH_U("041D043500200432044B043104400430043D")
    End If
    xml = xml & "<button id=""nssCurrentInfo"" label=""" & _
        SH_XmlEscape(SH_MenuText(labelText)) & """ enabled=""false""/>"
    xml = xml & "<menuSeparator id=""nssChoicesSeparator""/>"

    itemCount = SH_NssCount(listText)
    If itemCount = 0 Then
        xml = xml & "<button id=""nssNoChoices"" label=""" & _
            SH_U("0421043F04380441043E043A0020041D042104210020043D04350020043D0430044104420440043E0435043D") & _
            """ enabled=""false""/>"
    Else
        For i = 1 To itemCount
            itemText = SH_NssNameAt(listText, i)
            labelText = itemText
            If StrComp(itemText, selected, vbTextCompare) = 0 Then labelText = "* " & itemText
            xml = xml & "<button id=""nssChoice""" & CStr(stationId) & """_""" & CStr(i) & _
                """ label=""" & SH_XmlEscape(SH_MenuText(labelText)) & _
                """ tag=""select:" & CStr(stationId) & ":" & CStr(i) & _
                """ onAction=""SH_RibbonNssAction""/>"
        Next i
    End If

    xml = xml & "<menuSeparator id=""nssSettingsSeparator""/>"
    xml = xml & "<button id=""nssEditKoch"" label=""" & _
        SH_U("041D0430044104420440043E04380442044C00200441043F04380441043E043A0020041D042104210020041A043E0447044304310435043504320441043A043E043900200412042D0421002E002E002E") & _
        """ tag=""edit:1"" onAction=""SH_RibbonNssAction""/>"
    xml = xml & "<button id=""nssEditKuz"" label=""" & _
        SH_U("041D0430044104420440043E04380442044C00200441043F04380441043E043A0020041D042104210020041A04430437044C043C0438043D0441043A043E043900200412042D0421002E002E002E") & _
        """ tag=""edit:2"" onAction=""SH_RibbonNssAction""/>"
    xml = xml & "</menu>"
    SH_NssMenuXml = xml
    Exit Function

Fallback:
    SH_NssMenuXml = _
        "<menu xmlns=""http://schemas.microsoft.com/office/2009/07/customui"">" & _
        "<button id=""nssEditKoch"" label=""" & _
        SH_U("041D0430044104420440043E04380442044C00200441043F04380441043E043A0020041D042104210020041A043E0447044304310435043504320441043A043E043900200412042D0421002E002E002E") & _
        """ tag=""edit:1"" onAction=""SH_RibbonNssAction""/>" & _
        "<button id=""nssEditKuz"" label=""" & _
        SH_U("041D0430044104420440043E04380442044C00200441043F04380441043E043A0020041D042104210020041A04430437044C043C0438043D0441043A043E043900200412042D0421002E002E002E") & _
        """ tag=""edit:2"" onAction=""SH_RibbonNssAction""/>" & _
        "</menu>"
End Function

Public Sub SH_NssRibbonAction(ByVal actionTag As String)
    On Error GoTo Failed
    Dim parts As Variant, stationId As Long, itemIndex As Long
    parts = Split(actionTag, ":")
    If UBound(parts) < 1 Then Err.Raise 5, , "Invalid NSS action."
    stationId = CLng(parts(1))

    Select Case LCase$(CStr(parts(0)))
        Case "edit"
            SH_EditNssList stationId
        Case "select"
            If UBound(parts) < 2 Then Err.Raise 5, , "Invalid NSS selection."
            itemIndex = CLng(parts(2))
            SH_SelectNss stationId, itemIndex
        Case Else
            Err.Raise 5, , "Unknown NSS action."
    End Select
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_ApplyNssForCurrentStation(ByVal wb As Workbook)
    Dim stationId As Long
    stationId = SH_ReportStationId(wb, True)
    SH_ApplyNssForStation wb, stationId
End Sub

Public Sub SH_ApplyNssForStation(ByVal wb As Workbook, ByVal stationId As Long)
    Dim listText As String, selected As String, prep As Worksheet
    listText = SH_NssListText(wb, stationId)
    selected = SH_NssSelected(wb, stationId)

    If Len(listText) > 0 Then
        If Len(selected) = 0 Or Not SH_NssListContains(listText, selected) Then
            selected = SH_NssNameAt(listText, 1)
            SH_SetMetaValue wb, SH_NssSelectedKey(stationId), selected
        End If
    ElseIf Len(selected) = 0 Then
        Exit Sub
    End If

    Set prep = SH_EnsurePrepSheet(wb)
    prep.Range(SH_NSS_CELL).Value = selected
End Sub

Public Function SH_NssSelected(ByVal wb As Workbook, ByVal stationId As Long) As String
    SH_NssSelected = Trim$(CStr(SH_MetaValue(wb, SH_NssSelectedKey(stationId), "")))
End Function

Private Sub SH_EditNssList(ByVal stationId As Long)
    Dim wb As Workbook, raw As Variant, currentText As String, normalized As String
    Dim promptText As String, selected As String

    Set wb = SH_JournalBook()
    currentText = SH_NssListText(wb, stationId)
    promptText = SH_U("041204320435043404380442043500200441043F04380441043E043A0020041D0421042100200434043B044F0020") & _
        SH_ReportStationName(stationId) & "." & vbCrLf & _
        SH_U("04200430043704340435043B044F043904420435002004440430043C0438043B04380438002F0438043C0435043D043000200442043E0447043A043E043900200441002004370430043F044F0442043E043900200028003B0029002E")

    raw = Application.InputBox( _
        Prompt:=promptText, _
        Title:=SH_U("0421043F04380441043E043A0020041D04210421"), _
        Default:=currentText, _
        Type:=2)
    If VarType(raw) = vbBoolean Then
        If raw = False Then Exit Sub
    End If

    normalized = SH_NssNormalizeList(CStr(raw))
    SH_SetMetaValue wb, SH_NssListKey(stationId), normalized
    selected = SH_NssSelected(wb, stationId)
    If Len(normalized) = 0 Then
        SH_SetMetaValue wb, SH_NssSelectedKey(stationId), ""
        If SH_ReportStationId(wb, False) = stationId Then
            SH_EnsurePrepSheet(wb).Range(SH_NSS_CELL).ClearContents
        End If
    ElseIf Len(selected) = 0 Or Not SH_NssListContains(normalized, selected) Then
        selected = SH_NssNameAt(normalized, 1)
        SH_SetMetaValue wb, SH_NssSelectedKey(stationId), selected
    End If

    If SH_ReportStationId(wb, False) = stationId Then
        SH_ApplyNssForStation wb, stationId
        SH_EnsureStationReportContour wb
        SH_CalculateReportInputs wb
    End If

    MsgBox SH_U("0421043F04380441043E043A0020041D0421042100200441043E044504400430043D0451043D00200434043B044F0020") & _
        SH_ReportStationName(stationId), vbInformation, "Shift-Helper"
End Sub

Private Sub SH_SelectNss(ByVal stationId As Long, ByVal itemIndex As Long)
    Dim wb As Workbook, listText As String, selected As String, currentStation As Long
    Set wb = SH_JournalBook()
    currentStation = SH_ReportStationId(wb, True)
    If currentStation <> stationId Then Err.Raise vbObjectError + 761, , "NSS station mismatch."

    listText = SH_NssListText(wb, stationId)
    selected = SH_NssNameAt(listText, itemIndex)
    If Len(selected) = 0 Then Err.Raise vbObjectError + 762, , "NSS selection is empty."

    SH_SetMetaValue wb, SH_NssSelectedKey(stationId), selected
    SH_ApplyNssForStation wb, stationId
    SH_EnsureStationReportContour wb
    SH_CalculateReportInputs wb
    MsgBox SH_U("041D0421042100200432044B043104400430043D003A0020") & selected, _
        vbInformation, "Shift-Helper"
End Sub

Private Function SH_NssListText(ByVal wb As Workbook, ByVal stationId As Long) As String
    SH_NssListText = SH_NssNormalizeList(CStr(SH_MetaValue(wb, SH_NssListKey(stationId), "")))
End Function

Private Function SH_NssListKey(ByVal stationId As Long) As String
    SH_NssListKey = SH_NSS_LIST_PREFIX & CStr(stationId)
End Function

Private Function SH_NssSelectedKey(ByVal stationId As Long) As String
    SH_NssSelectedKey = SH_NSS_SELECTED_PREFIX & CStr(stationId)
End Function

Private Function SH_NssNormalizeList(ByVal rawText As String) As String
    Dim normalized As String, items As Variant, item As Variant, nameText As String, result As String
    normalized = Replace(rawText, vbCr, ";")
    normalized = Replace(normalized, vbLf, ";")
    items = Split(normalized, ";")
    For Each item In items
        nameText = Trim$(CStr(item))
        If Len(nameText) > 0 Then
            If Not SH_NssListContains(result, nameText) Then
                If Len(result) > 0 Then result = result & "; "
                result = result & nameText
            End If
        End If
    Next item
    SH_NssNormalizeList = result
End Function

Private Function SH_NssListContains(ByVal listText As String, ByVal nameText As String) As Boolean
    Dim i As Long
    For i = 1 To SH_NssCount(listText)
        If StrComp(SH_NssNameAt(listText, i), nameText, vbTextCompare) = 0 Then
            SH_NssListContains = True
            Exit Function
        End If
    Next i
End Function

Private Function SH_NssCount(ByVal listText As String) As Long
    Dim items As Variant
    If Len(Trim$(listText)) = 0 Then Exit Function
    items = Split(listText, ";")
    SH_NssCount = UBound(items) - LBound(items) + 1
End Function

Private Function SH_NssNameAt(ByVal listText As String, ByVal itemIndex As Long) As String
    Dim items As Variant, zeroIndex As Long
    If Len(Trim$(listText)) = 0 Then Exit Function
    items = Split(listText, ";")
    zeroIndex = itemIndex - 1
    If zeroIndex < LBound(items) Or zeroIndex > UBound(items) Then Exit Function
    SH_NssNameAt = Trim$(CStr(items(zeroIndex)))
End Function
