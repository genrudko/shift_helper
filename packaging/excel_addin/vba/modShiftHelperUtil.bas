Attribute VB_Name = "modShiftHelperUtil"
Option Explicit

#If VBA7 Then
Private Declare PtrSafe Function OpenClipboard Lib "user32" (ByVal hwnd As LongPtr) As Long
Private Declare PtrSafe Function CloseClipboard Lib "user32" () As Long
Private Declare PtrSafe Function EmptyClipboard Lib "user32" () As Long
Private Declare PtrSafe Function SetClipboardData Lib "user32" (ByVal wFormat As Long, ByVal hMem As LongPtr) As LongPtr
Private Declare PtrSafe Function GlobalAlloc Lib "kernel32" (ByVal wFlags As Long, ByVal dwBytes As LongPtr) As LongPtr
Private Declare PtrSafe Function GlobalLock Lib "kernel32" (ByVal hMem As LongPtr) As LongPtr
Private Declare PtrSafe Function GlobalUnlock Lib "kernel32" (ByVal hMem As LongPtr) As Long
Private Declare PtrSafe Sub CopyMemory Lib "kernel32" Alias "RtlMoveMemory" (ByVal Destination As LongPtr, ByVal Source As LongPtr, ByVal Length As LongPtr)
#Else
Private Declare Function OpenClipboard Lib "user32" (ByVal hwnd As Long) As Long
Private Declare Function CloseClipboard Lib "user32" () As Long
Private Declare Function EmptyClipboard Lib "user32" () As Long
Private Declare Function SetClipboardData Lib "user32" (ByVal wFormat As Long, ByVal hMem As Long) As Long
Private Declare Function GlobalAlloc Lib "kernel32" (ByVal wFlags As Long, ByVal dwBytes As Long) As Long
Private Declare Function GlobalLock Lib "kernel32" (ByVal hMem As Long) As Long
Private Declare Function GlobalUnlock Lib "kernel32" (ByVal hMem As Long) As Long
Private Declare Sub CopyMemory Lib "kernel32" Alias "RtlMoveMemory" (ByVal Destination As Long, ByVal Source As Long, ByVal Length As Long)
#End If

Private Const CF_UNICODETEXT As Long = 13
Private Const GMEM_MOVEABLE As Long = &H2&
Private Const GMEM_ZEROINIT As Long = &H40&

Public Function SH_U(ByVal hexText As String) As String
    Dim i As Long, result As String
    If Len(hexText) Mod 4 <> 0 Then Err.Raise 5, , "invalid Shift-Helper UTF-16 literal"
    For i = 1 To Len(hexText) Step 4
        result = result & ChrW$(CLng("&H" & Mid$(hexText, i, 4)))
    Next i
    SH_U = result
End Function

