from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VBA = ROOT / "packaging" / "excel_addin" / "vba"


def _source(name: str) -> str:
    return (VBA / name).read_text(encoding="ascii")


def test_report_contour_avoids_full_workbook_recalculation_and_cellwise_journal_scan() -> None:
    report = _source("modShiftHelperReport.bas")

    assert "Application.Calculation = xlCalculationManual" in report
    assert "Application.EnableEvents = False" in report
    assert "Public Sub SH_CalculateReportInputs" in report
    assert "wb.Calculate" not in report
    assert 'source.Range("B2:J" & lastRow).Value2' in report
    assert "SH_ReportSafeText" in report
    assert "SH_ReportTrySerial" in report
    assert 'Stage [" & stage & "]' in report


def test_generation_import_uses_hardened_runtime_and_bounded_outlook_scan() -> None:
    generation = _source("modShiftHelperGeneration.bas")
    ribbon = _source("modShiftHelperRibbon.bas")

    assert "Public Sub SH_ImportGenerationSafe" in generation
    assert "Application.Calculation = xlCalculationManual" in generation
    assert "SH_CalculateReportInputs wb" in generation
    assert "wb.Calculate" not in generation
    assert "SH_GenSafeDouble" in generation
    assert "SH_GenSafeText" in generation
    assert "SH_GenIsNumericValue" in generation
    assert "errNumber = Err.Number" in generation
    assert "errDescription = Err.Description" in generation
    assert "If Not source Is Nothing Then source.Close SaveChanges:=False" in generation
    assert "SH_GenTryDate(received, receivedDate)" in generation
    assert "If receivedDate < cutoff Then Exit For" in generation
    assert "SH_GenTryDate(received, cutoff)" not in generation
    assert "SH_ImportGenerationSafe" in ribbon


def test_live_repair_preserves_shared_journal_boundary() -> None:
    report = _source("modShiftHelperReport.bas")
    generation = _source("modShiftHelperGeneration.bas")

    combined = report + generation
    assert "VBProject" not in combined
    assert "ActiveX" not in combined
    assert "SaveAs Filename:=wb." not in combined
