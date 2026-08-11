Attribute VB_Name = "modShiftHelperReportSaveSettings"
Option Explicit

Private Const SH_REPORT_FOLDER_KEY As String = "report.output.folder"
Private Const SH_REPORT_FILENAME_KEY As String = "report.output.filename_template"
Private Const SH_REPORT_DEFAULT_TEMPLATE As String = "Shift-Helper-Report-{date_iso}.xlsx"

Public Function SH_ReportSaveFolder(ByVal wb As Workbook) As String
    Dim configured As String
    configured = Trim$(CStr(SH_MetaValue(wb, SH_REPORT_FOLDER_KEY, "")))

    If Len(configured) > 0 Then
        If Not SH_ReportFolderExists(configured) Then
            Err.Raise vbObjectError + 750, , _
                SH_U("041D0430044104420440043E0435043D043D0430044F0020043F0430043F043A043000200441043E044504400430043D0435043D0438044F002004400430043F043E0440044204300020043D043500200441044304490435044104420432044304350442003A") & _
                " " & configured
        End If
        SH_ReportSaveFolder = configured
        Exit Function
    End If

    If Len(wb.Path) > 0 Then
        SH_ReportSaveFolder = wb.Path
    Else
        SH_ReportSaveFolder = Application.DefaultFilePath
    End If
End Function

Public Function SH_ReportFilenameTemplate(ByVal wb As Workbook) As String
    Dim configured As String
    configured = Trim$(CStr(SH_MetaValue(wb, SH_REPORT_FILENAME_KEY, "")))
    If Len(configured) = 0 Then configured = SH_REPORT_DEFAULT_TEMPLATE
    SH_ReportFilenameTemplate = configured
End Function

Public Function SH_ReportSuggestedFilename(ByVal wb As Workbook, ByVal reportDate As Date) As String
    SH_ReportSuggestedFilename = SH_ReportFilenameFromTemplate( _
        SH_ReportFilenameTemplate(wb), reportDate)
End Function

Public Function SH_ReportSuggestedPath(ByVal wb As Workbook, ByVal reportDate As Date) As String
    Dim folderPath As String
    folderPath = SH_ReportSaveFolder(wb)
    SH_ReportSuggestedPath = SH_ReportJoinPath(folderPath, _
        SH_ReportSuggestedFilename(wb, reportDate))
End Function