Public Function SH_T(ByVal key As String) As String
    Select Case key
        Case "ERR_JOURNAL": SH_T = SH_U("0410043A044204380432043D0430044F0020043A043D0438043304300020043D04350020044F0432043B044F043504420441044F0020043604430440043D0430043B043E043C002000530068006900660074002D00480065006C007000650072002E")
        Case "ERR_SELECTION_BOOK": SH_T = SH_U("0412044B043104400430043D043D044B04390020043404380430043F04300437043E043D0020043D04300445043E0434043804420441044F0020043D043500200432002004420435043A044304490435043C0020043604430440043D0430043B0435002E")
        Case "OK_PREP": SH_T = SH_U("041A043E043D044204430440002004400430043F043E0440044204300020043F0440043E0432043504400435043D002004380020043F043E04340433043E0442043E0432043B0435043D002E")
        Case "ERR_PREP": SH_T = SH_U("041D04350020044304340430043B043E0441044C0020043F043E04340433043E0442043E043204380442044C0020043A043E043D044204430440002004400430043F043E044004420430003A0020")
        Case "ERR_REPORT": SH_T = SH_U("041D04350020044304340430043B043E0441044C002004410444043E0440043C04380440043E043204300442044C002004400430043F043E04400442003A0020")
        Case "OK_REPORT": SH_T = SH_U("0423044204400435043D043D04380439002004400430043F043E04400442002004410444043E0440043C04380440043E04320430043D003A0020")
        Case "ERR_SELECTION": SH_T = SH_U("0412044B0431043504400438044204350020044F044704350439043A04380020044004300431043E044704350433043E0020043604430440043D0430043B0430002E")
        Case "OK_COPY": SH_T = SH_U("04220435043A0441044200200441043A043E043F04380440043E04320430043D002004320020043104430444043504400020043E0431043C0435043D0430002000570069006E0064006F00770073002E")
        Case "ERR_COPY": SH_T = SH_U("041D04350020044304340430043B043E0441044C00200441043A043E043F04380440043E043204300442044C002004420435043A04410442002004320020043104430444043504400020043E0431043C0435043D0430002E")
        Case "ROW_HEIGHT_PROMPT": SH_T = SH_U("0423043A0430043604380442043500200432044B0441043E0442044300200432044B043104400430043D043D044B04450020044104420440043E043A00200028003520130032003000300020043F0443043D043A0442043E04320029003A")
        Case "ROW_HEIGHT_TITLE": SH_T = SH_U("00530068006900660074002D00480065006C0070006500720020201400200432044B0441043E044204300020044104420440043E043A")
        Case "OUTLOOK_TITLE": SH_T = SH_U("00530068006900660074002D00480065006C007000650072002020140020043D0430044104420440043E0439043A04380020004F00750074006C006F006F006B")
        Case "OUTLOOK_SAVED": SH_T = SH_U("041D0430044104420440043E0439043A04380020004F00750074006C006F006F006B00200441043E044504400430043D0435043D044B002E")
        Case "OUTLOOK_NOT_FOUND": SH_T = SH_U("041F043E04340445043E0434044F0449043504350020043F04380441044C043C043E0020004F00750074006C006F006F006B0020043D04350020043D0430043904340435043D043E002E")
        Case "OUTLOOK_UNAVAILABLE": SH_T = SH_U("004F00750074006C006F006F006B0020043D04350434043E044104420443043F0435043D002E0020041C043E0436043D043E00200432044B0431044004300442044C0020044404300439043B002004330435043D04350440043004460438043800200432044004430447043D0443044E002E")
        Case "GEN_PICK": SH_T = SH_U("0412044B0431043504400438044204350020044404300439043B002004330435043D043504400430044604380438")
        Case "GEN_OK": SH_T = SH_U("04130435043D04350440043004460438044F00200438043C043F043E0440044204380440043E04320430043D0430002E")
        Case "GEN_BAD": SH_T = SH_U("041D04350020044304340430043B043E0441044C00200438043C043F043E0440044204380440043E043204300442044C002004330435043D04350440043004460438044E003A0020")
        Case "CAL_TODAY": SH_T = SH_U("042104350433043E0434043D044F")
        Case "CAL_WEEK": SH_T = SH_U("041D043504340435043B044F0020")
        Case "SHIFT_DAY": SH_T = SH_U("0414")
        Case "SHIFT_NIGHT": SH_T = SH_U("041D")
        Case "SHIFT_NOT_FOUND": SH_T = SH_U("041D04350020044304340430043B043E0441044C0020043D0430043904420438002004420435043A0443044904380439002004340435043D044C002F0441043C0435043D04430020043D0430002004330440043004440438043A04350020043E0441043C043E04420440043E0432002E")
        Case "ROTOR_OK": SH_T = SH_U("041E043304400430043D043804470435043D0438044F0020043F043E0020043E0431043E0440043E04420430043C002F043C043E0449043D043E04410442043800200430043A044204430430043B0438043704380440043E04320430043D044B002E")
        Case "ROTOR_BAD": SH_T = SH_U("041D04350020044304340430043B043E0441044C00200430043A044204430430043B0438043704380440043E043204300442044C0020043E043304400430043D043804470435043D0438044F003A0020")
        Case "NO_TEMPLATE_PICK": SH_T = SH_U("0412043D04350448043D043804390020044404300439043B0020044804300431043B043E043D0430002004400430043F043E0440044204300020043D0435002004420440043504310443043504420441044F002E")
        Case "INVALID_OUTLOOK_FILE": SH_T = SH_U("042404300439043B002004330435043D0435044004300446043804380020043D043500200441043E043E04420432043504420441044204320443043504420020043E04360438043404300435043C043E043900200441044204400443043A0442044304400435002E")
        Case "SHEET_MISSING": SH_T = SH_U("041E04420441044304420441044204320443043504420020043E0431044F0437043004420435043B044C043D044B04390020043B043804410442003A0020")
        Case "SAVE_REPORT": SH_T = SH_U("0421043E044504400430043D04380442044C0020043F043E043B043D044B043900200443044204400435043D043D04380439002004400430043F043E04400442")
        Case "WORKING": SH_T = SH_U("042004300431043E04420430")
        Case "STOPPED": SH_T = SH_U("041E044104420430043D043E0432")
        Case "ACCIDENT": SH_T = SH_U("04100432043004400438044F")
        Case "REPAIR": SH_T = SH_U("04200435043C043E043D0442")
        Case "LIMIT_REASON": SH_T = SH_U("041E043304400430043D043804470435043D043804350020043F043E0020043E0431043E0440043E04420430043C0020")
        Case Else: SH_T = key
    End Select
