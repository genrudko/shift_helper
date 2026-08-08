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


def test_calendar_uses_bounded_report_calculation_after_date_selection() -> None:
    calendar = _source("modShiftHelperCalendar.bas")

    assert "Application.Calculation = xlCalculationManual" in calendar
    assert "Application.EnableEvents = False" in calendar
    assert "SH_CalculateReportInputs wb" in calendar
    assert "wb.Calculate" not in calendar
    assert 'stage = "write report date"' in calendar
    assert 'stage = "refresh emergency outages"' in calendar
    assert 'Stage [" & stage & "]' in calendar
    assert "SH_CalendarTryDate" in calendar


def test_rotor_refresh_uses_array_scan_and_bounded_calculation() -> None:
    rotor = _source("modShiftHelperRotor.bas")

    assert "Application.Calculation = xlCalculationManual" in rotor
    assert 'journal.Range("B2:J" & lastRow).Value2' in rotor
    assert "SH_RotorSafeText" in rotor
    assert "SH_RotorTrySerial" in rotor
    assert "SH_CalculateReportInputs wb" in rotor
    assert "wb.Calculate" not in rotor
    assert 'Stage [" & stage & "]' in rotor


def test_live_repair_preserves_shared_journal_boundary() -> None:
    report = _source("modShiftHelperReport.bas")
    generation = _source("modShiftHelperGeneration.bas")
    calendar = _source("modShiftHelperCalendar.bas")
    rotor = _source("modShiftHelperRotor.bas")

    combined = report + generation + calendar + rotor
    assert "VBProject" not in combined
    assert "ActiveX" not in combined
    assert "SaveAs Filename:=wb." not in combined
