from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VBA = ROOT / "packaging" / "excel_addin" / "vba"


def _source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def test_generation_import_supports_both_station_workbook_contracts() -> None:
    source = _source("modShiftHelperGenProfiles.bas")
    ribbon = _source("modShiftHelperRibbon.bas")

    assert "Public Sub SH_ImportGenerationUniversal" in source
    assert "SH_ImportGenerationUniversal" in ribbon
    assert "SH_ImportGenerationSafe" not in ribbon

    # Accepted Kochubeevskaya contract from the legacy macro.
    assert 'ws.Range("G26").Value2' in source
    assert 'ws.Range("Q26").Value2' in source
    assert 'ws.Range("Q" & CStr(rowNumber)).Value2' in source

    # Kuzminskaya workbook uploaded during live acceptance.
    assert 'ws.Range("J1").Value2' in source
    assert 'ws.Range("Z1").Value2' in source
    assert 'ws.Range("J26").Value2' in source
    assert 'ws.Range("Z26").Value2' in source
    assert "SH_G2TryKuzProfile" in source
    assert "SH_G2TryKvesProfile" in source

    # Formula-driven source workbooks are recalculated even while the host journal
    # remains in manual calculation mode for performance.
    assert "For pass = 1 To 2" in source
    assert "ws.Calculate" in source

    # Wrong-day source files must not be silently imported.
    assert 'sumSheet.Range("A2").Value2' in source
    assert "Generation workbook date does not match the report day." in source


def test_generation_outlook_search_is_station_aware_but_keeps_manual_fallback() -> None:
    source = _source("modShiftHelperGenProfiles.bas")

    assert "SH_G2StationHint" in source
    assert "SH_G2StationFromText" in source
    assert "SH_G2FileMatchesStation" in source
    assert "SH_G2AttachmentMatches" in source
    assert "ns.GetSharedDefaultFolder(recipient, 6)" in source
    assert "root.Store.GetDefaultFolder(6)" in source
    assert "ns.GetDefaultFolder(6)" in source
    assert "SH_G2PickFile" in source
    assert "XLSX samples:" in source
    assert '"Station: " & SH_G2ProfileCaption(stationHint)' in source
