Attribute VB_Name = "modShiftHelperStation"
Option Explicit

Public Const SH_STATION_KOCH As Long = 1
Public Const SH_STATION_KUZ As Long = 2

Public Function SH_ReportStationId(ByVal wb As Workbook, Optional ByVal promptIfUnknown As Boolean = True) As Long
    Dim raw As Variant, detected As Long, selected As Variant
    raw = SH_MetaValue(wb, SH_StationMetaLabel(), "")
    If Not IsError(raw) And Not IsNull(raw) And Not IsEmpty(raw) Then
        If IsNumeric(raw) Then
            detected = CLng(raw)
            If detected = SH_STATION_KOCH Or detected = SH_STATION_KUZ Then
                SH_ReportStationId = detected
                Exit Function
            End If
        Else
            detected = SH_StationFromText(CStr(raw))
            If detected <> 0 Then
                SH_ReportStationId = detected
                Exit Function
            End If
        End If
    End If

    detected = SH_StationFromText(wb.Name)
    If detected = 0 And SH_HasSheet(wb, SH_InputSheetName(1)) Then
        detected = SH_StationFromText(SH_StationSafeText(wb.Worksheets(SH_InputSheetName(1)).Range("B1").Value2))
        If detected = 0 Then detected = SH_StationFromText(SH_StationSafeText(wb.Worksheets(SH_InputSheetName(1)).Range("H3").Value2))
    End If
    If detected = 0 And SH_HasSheet(wb, SH_InputSheetName(5)) Then
        detected = SH_StationFromText(SH_StationSafeText(wb.Worksheets(SH_InputSheetName(5)).Range("B1").Value2))
        If detected = 0 Then detected = SH_StationFromText(SH_StationSafeText(wb.Worksheets(SH_InputSheetName(5)).Range("B4").Value2))
    End If

    If detected = 0 And promptIfUnknown Then
        selected = Application.InputBox( _
            Prompt:=SH_U("0412044B0431043504400438044204350020044104420430043D04460438044E002004400430043F043E044004420430003A000A0031002020140020041A043E0447044304310435043504320441043A0430044F00200412042D0421000A0032002020140020041A04430437044C043C0438043D0441043A0430044F00200412042D0421"), _
            Title:="Shift-Helper", Type:=1)
        If VarType(selected) = vbBoolean Then
            If selected = False Then Err.Raise vbObjectError + 660, , "Report station selection was cancelled."
        End If
        If Not IsNumeric(selected) Then Err.Raise vbObjectError + 661, , "Report station must be 1 or 2."
        detected = CLng(selected)
        If detected <> SH_STATION_KOCH And detected <> SH_STATION_KUZ Then
            Err.Raise vbObjectError + 662, , "Report station must be 1 or 2."
        End If
    End If

    If detected <> 0 Then SH_SetMetaValue wb, SH_StationMetaLabel(), detected
    SH_ReportStationId = detected
End Function

Public Function SH_ReportStationName(ByVal stationId As Long) As String
    Select Case stationId
        Case SH_STATION_KOCH
            SH_ReportStationName = SH_U("041A043E0447044304310435043504320441043A0430044F00200412042D0421")
        Case SH_STATION_KUZ
            SH_ReportStationName = SH_U("041A04430437044C043C0438043D0441043A0430044F00200412042D0421")
        Case Else
            Err.Raise 5
    End Select
End Function

Public Function SH_ReportStationWtgCount(ByVal stationId As Long) As Long
    If stationId = SH_STATION_KUZ Then
        SH_ReportStationWtgCount = 64
    Else
        SH_ReportStationWtgCount = 84
    End If
End Function

Public Function SH_ReportStationStateLastRow(ByVal stationId As Long) As Long
    If stationId = SH_STATION_KUZ Then
        SH_ReportStationStateLastRow = 74
    Else
        SH_ReportStationStateLastRow = 98
    End If
End Function

