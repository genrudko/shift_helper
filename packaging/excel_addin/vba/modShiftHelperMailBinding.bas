Attribute VB_Name = "modShiftHelperMailBinding"
Option Explicit

Public Sub SH_RepairMailButtons()
    On Error GoTo Failed
    Dim wb As Workbook, repaired As Long
    Set wb = SH_JournalBook()
    repaired = SH_RepairMailButtonBindings(wb, True)
    Exit Sub
Failed:
    MsgBox "Could not repair mailing buttons [#" & CStr(Err.Number) & "]: " & Err.Description, _
        vbExclamation, "Shift-Helper"
End Sub

Public Function SH_RepairMailButtonBindings(ByVal wb As Workbook, _
    Optional ByVal showResult As Boolean = False) As Long
    On Error GoTo Failed
    Dim ws As Worksheet, shp As Shape
    Dim currentAction As String, targetMacro As String, expectedAction As String
    Dim repaired As Long

    If wb Is Nothing Then Exit Function
    If wb Is ThisWorkbook Then Exit Function
    If Not SH_HasSheet(wb, SH_JournalSheetName()) Then Exit Function
    If Not SH_MailWorkbookHasButtons(wb) Then Exit Function

    For Each ws In wb.Worksheets
        For Each shp In ws.Shapes
            currentAction = SH_MailShapeAction(shp)
            targetMacro = SH_MailTargetMacro(ws.Name, shp, currentAction)
            If Len(targetMacro) > 0 Then
                expectedAction = "'" & ThisWorkbook.Name & "'!" & targetMacro
                If StrComp(currentAction, expectedAction, vbBinaryCompare) <> 0 Then
                    On Error Resume Next
                    shp.OnAction = expectedAction
                    If Err.Number = 0 Then repaired = repaired + 1
                    Err.Clear
                    On Error GoTo Failed
                End If
            End If
        Next shp
    Next ws

    SH_RepairMailButtonBindings = repaired
    If showResult Then
        MsgBox "Mailing button bindings checked. Updated: " & CStr(repaired) & ".", _
            vbInformation, "Shift-Helper"
    End If
    Exit Function

Failed:
    If showResult Then
        MsgBox "Could not repair mailing buttons [#" & CStr(Err.Number) & "]: " & Err.Description, _
            vbExclamation, "Shift-Helper"
    End If
End Function

Private Function SH_MailWorkbookHasButtons(ByVal wb As Workbook) As Boolean
    SH_MailWorkbookHasButtons = _
        SH_HasSheet(wb, SH_U("0420043004410441044B043B043A0430")) Or _
        SH_HasSheet(wb, SH_U("04200430043F043E044004420020044304420440043E")) Or _
        SH_HasSheet(wb, SH_U("0421043F04380441043E043A00200440043004410441044B043B043A0438002021160031")) Or _
        SH_HasSheet(wb, SH_U("0421043F04380441043E043A00200440043004410441044B043B043A0438002021160032")) Or _
        SH_HasSheet(wb, SH_U("0421043F04380441043E043A00200440043004410441044B043B043A0438002021160033")) Or _
        SH_HasSheet(wb, SH_U("0417043004400443043104350436043D043504440442044C"))
End Function

Private Function SH_MailShapeAction(ByVal shp As Shape) As String
    On Error Resume Next
    SH_MailShapeAction = CStr(shp.OnAction)
    Err.Clear
    On Error GoTo 0
End Function

Private Function SH_MailShapeText(ByVal shp As Shape) As String
    On Error Resume Next
    SH_MailShapeText = CStr(shp.TextFrame2.TextRange.Text)
    If Err.Number <> 0 Or Len(SH_MailShapeText) = 0 Then
        Err.Clear
        SH_MailShapeText = CStr(shp.TextFrame.Characters.Text)
    End If
    Err.Clear
    On Error GoTo 0
End Function

