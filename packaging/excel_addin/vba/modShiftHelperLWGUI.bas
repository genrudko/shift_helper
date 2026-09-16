Attribute VB_Name = "modShiftHelperLWGUI"
Option Explicit

Private Const SH_LWGUI_BADGE_NAME As String = "ShiftHelperLWGUI"

Public Sub SH_RefreshLWGUIBadge(Optional ByVal wb As Workbook)
    On Error GoTo SafeExit
    Dim wsJournal As Worksheet, wsDay As Worksheet, badge As Shape
    Dim raw As Variant, passwordText As String, desiredText As String
    Dim anchor As Range

    ' Never touch workbook objects while Excel owns a pending native copy/cut operation.
    If Application.CutCopyMode <> False Then Exit Sub

    If wb Is Nothing Then Set wb = Application.ActiveWorkbook
    If wb Is Nothing Then Exit Sub
    If wb Is ThisWorkbook Then Exit Sub
    If Not SH_HasSheet(wb, SH_JournalSheetName()) Then Exit Sub

    Set wsJournal = wb.Worksheets(SH_JournalSheetName())
    Set badge = SH_LWGUIExistingBadge(wsJournal)

    If Not SH_HasSheet(wb, "Day") Then
        If Not badge Is Nothing Then badge.Visible = msoFalse
        Exit Sub
    End If

    Set wsDay = wb.Worksheets("Day")
    raw = wsDay.Range("D9").Value2
    If IsError(raw) Or IsNull(raw) Or IsEmpty(raw) Then
        If Not badge Is Nothing Then badge.Visible = msoFalse
        Exit Sub
    End If

    passwordText = Trim$(CStr(raw))
    If Len(passwordText) = 0 Then
        If Not badge Is Nothing Then badge.Visible = msoFalse
        Exit Sub
    End If

    desiredText = passwordText

    If badge Is Nothing Then
        Set anchor = wsJournal.Range("P1")
        Set badge = wsJournal.Shapes.AddShape(msoShapeRoundedRectangle, _
            anchor.Left, anchor.Top + 2, 135, 40)
        badge.Name = SH_LWGUI_BADGE_NAME
        badge.Placement = xlFreeFloating
        badge.Fill.ForeColor.RGB = RGB(242, 242, 242)
        badge.Line.ForeColor.RGB = RGB(166, 166, 166)
        badge.TextFrame2.TextRange.Font.Bold = msoTrue
        badge.TextFrame2.TextRange.ParagraphFormat.Alignment = msoAlignCenter
        badge.TextFrame2.VerticalAnchor = msoAnchorMiddle
    End If

    ' Keep the presentation contract even when the badge already exists from an older XLAM.
    If badge.TextFrame2.TextRange.Font.Size <> 24 Then badge.TextFrame2.TextRange.Font.Size = 24
    If badge.Height <> 40 Then badge.Height = 40

    ' Avoid a needless workbook write on every activation: update only when value changed.
    If badge.TextFrame2.TextRange.Text <> desiredText Then
        badge.TextFrame2.TextRange.Text = desiredText
    End If
    If badge.Visible <> msoTrue Then badge.Visible = msoTrue
SafeExit:
End Sub

Private Function SH_LWGUIExistingBadge(ByVal ws As Worksheet) As Shape
    On Error Resume Next
    Set SH_LWGUIExistingBadge = ws.Shapes(SH_LWGUI_BADGE_NAME)
    On Error GoTo 0
End Function
