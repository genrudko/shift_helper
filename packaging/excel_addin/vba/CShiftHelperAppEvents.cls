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
End Sub

Private Sub App_WorkbookActivate(ByVal Wb As Workbook)
    SH_RepairMailButtonBindings Wb, False
End Sub

Private Sub App_SheetSelectionChange(ByVal Sh As Object, ByVal Target As Range)
    If Not SH_QuickInputEventAllowed(Sh) Then Exit Sub
    SH_PrepareQuickInputSelection Sh, Target
End Sub

Private Sub App_SheetChange(ByVal Sh As Object, ByVal Target As Range)
    SH_HandlePrepReportDateChange Sh, Target
    If Not SH_QuickInputEventAllowed(Sh) Then Exit Sub
    SH_HandleQuickInputChange Sh, Target
End Sub