Public Function SH_StationMenuXml() As String
    SH_StationMenuXml = _
        "<menu xmlns=""http://schemas.microsoft.com/office/2009/07/customui"">" & _
        "<button id=""stationKoch"" label=""" & SH_ReportStationName(SH_STATION_KOCH) & _
        """ tag=""1"" onAction=""SH_RibbonSetStation""/>" & _
        "<button id=""stationKuz"" label=""" & SH_ReportStationName(SH_STATION_KUZ) & _
        """ tag=""2"" onAction=""SH_RibbonSetStation""/>" & _
        "</menu>"
End Function

Public Sub SH_SetReportStation(ByVal stationId As Long)
    On Error GoTo Failed
    Dim wb As Workbook
    If stationId <> SH_STATION_KOCH And stationId <> SH_STATION_KUZ Then Err.Raise 5
    Set wb = SH_JournalBook()
    SH_SetMetaValue wb, SH_StationMetaLabel(), stationId
    SH_EnsureStationReportContour wb
    MsgBox SH_U("042104420430043D04460438044F002004400430043F043E04400442043000200443044104420430043D043E0432043B0435043D0430003A0020") & _
        SH_ReportStationName(stationId), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    MsgBox Err.Description, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_PrepareStationReportContour()
    On Error GoTo Failed
    Dim wb As Workbook
    Set wb = SH_JournalBook()
    SH_EnsureStationReportContour wb
    MsgBox SH_T("OK_PREP") & vbCrLf & SH_T("NO_TEMPLATE_PICK"), vbInformation, "Shift-Helper"
    Exit Sub
Failed:
    MsgBox SH_T("ERR_PREP") & "[#" & CStr(Err.Number) & "] " & Err.Description, vbExclamation, "Shift-Helper"
End Sub

Public Sub SH_ShowStationCalendar()
    Dim wb As Workbook
    Set wb = SH_JournalBook()
    SH_EnsureStationReportContour wb
    SH_ShowCalendar
    SH_EnsureStationReportContour wb
End Sub

Public Sub SH_ImportStationGeneration()
    Dim wb As Workbook
    Set wb = SH_JournalBook()
    SH_EnsureStationReportContour wb
    SH_ImportGenerationUniversal
    SH_EnsureStationReportContour wb
End Sub

Public Sub SH_UpdateStationRotorLimits()
    Dim wb As Workbook
    Set wb = SH_JournalBook()
    SH_EnsureStationReportContour wb
    SH_UpdateRotorLimits
    SH_EnsureStationReportContour wb
End Sub

Public Sub SH_EnsureStationReportContour(ByVal wb As Workbook)
    On Error GoTo Failed
    Dim stationId As Long, oldCalculation As XlCalculation
    Dim oldEvents As Boolean, oldScreenUpdating As Boolean, captured As Boolean
    Dim stage As String, errNumber As Long, errDescription As String

    stage = "resolve report station"
    stationId = SH_ReportStationId(wb, True)

    stage = "capture Excel state"
    oldCalculation = Application.Calculation
    oldEvents = Application.EnableEvents
    oldScreenUpdating = Application.ScreenUpdating
    captured = True
    Application.Calculation = xlCalculationManual
    Application.EnableEvents = False
    Application.ScreenUpdating = False

    stage = "prepare common report contour"
    SH_EnsureReportContour wb

    stage = "apply station layout"
    SH_ApplyStationProfile wb, stationId

    stage = "apply common formulas"
    SH_ApplyCriticalFormulas wb

    stage = "apply station formulas"
    SH_ApplyStationOverrides wb, stationId

    stage = "calculate station report inputs"
    SH_CalculateReportInputs wb

    Application.Calculation = oldCalculation
    Application.EnableEvents = oldEvents
    Application.ScreenUpdating = oldScreenUpdating
    Exit Sub
Failed:
    errNumber = Err.Number
    errDescription = Err.Description
    On Error Resume Next
    If captured Then
        Application.Calculation = oldCalculation
        Application.EnableEvents = oldEvents
        Application.ScreenUpdating = oldScreenUpdating
    End If
    On Error GoTo 0
    If errNumber = 0 Then errNumber = vbObjectError + 663
    If Len(errDescription) = 0 Then errDescription = "Station report preparation failed."
    Err.Raise errNumber, , "Stage [" & stage & "]: " & errDescription
End Sub

Private Sub SH_ApplyStationProfile(ByVal wb As Workbook, ByVal stationId As Long)
    Dim main As Worksheet, state As Worksheet, monthIndex As Long
    Set main = SH_RequireSheet(wb, SH_InputSheetName(1))
    Set state = SH_RequireSheet(wb, SH_InputSheetName(5))

    For monthIndex = 1 To 12
        main.Cells(monthIndex + 4, 9).Value2 = SH_StationPlan2026(stationId, monthIndex)
    Next monthIndex

    If Not SH_StationLayoutMatches(state, stationId) Then
        SH_RebuildStationState state, stationId
    End If
End Sub

Private Sub SH_ApplyStationOverrides(ByVal wb As Workbook, ByVal stationId As Long)
    Dim main As Worksheet, state As Worksheet, ws As Worksheet
    Dim q As String, prepName As String, stationName As String, lastStateRow As Long
    Dim i As Long, baseTitle As String
    q = Chr$(34)
    prepName = SH_PrepSheetName()
    stationName = SH_ReportStationName(stationId)
    Set main = SH_RequireSheet(wb, SH_InputSheetName(1))
    Set state = SH_RequireSheet(wb, SH_InputSheetName(5))
    lastStateRow = SH_ReportStationStateLastRow(stationId)

    If stationId = SH_STATION_KUZ Then
        main.Range("B1").Formula = "=" & q & SH_U("04200430043F043E044004420020041D042104210020043D04300020") & q & _
            "&TEXT('" & prepName & "'!B3," & q & "dd.mm.yyyy" & q & ")&" & q & " " & q & "&" & q & stationName & q & _
            "&" & q & SH_U("002E0020041F043E0441043B04350434043D04380435002004380437043C0435043D0435043D0438044F0020") & q & _
            "&TEXT(NOW()," & q & "dd.mm.yyyy, hh:mm:ss" & q & ")"
    Else
        main.Range("B1").Formula = "=" & q & SH_U("04200430043F043E044004420020041D042104210020043D04300020") & q & _
            "&TEXT('" & prepName & "'!B3," & q & "dd.mm.yyyy" & q & ")&" & q & " " & q & "&" & q & stationName & q & _
            "&" & q & SH_U("00200028") & q & "&'" & prepName & "'!B7&" & q & _
            SH_U("0029002E0020041F043E0441043B04350434043D04380435002004380437043C0435043D0435043D0438044F0020") & q & _
            "&TEXT(NOW()," & q & "dd.mm.yyyy, hh:mm:ss" & q & ")"
    End If

    main.Range("H3").Formula = "=" & q & SH_U("041F043B0430043D002F04240430043A04420020") & stationName & " " & q & _
        "&YEAR('" & prepName & "'!B3)"
    main.Range("F4").Formula = "=COUNTIF('" & state.Name & "'!L4:L" & CStr(lastStateRow) & "," & q & SH_StatusText(2) & q & ")"
    main.Range("F5").Formula = "=COUNTIF('" & state.Name & "'!L4:L" & CStr(lastStateRow) & "," & q & SH_StatusText(1) & q & ")"
    main.Range("F6").Formula = "=COUNTIF('" & state.Name & "'!L4:L" & CStr(lastStateRow) & "," & q & SH_StatusText(3) & q & ")"
    main.Range("F7").Formula = "=COUNTIF('" & state.Name & "'!L4:L" & CStr(lastStateRow) & "," & q & SH_StatusText(4) & q & ")"

    For i = 2 To SH_ReportSheetCount()
        Set ws = SH_RequireSheet(wb, SH_InputSheetName(i))
        Select Case i
            Case 2: baseTitle = SH_U("041004320430044004380439043D044B04350020043E0442043A043B044E04470435043D0438044F0020041B042D041F0020043D04300020")
            Case 3: baseTitle = SH_U("041A043E043C0430043D0434044B0020043F043E00200432043D04350448043D0435043900200438043D043804460438043004420438043204350020043D04300020")
            Case 4: baseTitle = SH_U("041D04300440044304480435043D0438044F0020041E04220438041F04110020002B0020042D043A043E043B043E04330438044F0020043D04300020")
            Case 5: baseTitle = SH_U("0421043E04410442043E044F043D0438043500200412042D04230020043D04300020")
            Case 6: baseTitle = SH_U("04170430043F043B0430043D04380440043E04320430043D043D044B04350020044004300431043E0442044B0020043D04300020")
            Case 7: baseTitle = SH_U("0414043504440435043A0442044B0020043E0431043E044004430434043E04320430043D0438044F0020043D04300020")
        End Select
        ws.Range("B1").Formula = "=" & q & baseTitle & q & "&TEXT('" & prepName & "'!B3," & q & "dd.mm.yyyy" & q & ")&" & q & " " & stationName & q
    Next i
End Sub

Private Function SH_StationPlan2026(ByVal stationId As Long, ByVal monthIndex As Long) As Double
    If stationId = SH_STATION_KUZ Then
        Select Case monthIndex
            Case 1: SH_StationPlan2026 = 36814159#
            Case 2: SH_StationPlan2026 = 33290612#
            Case 3: SH_StationPlan2026 = 45586481#
            Case 4: SH_StationPlan2026 = 39089392#
            Case 5: SH_StationPlan2026 = 30340811#
            Case 6: SH_StationPlan2026 = 20301332#
            Case 7: SH_StationPlan2026 = 20890080#
            Case 8: SH_StationPlan2026 = 31380024#
            Case 9: SH_StationPlan2026 = 27937084#
            Case 10: SH_StationPlan2026 = 52918060#
            Case 11: SH_StationPlan2026 = 40794027#
            Case 12: SH_StationPlan2026 = 45505936#
            Case Else: Err.Raise 5
        End Select
    Else
        Select Case monthIndex
            Case 1: SH_StationPlan2026 = 51934734#
            Case 2: SH_StationPlan2026 = 44351219#
            Case 3: SH_StationPlan2026 = 60732317#
            Case 4: SH_StationPlan2026 = 52076610#
            Case 5: SH_StationPlan2026 = 40421364#
            Case 6: SH_StationPlan2026 = 27046328#
            Case 7: SH_StationPlan2026 = 27830685#
            Case 8: SH_StationPlan2026 = 43191351#
            Case 9: SH_StationPlan2026 = 37219013#
            Case 10: SH_StationPlan2026 = 70499769#
            Case 11: SH_StationPlan2026 = 54347599#
            Case 12: SH_StationPlan2026 = 60625012#
            Case Else: Err.Raise 5
        End Select
    End If
End Function

Private Function SH_StationLayoutMatches(ByVal state As Worksheet, ByVal stationId As Long) As Boolean
    Dim r As Long, countWtg As Long, assetText As String, expected As Long
    Dim firstCode As String, lastCode As String, foundFirst As Boolean, foundLast As Boolean
    Dim nextKuzAsset As Long
    expected = SH_ReportStationWtgCount(stationId)
    If stationId = SH_STATION_KUZ Then
        firstCode = "GVIE0531": lastCode = "GVIE0545"
        nextKuzAsset = 1
    Else
        firstCode = "GVIE0532": lastCode = "GVIE0891"
    End If
    For r = 4 To 220
        assetText = SH_StationSafeText(state.Cells(r, 4).Value2)
        If Left$(assetText, 4) = SH_U("0412042D0423002D") Then
            countWtg = countWtg + 1
            If stationId = SH_STATION_KUZ Then
                If assetText <> SH_U("0412042D0423002D") & CStr(nextKuzAsset) Then Exit Function
                nextKuzAsset = nextKuzAsset + 1
            End If
        End If
        If StrComp(SH_StationSafeText(state.Cells(r, 3).Value2), firstCode, vbTextCompare) = 0 Then foundFirst = True
        If StrComp(SH_StationSafeText(state.Cells(r, 3).Value2), lastCode, vbTextCompare) = 0 Then foundLast = True
    Next r
    SH_StationLayoutMatches = (countWtg = expected And foundFirst And foundLast)
    If stationId = SH_STATION_KUZ Then
        SH_StationLayoutMatches = SH_StationLayoutMatches And nextKuzAsset = 65
    End If
End Function

Private Sub SH_RebuildStationState(ByVal state As Worksheet, ByVal stationId As Long)
    Dim starts As Variant, ends As Variant, codes As Variant
    Dim groupIndex As Long, asset As Long, rowNumber As Long, groupRow As Long
    Dim groupHeight As Double, childHeight As Double, stationName As String

    If stationId = SH_STATION_KUZ Then
        starts = Array(1, 17, 25, 33, 41, 49, 57)
        ends = Array(16, 24, 32, 40, 48, 56, 64)
        codes = Array("GVIE0531", "GVIE0555", "GVIE0546", "GVIE0543", "GVIE0547", "GVIE0549", "GVIE0545")
    Else
        starts = Array(45, 5, 13, 21, 29, 37, 61, 53, 69, 77, 1)
        ends = Array(52, 12, 20, 28, 36, 44, 68, 60, 76, 84, 4)
        codes = Array("GVIE0532", "GVIE0534", "GVIE0536", "GVIE0537", "GVIE0538", "GVIE0539", "GVIE0570", "GVIE0571", "GVIE0573", "GVIE0580", "GVIE0891")
    End If

    stationName = SH_ReportStationName(stationId)
    groupHeight = state.Rows(4).RowHeight
    childHeight = state.Rows(5).RowHeight
    On Error Resume Next
    state.Range("B4:C220").UnMerge
    On Error GoTo 0
    state.Range("B4:L220").ClearContents
    rowNumber = 4

    For groupIndex = LBound(starts) To UBound(starts)
        groupRow = rowNumber
        If groupRow <> 4 Then
            state.Range("B4:L4").Copy
            state.Range("B" & CStr(groupRow) & ":L" & CStr(groupRow)).PasteSpecial Paste:=xlPasteFormats
        End If
        state.Rows(groupRow).RowHeight = groupHeight
        state.Cells(groupRow, 2).Value = stationName & " (" & SH_U("0412042D0423") & CStr(starts(groupIndex)) & "-" & SH_U("0412042D0423") & CStr(ends(groupIndex)) & ")"
        state.Cells(groupRow, 3).Value = CStr(codes(groupIndex))
        state.Cells(groupRow, 5).Value2 = (CLng(ends(groupIndex)) - CLng(starts(groupIndex)) + 1) * 2.5
        rowNumber = rowNumber + 1

        For asset = CLng(starts(groupIndex)) To CLng(ends(groupIndex))
            If rowNumber <> 5 Then
                state.Range("B5:L5").Copy
                state.Range("B" & CStr(rowNumber) & ":L" & CStr(rowNumber)).PasteSpecial Paste:=xlPasteFormats
            End If
            state.Rows(rowNumber).RowHeight = childHeight
            state.Cells(rowNumber, 4).Value = SH_U("0412042D0423002D") & CStr(asset)
            state.Cells(rowNumber, 5).Value2 = 2.5
            state.Cells(rowNumber, 6).Value2 = 2.5
            state.Cells(rowNumber, 7).Value2 = 0#
            state.Cells(rowNumber, 8).Formula = "=MAX(F" & CStr(rowNumber) & "-G" & CStr(rowNumber) & ",0)"
            state.Cells(rowNumber, 12).Value = SH_StatusText(1)
            rowNumber = rowNumber + 1
        Next asset

        state.Range("B" & CStr(groupRow) & ":B" & CStr(rowNumber - 1)).Merge
        state.Range("C" & CStr(groupRow) & ":C" & CStr(rowNumber - 1)).Merge
        With state.Range("B" & CStr(groupRow) & ":C" & CStr(rowNumber - 1))
            .HorizontalAlignment = xlCenter
            .VerticalAlignment = xlCenter
            .WrapText = True
        End With
    Next groupIndex
    Application.CutCopyMode = False

    If rowNumber - 1 <> SH_ReportStationStateLastRow(stationId) Then
        Err.Raise vbObjectError + 664, , "Station WTG layout row count mismatch."
    End If

    If stationId = SH_STATION_KUZ Then
        state.Rows("75:98").Delete Shift:=xlUp
    Else
        state.Range("B99:L220").ClearContents
    End If
End Sub

Private Function SH_StationFromText(ByVal value As String) As Long
    Dim normalized As String
    normalized = LCase$(Trim$(value))
    If InStr(1, normalized, SH_U("043A04430437044C043C0438043D"), vbTextCompare) > 0 Or _
       InStr(1, normalized, SH_U("043A04430437"), vbTextCompare) > 0 Then
        SH_StationFromText = SH_STATION_KUZ
    ElseIf InStr(1, normalized, SH_U("043A043E044704430431"), vbTextCompare) > 0 Then
        SH_StationFromText = SH_STATION_KOCH
    End If
End Function

Private Function SH_StationMetaLabel() As String
    SH_StationMetaLabel = SH_U("042104420430043D04460438044F002004400430043F043E044004420430")
End Function

Private Function SH_StationSafeText(ByVal value As Variant) As String
    On Error GoTo Failed
    If IsError(value) Or IsNull(value) Or IsEmpty(value) Then Exit Function
    SH_StationSafeText = CStr(value)
    Exit Function
Failed:
    SH_StationSafeText = ""
End Function