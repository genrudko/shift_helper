from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
VBA = ROOT / "packaging" / "excel_addin" / "vba"
RIBBON = ROOT / "packaging" / "excel_addin" / "customUI14.xml"
NS = {"ui": "http://schemas.microsoft.com/office/2009/07/customui"}


def _source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def test_mail_button_binding_never_persists_a_user_profile_path() -> None:
    binding = _source("modShiftHelperMailBinding.bas")

    assert "ThisWorkbook.Name" in binding
    assert "ThisWorkbook.FullName" not in binding
    assert 'expectedAction = "\'" & ThisWorkbook.Name & "\'!" & targetMacro' in binding
    assert "C:\\Users\\" not in binding


def test_old_and_new_sheet_button_actions_are_migrated() -> None:
    binding = _source("modShiftHelperMailBinding.bas")

    for token in (
        "createmail_list1",
        "createmail_list2",
        "createmail_list3",
        "send_mail",
        "sh_mail_list1",
        "sh_mail_list2",
        "sh_mail_list3",
        "sh_mail_morning",
        "sh_mail_zarubezhneft_list1",
        "sh_mail_zarubezhneft_list2",
        "sh_mail_zarubezhneft_list3",
        "sh_mail_zarubezhneft_morning",
        "sh_mail_zarubezhneft",
    ):
        assert token in binding.lower()


def test_mail_button_bindings_auto_repair_on_workbook_open_and_activate() -> None:
    events = _source("CShiftHelperAppEvents.cls")

    assert "Private Sub App_WorkbookOpen(ByVal Wb As Workbook)" in events
    assert "Private Sub App_WorkbookActivate(ByVal Wb As Workbook)" in events
    assert events.count("SH_RepairMailButtonBindings Wb, False") == 2


def test_ribbon_has_manual_mail_button_repair_fallback() -> None:
    root = ET.parse(RIBBON).getroot()
    callbacks = _source("modShiftHelperRibbon.bas")

    control = root.find(".//ui:button[@id='btnRepairMailButtons']", NS)
    assert control is not None
    assert control.attrib["onAction"] == "SH_RibbonRepairMailButtons"
    assert "Public Sub SH_RibbonRepairMailButtons" in callbacks
    assert "SH_RepairMailButtons" in callbacks