Public Function SH_ReportSaveSettingsMenuXml() As String
    On Error GoTo Fallback
    Dim wb As Workbook, folderPath As String, filenameTemplate As String

    Set wb = SH_JournalBook()
    folderPath = SH_ReportSaveFolder(wb)
    filenameTemplate = SH_ReportFilenameTemplate(wb)

    SH_ReportSaveSettingsMenuXml = _
        "<menu xmlns=""http://schemas.microsoft.com/office/2009/07/customui"">" & _
        "<button id=""reportSaveFolderInfo"" label=""" & _
            SH_XmlEscape(SH_U("041F0430043F043A0430003A0020") & SH_MenuText(folderPath)) & _
            """ enabled=""false""/>" & _
        "<button id=""reportSaveFolderEdit"" label=""" & _
            SH_U("0412044B0431044004300442044C0020043F0430043F043A0443002E002E002E") & _
            """ tag=""folder"" onAction=""SH_RibbonReportSaveSetting""/>" & _
        "<button id=""reportSaveNameInfo"" label=""" & _
            SH_XmlEscape(SH_U("0418043C044F003A0020") & SH_MenuText(filenameTemplate)) & _
            """ enabled=""false""/>" & _
        "<button id=""reportSaveNameEdit"" label=""" & _
            SH_U("04180437043C0435043D04380442044C0020044804300431043B043E043D00200438043C0435043D0438002E002E002E") & _
            """ tag=""name"" onAction=""SH_RibbonReportSaveSetting""/>" & _
        "<menuSeparator id=""reportSaveSeparator""/>" & _
        "<button id=""reportSaveReset"" label=""" & _
            SH_U("042104310440043E044104380442044C0020043D0430044104420440043E0439043A0438") & _
            """ tag=""reset"" onAction=""SH_RibbonReportSaveSetting""/>" & _
        "</menu>"
    Exit Function

Fallback:
    SH_ReportSaveSettingsMenuXml = _
        "<menu xmlns=""http://schemas.microsoft.com/office/2009/07/customui"">" & _
        "<button id=""reportSaveFolderEdit"" label=""" & _
            SH_U("0412044B0431044004300442044C0020043F0430043F043A0443002E002E002E") & _
            """ tag=""folder"" onAction=""SH_RibbonReportSaveSetting""/>" & _
        "<button id=""reportSaveNameEdit"" label=""" & _
            SH_U("04180437043C0435043D04380442044C0020044804300431043B043E043D00200438043C0435043D0438002E002E002E") & _
            """ tag=""name"" onAction=""SH_RibbonReportSaveSetting""/>" & _
        "</menu>"
End Function

Public Sub SH_EditReportSaveSetting(ByVal settingName As String)
    Select Case LCase$(Trim$(settingName))
        Case "folder"
            SH_EditReportSaveFolder
        Case "name"
            SH_EditReportFilename
        Case "reset"
            SH_ResetReportSaveSettings
        Case Else
            Err.Raise 5, , "Unknown report save setting."
    End Select
End Sub

Private Sub SH_EditReportSaveFolder()
    On Error GoTo Failed
    Dim wb As Workbook, picker As FileDialog
    Dim currentPath As String, selectedPath As String

    Set wb = SH_JournalBook()
    currentPath = SH_ReportSaveFolder(wb)
    Set picker = Application.FileDialog(msoFileDialogFolderPicker)
    With picker
        .Title = SH_U("0412044B0431043504400438044204350020043F0430043F043A044300200441043E044504400430043D0435043D0438044F00200443044204400435043D043D04350433043E002004400430043F043E044004420430")
        .AllowMultiSelect = False
        If Len(currentPath) > 0 Then .InitialFileName = currentPath
        If .Show <> -1 Then Exit Sub
        selectedPath = CStr(.SelectedItems(1))
    End With

    If Not SH_ReportFolderExists(selectedPath) Then
        Err.Raise vbObjectError + 751, , "Selected report output folder does not exist."
    End If

    SH_SetMetaValue wb, SH_REPORT_FOLDER_KEY, selectedPath
    MsgBox SH_U("041F0430043F043A043000200441043E044504400430043D0435043D0438044F002004400430043F043E04400442043000200441043E044504400430043D0435043D0430003A") & _
        vbCrLf & selectedPath, vbInformation, "Shift-Helper"
    Exit Sub

Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Private Sub SH_EditReportFilename()
    On Error GoTo Failed
    Dim wb As Workbook, raw As Variant, templateText As String, preview As String
    Dim reportDate As Date, promptText As String

    Set wb = SH_JournalBook()
    reportDate = SH_ReportDate(wb)
    promptText = SH_U("04120432043504340438044204350020044804300431043B043E043D00200438043C0435043D04380020044404300439043B0430002E") & _
        vbCrLf & vbCrLf & _
        SH_U("0414043E044104420443043F043D044B04350020043F043E0434044104420430043D043E0432043A0438003A") & vbCrLf & _
        SH_U("007B0064006100740065007D0020201400200434043004420430002004400430043F043E0440044204300020043200200444043E0440043C043004420435002000640064002E006D006D002E0079007900790079") & vbCrLf & _
        SH_U("007B0064006100740065005F00690073006F007D0020201400200434043004420430002004400430043F043E0440044204300020043200200444043E0440043C04300442043500200079007900790079002D006D006D002D00640064") & vbCrLf & _
        SH_U("0420043004410448043804400435043D043804350020002E0078006C007300780020043C043E0436043D043E0020043D043500200443043A04300437044B043204300442044C002E")

    raw = Application.InputBox( _
        Prompt:=promptText, _
        Title:=SH_U("0421043E044504400430043D0435043D04380435002004400430043F043E044004420430"), _
        Default:=SH_ReportFilenameTemplate(wb), _
        Type:=2)
    If VarType(raw) = vbBoolean Then
        If raw = False Then Exit Sub
    End If

    templateText = Trim$(CStr(raw))
    If Len(templateText) = 0 Then
        Err.Raise vbObjectError + 752, , _
            SH_U("042804300431043B043E043D00200438043C0435043D04380020044404300439043B04300020043D04350020043C043E04360435044200200431044B0442044C0020043F044304410442044B043C002E")
    End If

    preview = SH_ReportFilenameFromTemplate(templateText, reportDate)
    SH_SetMetaValue wb, SH_REPORT_FILENAME_KEY, templateText
    MsgBox SH_U("041D0430044104420440043E0439043A043000200438043C0435043D04380020044404300439043B043000200441043E044504400430043D0435043D0430002E") & _
        vbCrLf & preview, vbInformation, "Shift-Helper"
    Exit Sub

Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Private Sub SH_ResetReportSaveSettings()
    On Error GoTo Failed
    Dim wb As Workbook
    Set wb = SH_JournalBook()
    SH_SetMetaValue wb, SH_REPORT_FOLDER_KEY, ""
    SH_SetMetaValue wb, SH_REPORT_FILENAME_KEY, ""
    MsgBox SH_U("041D0430044104420440043E0439043A043800200441043E044504400430043D0435043D0438044F002004400430043F043E0440044204300020044104310440043E04480435043D044B002E"), _
        vbInformation, "Shift-Helper"
    Exit Sub

Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Private Function SH_ReportFilenameFromTemplate(ByVal templateText As String, _
    ByVal reportDate As Date) As String
    Dim result As String
    result = Trim$(templateText)
    result = Replace(result, "{date_iso}", Format$(reportDate, "yyyy-mm-dd"), _
        1, -1, vbTextCompare)
    result = Replace(result, "{date}", Format$(reportDate, "dd.mm.yyyy"), _
        1, -1, vbTextCompare)
    result = SH_ReportSanitizeFilename(result)
    If Len(result) = 0 Then result = "Shift-Helper-Report-" & _
        Format$(reportDate, "yyyy-mm-dd")
    If LCase$(Right$(result, 5)) <> ".xlsx" Then result = result & ".xlsx"
    SH_ReportFilenameFromTemplate = result
End Function

Private Function SH_ReportSanitizeFilename(ByVal value As String) As String
    Dim invalid As Variant, item As Variant, result As String
    result = Trim$(value)
    invalid = Array("\", "/", ":", "*", "?", Chr$(34), "<", ">", "|")
    For Each item In invalid
        result = Replace(result, CStr(item), "_")
    Next item
    Do While Len(result) > 0 And (Right$(result, 1) = "." Or Right$(result, 1) = " ")
        result = Left$(result, Len(result) - 1)
    Loop
    SH_ReportSanitizeFilename = result
End Function

Private Function SH_ReportJoinPath(ByVal folderPath As String, ByVal fileName As String) As String
    Dim separator As String
    separator = Application.PathSeparator
    If Right$(folderPath, 1) = "\" Or Right$(folderPath, 1) = "/" Then
        SH_ReportJoinPath = folderPath & fileName
    Else
        SH_ReportJoinPath = folderPath & separator & fileName
    End If
End Function

Private Function SH_ReportFolderExists(ByVal folderPath As String) As Boolean
    On Error GoTo Missing
    Dim attributes As Long
    attributes = GetAttr(folderPath)
    SH_ReportFolderExists = ((attributes And vbDirectory) = vbDirectory)
    Exit Function
Missing:
    SH_ReportFolderExists = False
End Function
