from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VBA = ROOT / "packaging" / "excel_addin" / "vba"


def _source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def test_ribbon_exposes_station_aware_mailing_menu() -> None:
    ribbon = _source("modShiftHelperRibbon.bas")
    mailing = _source("modShiftHelperMailing.bas")
    custom_ui = (ROOT / "packaging" / "excel_addin" / "customUI14.xml").read_text(
        encoding="utf-8"
    )

    assert 'id="btnMailing"' in custom_ui
    assert 'getContent="SH_RibbonMailingMenu"' in custom_ui
    assert "SH_MailingMenuXml" in ribbon
    assert "SH_CreateStationMailingDraft CStr(control.Tag)" in ribbon
    assert 'Case "btnMailing"' in ribbon
    assert 'Case "btnMailDraft"' not in ribbon

    for tag in (
        '"list:1"',
        '"list:2"',
        '"list:3"',
        '"morning"',
        '"foreign-list:1"',
        '"foreign-list:2"',
        '"foreign-list:3"',
        '"foreign-morning"',
        '"foreign-sheet"',
    ):
        assert tag in mailing


def test_kochubeevskaya_mailing_preserves_legacy_layout_and_signature_behavior() -> None:
    mailing = _source("modShiftHelperMailing.bas")

    assert 'subjectCell = "B2": recipientCell = "A8"' in mailing
    assert 'subjectCell = "B3": recipientCell = "B8"' in mailing
    assert 'subjectCell = "B4": recipientCell = "C8"' in mailing
    expected = (
        'SH_CreateMailDraft ws, "B1", recipientCell, "", subjectCell, '
        '"C2", "", "", True'
    )
    assert expected in mailing
    assert "SH_MailNormalizeRecipients" in mailing
    assert "mail.GetInspector.WordEditor" in mailing
    assert 'insertedRange.Font.Name = "Arial"' in mailing
    assert "insertedRange.Font.Size = 12" in mailing


def test_kuzminskaya_mailing_preserves_three_lists_and_zarubezhneft_paths() -> None:
    mailing = _source("modShiftHelperMailing.bas")

    assert 'SH_CreateMailDraft ws, "B4", "B5", "", "B7", "B8", "B9", "B10", False' in mailing
    assert 'SH_CreateMailDraft ws, "B17", "B18", "B19", "B20", "B8", "B9", "B10", False' in mailing
    assert 'SH_CreateMailDraft ws, "B2", "B3", "B4", "B5", "B6", "B7", "B10", False' in mailing
    assert "foreign-list:1" in mailing
    assert "foreign-morning" in mailing
    assert "foreign-sheet" in mailing
    assert "mail.CC = ccValue" in mailing
    assert "mail.Attachments.Add attachment" in mailing


def test_generated_report_path_is_registered_for_morning_mailings() -> None:
    mailing = _source("modShiftHelperMailing.bas")
    output = _source("modShiftHelperReportOutput.bas")

    assert "Public Sub SH_RegisterGeneratedReport" in mailing
    assert 'ws.Range("B10").Value = reportPath' in mailing
    assert 'ws.Range("B23").Value = reportPath' in mailing
    assert "SH_RegisterGeneratedReport wb, CStr(outputPath)" in output
