from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VBA_DIR = ROOT / "packaging" / "excel_addin" / "vba"
RIBBON = ROOT / "packaging" / "excel_addin" / "customUI14.xml"


def _read(name: str) -> str:
    return (VBA_DIR / name).read_text(encoding="ascii")


def test_report_save_settings_are_exposed_from_ribbon() -> None:
    xml = RIBBON.read_text(encoding="utf-8")
    ribbon = _read("modShiftHelperRibbon.bas")

    assert 'id="btnReportSaveSettings"' in xml
    assert 'label="Сохранение"' in xml
    assert 'getContent="SH_RibbonReportSaveSettingsMenu"' in xml
    assert "Public Sub SH_RibbonReportSaveSettingsMenu" in ribbon
    assert "Public Sub SH_RibbonReportSaveSetting" in ribbon
    assert "SH_ReportSaveSettingsMenuXml()" in ribbon
    assert "SH_EditReportSaveSetting CStr(control.Tag)" in ribbon


def test_report_save_settings_use_workbook_metadata_and_date_tokens() -> None:
    settings = _read("modShiftHelperReportSaveSettings.bas")

    assert '"report.output.folder"' in settings
    assert '"report.output.filename_template"' in settings
    assert "SH_MetaValue" in settings
    assert "SH_SetMetaValue" in settings
    assert '"{date}"' in settings
    assert '"{date_iso}"' in settings
    assert 'Format$(reportDate, "dd.mm.yyyy")' in settings
    assert 'Format$(reportDate, "yyyy-mm-dd")' in settings
    assert "msoFileDialogFolderPicker" in settings
    assert "Application.InputBox" in settings


def test_generated_report_uses_configured_suggested_path_but_keeps_save_dialog() -> None:
    output = _read("modShiftHelperReportOutput.bas")

    assert "suggested = SH_ReportSuggestedPath(wb, reportDate)" in output
    assert "Application.GetSaveAsFilename" in output
    assert '"Shift-Helper-Report-" & Format$(reportDate' not in output


def test_report_save_settings_vba_remains_ascii_safe() -> None:
    raw = (VBA_DIR / "modShiftHelperReportSaveSettings.bas").read_bytes()
    raw.decode("ascii")
