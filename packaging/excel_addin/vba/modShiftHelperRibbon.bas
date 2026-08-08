Attribute VB_Name = "modShiftHelperRibbon"
Option Explicit

Public Sub SH_RibbonImage(ByVal control As IRibbonControl, ByRef returnedVal)
    Dim picture As Object, imageId As String
    imageId = SH_RibbonImageId(control.Id)
    On Error Resume Next
    Set picture = Application.CommandBars.GetImageMso(imageId, 32, 32)
    If picture Is Nothing Then Set picture = Application.CommandBars.GetImageMso("Paste", 32, 32)
    On Error GoTo 0
    If Not picture Is Nothing Then Set returnedVal = picture
End Sub

Private Function SH_RibbonImageId(ByVal controlId As String) As String
    Select Case controlId
        Case "btnSort": SH_RibbonImageId = "SortAscendingExcel"
        Case "btnMergeCopy": SH_RibbonImageId = "Copy"
        Case "btnClean": SH_RibbonImageId = "Clear"
        Case "btnRows": SH_RibbonImageId = "FormatRowAutoFitExcel"
        Case "btnPrepare": SH_RibbonImageId = "TableInsertRowsAbove"
        Case "btnCalendar": SH_RibbonImageId = "CalendarInsert"
        Case "btnGenerate": SH_RibbonImageId = "FileSaveAs"
        Case "btnGeneration": SH_RibbonImageId = "RefreshAll"
        Case "btnOutlook": SH_RibbonImageId = "Outlook"
        Case "btnRotor": SH_RibbonImageId = "ControlsGallery"
        Case "btnShift": SH_RibbonImageId = "GoTo"
        Case Else: SH_RibbonImageId = "Paste"
    End Select
End Function

Public Sub SH_RibbonSort(ByVal control As IRibbonControl)
    SH_SortJournalByTime
End Sub

Public Sub SH_RibbonMergeCopy(ByVal control As IRibbonControl)
    SH_MergeAndCopy
End Sub

Public Sub SH_RibbonCleanSpaces(ByVal control As IRibbonControl)
    SH_CleanSpaces
End Sub

Public Sub SH_RibbonAutoFitRows(ByVal control As IRibbonControl)
    SH_AutoFitRows
End Sub

Public Sub SH_RibbonPrepare(ByVal control As IRibbonControl)
    SH_PrepareReportContour
End Sub

Public Sub SH_RibbonCalendar(ByVal control As IRibbonControl)
    SH_ShowCalendar
End Sub

Public Sub SH_RibbonGenerate(ByVal control As IRibbonControl)
    SH_GenerateFullReport
End Sub

Public Sub SH_RibbonImportGeneration(ByVal control As IRibbonControl)
    SH_ImportGeneration
End Sub

Public Sub SH_RibbonOutlookMenu(ByVal control As IRibbonControl, ByRef returnedVal)
    returnedVal = SH_OutlookMenuXml()
End Sub

Public Sub SH_RibbonOutlookEdit(ByVal control As IRibbonControl)
    SH_EditOutlookSetting control.Tag
End Sub

Public Sub SH_RibbonRotorLimits(ByVal control As IRibbonControl)
    SH_UpdateRotorLimits
End Sub

Public Sub SH_RibbonCurrentShift(ByVal control As IRibbonControl)
    SH_GotoCurrentInspectionShift
End Sub
