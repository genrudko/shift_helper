Attribute VB_Name = "modShiftHelperQuickCompat"
Option Explicit

Public Function SH_QuickInputEventAllowed(ByVal Sh As Object) As Boolean
    On Error GoTo Blocked
    Dim wb As Workbook, fileName As String

    If TypeName(Sh) <> "Worksheet" Then Exit Function
    If Sh.Name <> SH_JournalSheetName() Then Exit Function

    Set wb = Sh.Parent
    If wb Is Nothing Then Exit Function
    fileName = LCase$(Trim$(wb.Name))

    ' Legacy macro-enabled workbooks can already own Worksheet_Change/Workbook events.
    ' Running the XLAM Application.SheetChange quick-input handler in parallel causes
    ' the same user edit to be processed by two independent VBA event systems.
    If Right$(fileName, 5) = ".xlsm" Then Exit Function
    If Right$(fileName, 5) = ".xlsb" Then Exit Function
    If Right$(fileName, 4) = ".xls" Then Exit Function

    SH_QuickInputEventAllowed = True
    Exit Function
Blocked:
    SH_QuickInputEventAllowed = False
End Function
