Attribute VB_Name = "modShiftHelperMailButtons"
Option Explicit

Public Sub SH_Mail_List1()
    SH_CreateStationMailingDraft "list:1"
End Sub

Public Sub SH_Mail_List2()
    SH_CreateStationMailingDraft "list:2"
End Sub

Public Sub SH_Mail_List3()
    SH_CreateStationMailingDraft "list:3"
End Sub

Public Sub SH_Mail_Morning()
    SH_CreateStationMailingDraft "morning"
End Sub

Public Sub SH_Mail_Zarubezhneft_List1()
    SH_CreateStationMailingDraft "foreign-list:1"
End Sub

Public Sub SH_Mail_Zarubezhneft_List2()
    SH_CreateStationMailingDraft "foreign-list:2"
End Sub

Public Sub SH_Mail_Zarubezhneft_List3()
    SH_CreateStationMailingDraft "foreign-list:3"
End Sub

Public Sub SH_Mail_Zarubezhneft_Morning()
    SH_CreateStationMailingDraft "foreign-morning"
End Sub

Public Sub SH_Mail_Zarubezhneft()
    SH_CreateStationMailingDraft "foreign-sheet"
End Sub