Private Function SH_MailTargetMacro(ByVal sheetName As String, ByVal shp As Shape, _
    ByVal currentAction As String) As String
    Dim actionText As String, captionText As String, listNumber As Long
    actionText = LCase$(Trim$(currentAction))
    captionText = LCase$(Trim$(SH_MailShapeText(shp)))

    If InStr(1, actionText, "sh_mail_zarubezhneft_list1", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_Zarubezhneft_List1": Exit Function
    If InStr(1, actionText, "sh_mail_zarubezhneft_list2", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_Zarubezhneft_List2": Exit Function
    If InStr(1, actionText, "sh_mail_zarubezhneft_list3", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_Zarubezhneft_List3": Exit Function
    If InStr(1, actionText, "sh_mail_zarubezhneft_morning", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_Zarubezhneft_Morning": Exit Function
    If InStr(1, actionText, "sh_mail_zarubezhneft", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_Zarubezhneft": Exit Function
    If InStr(1, actionText, "sh_mail_list1", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_List1": Exit Function
    If InStr(1, actionText, "sh_mail_list2", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_List2": Exit Function
    If InStr(1, actionText, "sh_mail_list3", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_List3": Exit Function
    If InStr(1, actionText, "sh_mail_morning", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_Morning": Exit Function

    If InStr(1, actionText, "createmail_list1", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_List1": Exit Function
    If InStr(1, actionText, "createmail_list2", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_List2": Exit Function
    If InStr(1, actionText, "createmail_list3", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_List3": Exit Function
    If InStr(1, actionText, "send_mail", vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_Morning": Exit Function

    listNumber = SH_MailListNumber(sheetName)
    If InStr(1, actionText, LCase$(SH_U("04200430043F043E044004420437043004400443043104350436043D043504440442044C")), vbTextCompare) > 0 Then
        If StrComp(sheetName, SH_U("04200430043F043E044004420020044304420440043E"), vbTextCompare) = 0 Then
            SH_MailTargetMacro = "SH_Mail_Zarubezhneft_Morning"
        ElseIf listNumber >= 1 And listNumber <= 3 Then
            SH_MailTargetMacro = "SH_Mail_Zarubezhneft_List" & CStr(listNumber)
        End If
        Exit Function
    End If
    If InStr(1, actionText, LCase$(SH_U("04200430043F043E04400442005F04400443043A043E0432043E04340441044204320443")), vbTextCompare) > 0 Then
        If StrComp(sheetName, SH_U("04200430043F043E044004420020044304420440043E"), vbTextCompare) = 0 Then
            SH_MailTargetMacro = "SH_Mail_Morning"
        ElseIf listNumber >= 1 And listNumber <= 3 Then
            SH_MailTargetMacro = "SH_Mail_List" & CStr(listNumber)
        End If
        Exit Function
    End If
    If InStr(1, actionText, LCase$(SH_U("0417043004400443043104350436043D043504440442044C")), vbTextCompare) > 0 Then
        SH_MailTargetMacro = "SH_Mail_Zarubezhneft"
        Exit Function
    End If

    If listNumber >= 1 And listNumber <= 3 Then
        If InStr(1, captionText, LCase$(SH_U("0421043E0437043404300442044C0020043F04380441044C043C043E00200437043004400443043104350436043D043504440442044C")), vbTextCompare) > 0 Then
            SH_MailTargetMacro = "SH_Mail_Zarubezhneft_List" & CStr(listNumber)
            Exit Function
        End If
        If InStr(1, captionText, LCase$(SH_U("0421043E0437043404300442044C0020043F04380441044C043C043E002004400443043A043E0432043E04340441044204320443")), vbTextCompare) > 0 Then
            SH_MailTargetMacro = "SH_Mail_List" & CStr(listNumber)
            Exit Function
        End If
    End If

    If StrComp(sheetName, SH_U("0420043004410441044B043B043A0430"), vbTextCompare) = 0 Then
        If InStr(1, captionText, LCase$(SH_U("0421043F04380441043E043A00200440043004410441044B043B043A0438002021160031")), vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_List1": Exit Function
        If InStr(1, captionText, LCase$(SH_U("0421043F04380441043E043A00200440043004410441044B043B043A0438002021160032")), vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_List2": Exit Function
        If InStr(1, captionText, LCase$(SH_U("0421043F04380441043E043A00200440043004410441044B043B043A0438002021160033")), vbTextCompare) > 0 Then SH_MailTargetMacro = "SH_Mail_List3": Exit Function
    End If

    If StrComp(sheetName, SH_U("04200430043F043E044004420020044304420440043E"), vbTextCompare) = 0 Then
        If InStr(1, captionText, LCase$(SH_U("0421043E0437043404300442044C0020043F04380441044C043C043E00200437043004400443043104350436043D043504440442044C")), vbTextCompare) > 0 Then
            SH_MailTargetMacro = "SH_Mail_Zarubezhneft_Morning": Exit Function
        End If
        If InStr(1, captionText, LCase$(SH_U("0421043E0437043404300442044C0020043F04380441044C043C043E002004400443043A043E0432043E04340441044204320443")), vbTextCompare) > 0 Then
            SH_MailTargetMacro = "SH_Mail_Morning": Exit Function
        End If
    End If

    If StrComp(sheetName, SH_U("0417043004400443043104350436043D043504440442044C"), vbTextCompare) = 0 Then
        If InStr(1, captionText, LCase$(SH_U("0421043E0437043404300442044C0020043F04380441044C043C043E00200437043004400443043104350436043D043504440442044C")), vbTextCompare) > 0 Then
            SH_MailTargetMacro = "SH_Mail_Zarubezhneft"
        End If
    End If
End Function

Private Function SH_MailListNumber(ByVal sheetName As String) As Long
    Dim prefix As String, suffix As String
    prefix = SH_U("0421043F04380441043E043A00200440043004410441044B043B043A043800202116")
    If Len(sheetName) <= Len(prefix) Then Exit Function
    If StrComp(Left$(sheetName, Len(prefix)), prefix, vbTextCompare) <> 0 Then Exit Function
    suffix = Trim$(Mid$(sheetName, Len(prefix) + 1))
    If IsNumeric(suffix) Then SH_MailListNumber = CLng(suffix)
End Function