End Function

Public Function SH_NormalizeSpaces(ByVal value As Variant) As String
    Dim s As String
    s = CStr(value)
    s = Replace(s, vbCr, " ")
    s = Replace(s, vbLf, " ")
    s = Replace(s, vbTab, " ")
    s = Replace(s, ChrW$(160), " ")
    Do While InStr(1, s, "  ", vbBinaryCompare) > 0
        s = Replace(s, "  ", " ")
    Loop
    SH_NormalizeSpaces = Trim$(s)
End Function

Public Function SH_XmlEscape(ByVal value As String) As String
    Dim s As String
    s = Replace(value, "&", "&amp;")
    s = Replace(s, "<", "&lt;")
    s = Replace(s, ">", "&gt;")
    s = Replace(s, Chr$(34), "&quot;")
    SH_XmlEscape = s
End Function

Public Function SH_MenuText(ByVal value As Variant) As String
    Dim s As String
    s = SH_NormalizeSpaces(value)
    If Len(s) = 0 Then s = "-"
    If Len(s) > 52 Then s = Left$(s, 49) & "..."
    SH_MenuText = s
End Function

Public Function SH_JournalBook() As Workbook
    Dim wb As Workbook
    Set wb = Application.ActiveWorkbook
    If wb Is Nothing Then Err.Raise vbObjectError + 510, , SH_T("ERR_JOURNAL")
    If wb Is ThisWorkbook Then Err.Raise vbObjectError + 511, , SH_T("ERR_JOURNAL")
    If Not SH_HasSheet(wb, SH_JournalSheetName()) Then Err.Raise vbObjectError + 512, , SH_T("ERR_JOURNAL")
    Set SH_JournalBook = wb
End Function

Public Function SH_HasSheet(ByVal wb As Workbook, ByVal sheetName As String) As Boolean
    Dim ws As Worksheet
    On Error Resume Next
    Set ws = wb.Worksheets(sheetName)
    SH_HasSheet = Not ws Is Nothing
    On Error GoTo 0
End Function

Public Function SH_RequireSheet(ByVal wb As Workbook, ByVal sheetName As String) As Worksheet
    If Not SH_HasSheet(wb, sheetName) Then Err.Raise vbObjectError + 514, , SH_T("SHEET_MISSING") & sheetName
    Set SH_RequireSheet = wb.Worksheets(sheetName)
End Function

Public Function SH_EnsurePrepSheet(ByVal wb As Workbook) As Worksheet
    Dim ws As Worksheet, previousSheet As Object
    If SH_HasSheet(wb, SH_PrepSheetName()) Then
        Set SH_EnsurePrepSheet = wb.Worksheets(SH_PrepSheetName())
        Exit Function
    End If
    If wb.ProtectStructure Then Err.Raise vbObjectError + 515, , SH_T("SHEET_MISSING") & SH_PrepSheetName()
    If wb Is Application.ActiveWorkbook Then Set previousSheet = Application.ActiveSheet
    Set ws = wb.Worksheets.Add(After:=wb.Worksheets(wb.Worksheets.Count))
    ws.Name = SH_PrepSheetName()
    SH_InitializePrepSheet ws
    If Not previousSheet Is Nothing Then previousSheet.Activate
    Set SH_EnsurePrepSheet = ws
