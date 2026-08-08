Attribute VB_Name = "modShiftHelperRibbon"
Option Explicit

Public Sub SH_RibbonSort(ByVal control As IRibbonControl)
    SH_SortJournalByTime
End Sub

Public Sub SH_RibbonMergeCopy(ByVal control As IRibbonControl)
    SH_MergeAndCopy
End Sub

Public Sub SH_RibbonCleanSpaces(ByVal control As IRibbonControl)
    SH_CleanSpaces
End Sub

Public Sub SH_RibbonRowHeight(ByVal control As IRibbonControl)
    SH_SetRowHeight
End Sub

Public Sub SH_RibbonPrepare(ByVal control As IRibbonControl)
    SH_PrepareReportContour
End Sub

Public Sub SH_RibbonCalendarMenu(ByVal control As IRibbonControl, ByRef returnedVal)
    returnedVal = SH_CalendarMenuXml()
End Sub

Public Sub SH_RibbonCalendarPick(ByVal control As IRibbonControl)
    SH_CalendarPickTag control.Tag
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
