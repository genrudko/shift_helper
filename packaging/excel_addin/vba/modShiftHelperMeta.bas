Attribute VB_Name = "modShiftHelperMeta"
Option Explicit

Public Function SH_MetaRow(ByVal wb As Workbook, ByVal labelText As String) As Long
    Dim ws As Worksheet, r As Long, lastRow As Long
    Set ws = wb.Worksheets(SH_PrepSheetName())
    lastRow = Application.Max(50, SH_LastRow(ws, 13))
    For r = 1 To lastRow
        If StrComp(CStr(ws.Cells(r, 13).Value2), labelText, vbTextCompare) = 0 Then
            SH_MetaRow = r
            Exit Function
        End If
    Next r
End Function

Public Function SH_MetaValue(ByVal wb As Workbook, ByVal labelText As String, ByVal fallback As Variant) As Variant
    Dim r As Long
    r = SH_MetaRow(wb, labelText)
    If r = 0 Then
        SH_MetaValue = fallback
    ElseIf Len(CStr(wb.Worksheets(SH_PrepSheetName()).Cells(r, 14).Value2)) = 0 Then
        SH_MetaValue = fallback
    Else
        SH_MetaValue = wb.Worksheets(SH_PrepSheetName()).Cells(r, 14).Value
    End If
End Function

Public Sub SH_SetMetaValue(ByVal wb As Workbook, ByVal labelText As String, ByVal value As Variant)
    Dim ws As Worksheet, r As Long
    Set ws = wb.Worksheets(SH_PrepSheetName())
    r = SH_MetaRow(wb, labelText)
    If r = 0 Then
        r = Application.Max(2, SH_LastRow(ws, 13) + 1)
        ws.Cells(r, 13).Value = labelText
    End If
    ws.Cells(r, 14).Value = value
    ws.Columns(13).Hidden = True
    ws.Columns(14).Hidden = True
End Sub

Public Function SH_Label(ByVal index As Long) As String
    Select Case index
        Case 1: SH_Label = SH_U("004F00750074006C006F006F006B003A0020043F043E04470442043E0432044B04390020044F04490438043A")
        Case 2: SH_Label = SH_U("004F00750074006C006F006F006B003A0020043F0430043F043A0430")
        Case 3: SH_Label = SH_U("004F00750074006C006F006F006B003A0020043C04300441043A043000200432043B043E04360435043D0438044F")
        Case 4: SH_Label = SH_U("004F00750074006C006F006F006B003A002004420435043C043000200441043E043404350440043604380442")
        Case 5: SH_Label = SH_U("004F00750074006C006F006F006B003A0020043E0442043F044004300432043804420435043B044C00200441043E043404350440043604380442")
        Case 6: SH_Label = SH_U("004F00750074006C006F006F006B003A00200433043B044304310438043D04300020043F043E04380441043A0430002C00200434043D04350439")
        Case 7: SH_Label = SH_U("004F00750074006C006F006F006B003A0020044004430447043D043E043900200432044B0431043E04400020043F044004380020043E044204410443044204410442043204380438")
        Case 8: SH_Label = SH_U("041F043E0441043B04350434043D043804390020044404300439043B002004330435043D043504400430044604380438")
        Case 9: SH_Label = SH_U("041F043E0441043B04350434043D044F044F0020043404300442043000200438043C043F043E044004420430002004330435043D043504400430044604380438")
        Case 10: SH_Label = SH_U("041F043E0441043B04350434043D044F044F00200432044B044004300431043E0442043A04300020043704300020044104430442043A0438")
        Case 11: SH_Label = SH_U("041F043E0441043B04350434043D0438043500200441043E04310441044204320435043D043D044B04350020043D044304360434044B0020043704300020044104430442043A0438")
    End Select
End Function

Public Function SH_DefaultSetting(ByVal index As Long) As String
    Select Case index
        Case 1: SH_DefaultSetting = SH_U("041D042104210020041A043E0447044304310435043504320441043A0430044F00200412042D0421")
        Case 2: SH_DefaultSetting = SH_U("04120445043E0434044F044904380435")
        Case 3: SH_DefaultSetting = SH_U("04130435043D04350440043004460438044F0020041A0412042D0421002004370430002004320447043504400430005F007B0064006100740065007D002E0078006C00730078")
        Case 4, 5: SH_DefaultSetting = ""
        Case 6: SH_DefaultSetting = "7"
        Case 7: SH_DefaultSetting = "1"
    End Select
End Function
