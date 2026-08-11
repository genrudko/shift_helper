from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VBA_DIR = ROOT / "packaging" / "excel_addin" / "vba"
RIBBON = ROOT / "packaging" / "excel_addin" / "customUI14.xml"


def _read(name: str) -> str:
    return (VBA_DIR / name).read_text(encoding="ascii")


def test_nss_selector_is_exposed_in_report_ribbon_group() -> None:
    xml = RIBBON.read_text(encoding="utf-8")
    ribbon = _read("modShiftHelperRibbon.bas")

    assert 'id="btnNss"' in xml
    assert 'label="НСС"' in xml
    assert 'getContent="SH_RibbonNssMenu"' in xml
    assert "Public Sub SH_RibbonNssMenu" in ribbon
    assert "Public Sub SH_RibbonNssAction" in ribbon
    assert "SH_NssMenuXml()" in ribbon
    assert "SH_NssRibbonAction CStr(control.Tag)" in ribbon


def test_nss_lists_and_selection_are_station_specific_and_feed_prep_b7() -> None:
    nss = _read("modShiftHelperNSS.bas")
    station_facts = _read("modShiftHelperStationFacts.bas")
    output = _read("modShiftHelperReportOutput.bas")

    assert '"report.nss.list."' in nss
    assert '"report.nss.selected."' in nss
    assert 'Private Const SH_NSS_CELL As String = "B7"' in nss
    assert 'tag=""edit:1""' in nss
    assert 'tag=""edit:2""' in nss
    assert "SH_SetMetaValue wb, SH_NssSelectedKey(stationId), selected" in nss
    assert "prep.Range(SH_NSS_CELL).Value = selected" in nss
    assert "SH_ApplyNssForStation wb, stationId" in station_facts
    assert "SH_ApplyNssForCurrentStation wb" in station_facts
    assert "SH_ApplyNssForCurrentStation wb" in output
    assert "Private Sub SH_OutputApplyNssCaption" in output
    assert "If stationId <> SH_STATION_KUZ Then Exit Sub" in output
    assert '" (" & selected & ")"' in output


def test_nss_vba_remains_ascii_safe_and_module_name_fits_vba_storage() -> None:
    raw = (VBA_DIR / "modShiftHelperNSS.bas").read_bytes()
    source = raw.decode("ascii")

    assert 'Attribute VB_Name = "modShiftHelperNSS"' in source
    assert len("modShiftHelperNSS") <= 31
