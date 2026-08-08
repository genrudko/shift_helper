Attribute VB_Name = "modShiftHelperRibbon"
Option Explicit

Public Sub SH_RibbonOnLoad(ByVal ribbon As IRibbonUI)
    SH_InitializeAddin
End Sub

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
        Case "btnInsertDate", "btnCalendar": SH_RibbonImageId = "CalendarInsert"
        Case "btnTime": SH_RibbonImageId = "InsertTime"
        Case "btnPrepare": SH_RibbonImageId = "TableInsertRowsAbove"
        Case "btnStation": SH_RibbonImageId = "BuildingBlocksOrganizer"
        Case "btnGenerate": SH_RibbonImageId = "FileSaveAs"
        Case "btnGeneration": SH_RibbonImageId = "RefreshAll"
        Case "btnOutlook": SH_RibbonImageId = "Outlook"
        Case "btnMailDraft": SH_RibbonImageId = "FileSendAsAttachment"
        Case "btnMaintenance": SH_RibbonImageId = "InsertTextBox"
        Case "btnRotor": SH_RibbonImageId = "ControlsGallery"
        Case "btnShift": SH_RibbonImageId = "GoTo"
        Case "btnQuickOn": SH_RibbonImageId = "MacroPlay"
        Case "btnQuickStatus": SH_RibbonImageId = "Info"
        Case "btnQuickOff": SH_RibbonImageId = "MacroStop"
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

Public Sub SH_RibbonInsertDate(ByVal control As IRibbonControl)
    SH_InsertDateIntoSelection
End Sub

Public Sub SH_RibbonTime(ByVal control As IRibbonControl)
    SH_ShowTimePicker
End Sub

Public Sub SH_RibbonPrepare(ByVal control As IRibbonControl)
    SH_PrepareStationReportContour
End Sub

Public Sub SH_RibbonCalendar(ByVal control As IRibbonControl)
    SH_ShowStationCalendar
End Sub

Public Sub SH_RibbonStationMenu(ByVal control As IRibbonControl, ByRef returnedVal)
    returnedVal = SH_StationMenuXml()
End Sub

Public Sub SH_RibbonSetStation(ByVal control As IRibbonControl)
    SH_SetReportStation CLng(control.Tag)
End Sub

Public Sub SH_RibbonGenerate(ByVal control As IRibbonControl)
    SH_GeneratePreparedReport
End Sub

Public Sub SH_RibbonImportGeneration(ByVal control As IRibbonControl)
    SH_ImportStationGenerationSelected
End Sub

Public Sub SH_RibbonOutlookMenu(ByVal control As IRibbonControl, ByRef returnedVal)
    returnedVal = SH_OutlookMenuXml()
End Sub

Public Sub SH_RibbonOutlookEdit(ByVal control As IRibbonControl)
    SH_EditOutlookSetting control.Tag
End Sub

Public Sub SH_RibbonMailDraft(ByVal control As IRibbonControl)
    SH_CreateOutlookDraft
End Sub

Public Sub SH_RibbonMaintenance(ByVal control As IRibbonControl)
    SH_InsertMaintenanceText
End Sub

Public Sub SH_RibbonRotorLimits(ByVal control As IRibbonControl)
    SH_UpdateStationRotorLimits
End Sub

Public Sub SH_RibbonCurrentShift(ByVal control As IRibbonControl)
    SH_GotoCurrentInspectionShift
End Sub

Public Sub SH_RibbonQuickOn(ByVal control As IRibbonControl)
    SH_EnableQuickInput
End Sub

Public Sub SH_RibbonQuickStatus(ByVal control As IRibbonControl)
    SH_ShowQuickInputStatus
End Sub

Public Sub SH_RibbonQuickOff(ByVal control As IRibbonControl)
    SH_DisableQuickInput
End Sub