End Function

Private Sub SH_InitializePrepSheet(ByVal ws As Worksheet)
    Dim reportDate As Date
    reportDate = Date
    ws.Range("A1").Value = SH_U("00530048004900460054002D00480045004C005000450052002020140020041F041E04140413041E0422041E0412041A041000200423042204200415041D041D04150413041E002004200410041F041E042004220410")
    ws.Range("A1:F1").Merge
    ws.Range("A1").Font.Bold = True
    ws.Range("A3").Value = SH_U("0414043004420430002004400430043F043E044004420430")
    ws.Range("B3").Value = reportDate
    ws.Range("B3").NumberFormat = "dd.mm.yyyy"
    ws.Range("A4").Value = SH_U("041D043004470430043B043E0020043E0442044704510442043D043E0433043E0020043E043A043D0430")
    ws.Range("B4").Value = reportDate - 1 + TimeSerial(7, 0, 0)
    ws.Range("B4").NumberFormat = "dd.mm.yyyy hh:mm"
    ws.Range("A5").Value = SH_U("041E043A043E043D04470430043D043804350020043E0442044704510442043D043E0433043E0020043E043A043D0430")
    ws.Range("B5").Value = reportDate + TimeSerial(7, 0, 0)
    ws.Range("B5").NumberFormat = "dd.mm.yyyy hh:mm"
    ws.Range("A6").Value = SH_U("0421043C043504490435043D043804350020043204400435043C0435043D04380020043200200433043E0442043E0432043E043C002004400430043F043E044004420435002C00200447")
    ws.Range("B6").Value = -3
    ws.Range("E3").Value = SH_U("042004300431043E0447043804390020043604430440043D0430043B")
    ws.Range("F3").Value = SH_U("042D0442043E04420020044404300439043B")
    ws.Range("E4").Value = SH_U("04130435043D04350440043004460438044F")
    ws.Range("F4").Value = SH_U("004F00750074006C006F006F006B0020002F0020044004430447043D043E043900200432044B0431043E04400020044404300439043B0430")
    ws.Range("E5").Value = SH_U("04220435043A04430449043804390020044104420430044204430441")
    ws.Range("F5").Value = SH_U("0413041E0422041E04120020041A002004170410041F041E041B041D0415041D0418042E")
    ws.Range("M1").Value = SH_U("0421043B0443043604350431043D044B04390020043F043004400430043C043504420440")
    ws.Range("N1").Value = SH_U("0417043D043004470435043D04380435")
    ws.Columns("A").ColumnWidth = 42
    ws.Columns("B").ColumnWidth = 22
    ws.Columns("E").ColumnWidth = 22
    ws.Columns("F").ColumnWidth = 32
    ws.Columns(13).Hidden = True
    ws.Columns(14).Hidden = True
End Sub

Public Function SH_SelectionRange(ByVal wb As Workbook) As Range
    Dim selected As Range, selectionBook As Workbook
    If TypeName(Selection) <> "Range" Then Err.Raise vbObjectError + 516, , SH_T("ERR_SELECTION")
    Set selected = Selection
    Set selectionBook = selected.Worksheet.Parent
    If Not (selectionBook Is wb) Then Err.Raise vbObjectError + 517, , SH_T("ERR_SELECTION_BOOK")
    Set SH_SelectionRange = selected
End Function

Public Function SH_LastRow(ByVal ws As Worksheet, ByVal columnNumber As Long) As Long
    Dim rowNumber As Long
    rowNumber = ws.Cells(ws.Rows.Count, columnNumber).End(xlUp).Row
    If rowNumber < 1 Then rowNumber = 1
    SH_LastRow = rowNumber
End Function

Public Function SH_CellDateTime(ByVal ws As Worksheet, ByVal rowNumber As Long) As Variant
    Dim d As Variant, t As Variant
    d = ws.Cells(rowNumber, 2).Value2
    t = ws.Cells(rowNumber, 3).Value2
    If Not IsDate(d) And Not IsNumeric(d) Then SH_CellDateTime = Empty: Exit Function
    If Not IsDate(t) And Not IsNumeric(t) Then SH_CellDateTime = Empty: Exit Function
    SH_CellDateTime = Int(CDbl(d)) + (CDbl(t) - Int(CDbl(t)))
