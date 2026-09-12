VERSION 1.0 CLASS
BEGIN
  MultiUse = -1  'True
END
Attribute VB_Name = "CShiftHelperAppEvents"
Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = False
Attribute VB_PredeclaredId = False
Attribute VB_Exposed = False
Option Explicit

Public WithEvents App As Application

Private Sub App_WorkbookOpen(ByVal Wb As Workbook)
    SH_RepairMailButtonBindings Wb, False
    SH_RefreshLWGUIBadge Wb
End Sub

Private Sub App_WorkbookActivate(ByVal Wb As Workbook)
    SH_RepairMailButtonBindings Wb, False
    SH_RefreshLWGUIBadge Wb
End Sub

Private Sub App_SheetActivate(ByVal Sh As Object)
    On Error GoTo SafeExit
    If Application.CutCopyMode <> False Then Exit Sub
    If TypeName(Sh) <> "Worksheet" Then Exit Sub
    If Sh.Name <> SH_JournalSheetName() Then Exit Sub
    SH_RefreshLWGUIBadge Sh.Parent
SafeExit:
End Sub

Private Sub App_SheetSelectionChange(ByVal Sh As Object, ByVal Target As Range)
    ' Native Excel copy/cut must take precedence over Shift-Helper selection preparation.
    ' Any format write during CutCopyMode cancels the user's pending Ctrl+C/Ctrl+X operation.
    If Application.CutCopyMode <> False Then Exit Sub
    If Not SH_QuickInputEventAllowed(Sh) Then Exit Sub
    SH_PrepareQuickInputSelection Sh, Target
End Sub

Private Sub App_SheetChange(ByVal Sh As Object, ByVal Target As Range)
    SH_HandlePrepReportDateChange Sh, Target
    If Not SH_QuickInputEventAllowed(Sh) Then Exit Sub
    SH_HandleQuickInputChange Sh, Target
End Sub