End Function

Public Function SH_CopyUnicodeText(ByVal text As String) As Boolean
#If VBA7 Then
    Dim hMem As LongPtr, pMem As LongPtr, result As LongPtr
#Else
    Dim hMem As Long, pMem As Long, result As Long
#End If
    Dim byteCount As Long
    byteCount = LenB(text) + 2
    If OpenClipboard(0) = 0 Then Exit Function
    On Error GoTo Failed
    EmptyClipboard
    hMem = GlobalAlloc(GMEM_MOVEABLE Or GMEM_ZEROINIT, byteCount)
    If hMem = 0 Then GoTo Failed
    pMem = GlobalLock(hMem)
    If pMem = 0 Then GoTo Failed
    CopyMemory pMem, StrPtr(text), LenB(text)
    GlobalUnlock hMem
    result = SetClipboardData(CF_UNICODETEXT, hMem)
    SH_CopyUnicodeText = (result <> 0)
Failed:
    CloseClipboard
End Function

Public Function SH_ReportDate(ByVal wb As Workbook) As Date
    Dim value As Variant, ws As Worksheet
    Set ws = SH_RequireSheet(wb, SH_PrepSheetName())
    value = ws.Range(SH_ReportDateCell()).Value
    If Not IsDate(value) And Not IsNumeric(value) Then Err.Raise vbObjectError + 513, , "Invalid report date in B3."
    SH_ReportDate = CDate(value)
End Function

Public Function SH_ReportOffset(ByVal wb As Workbook) As Double
    Dim value As Variant, ws As Worksheet
    Set ws = SH_RequireSheet(wb, SH_PrepSheetName())
    value = ws.Range(SH_ReportOffsetCell()).Value2
    If IsNumeric(value) Then SH_ReportOffset = CDbl(value) Else SH_ReportOffset = 0#
End Function

Public Function SH_SettingValue(ByVal wb As Workbook, ByVal labelText As String, ByVal fallback As String) As String
    Dim ws As Worksheet, lastRow As Long, r As Long, value As String
    If Not SH_HasSheet(wb, SH_PrepSheetName()) Then
        SH_SettingValue = GetSetting("Shift-Helper", "Outlook", labelText, fallback)
        Exit Function
    End If
    Set ws = wb.Worksheets(SH_PrepSheetName())
    lastRow = Application.Max(30, SH_LastRow(ws, 13))
    For r = 1 To lastRow
        If StrComp(CStr(ws.Cells(r, 13).Value2), labelText, vbTextCompare) = 0 Then
            value = CStr(ws.Cells(r, 14).Value2)
            If Len(value) > 0 Then SH_SettingValue = value Else SH_SettingValue = fallback
            Exit Function
        End If
    Next r
    SH_SettingValue = GetSetting("Shift-Helper", "Outlook", labelText, fallback)
End Function

Public Sub SH_SaveSettingValue(ByVal wb As Workbook, ByVal labelText As String, ByVal value As String)
    Dim ws As Worksheet, lastRow As Long, r As Long, targetRow As Long
    Set ws = SH_EnsurePrepSheet(wb)
    lastRow = Application.Max(30, SH_LastRow(ws, 13))
    For r = 1 To lastRow
        If StrComp(CStr(ws.Cells(r, 13).Value2), labelText, vbTextCompare) = 0 Then targetRow = r: Exit For
    Next r
    If targetRow = 0 Then targetRow = SH_LastRow(ws, 13) + 1: If targetRow < 2 Then targetRow = 2
    ws.Cells(targetRow, 13).Value = labelText
    ws.Cells(targetRow, 14).Value = value
    ws.Columns(13).Hidden = True
    ws.Columns(14).Hidden = True
    SaveSetting "Shift-Helper", "Outlook", labelText, value
End Sub

Public Function SH_QualifiedMacro(ByVal macroName As String) As String
    SH_QualifiedMacro = "'" & Replace(ThisWorkbook.Name, "'", "''") & "'!" & macroName
End Function
