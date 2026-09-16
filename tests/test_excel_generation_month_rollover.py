from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VBA_DIR = ROOT / "packaging" / "excel_addin" / "vba"


def _read(name: str) -> str:
    return (VBA_DIR / name).read_text(encoding="ascii")


def test_generation_is_bucketed_by_actual_generation_day() -> None:
    source = _read("modShiftHelperGenProfiles.bas")

    assert 'factDate = DateAdd("d", -1, DateValue(reportDate))' in source
    assert 'oldFactDate = DateAdd("d", -1, DateValue(oldDate))' in source
    assert "main.Cells(Month(factDate) + 4, 10).Value2 = monthGeneration" in source


def test_generation_month_total_resets_on_real_month_boundary() -> None:
    source = _read("modShiftHelperGenProfiles.bas")

    assert "DateValue(oldDate) = DateValue(reportDate)" in source
    assert "Year(oldFactDate) = Year(factDate)" in source
    assert "Month(oldFactDate) = Month(factDate)" in source
    assert "monthGeneration = monthGeneration + daily" in source
    assert "monthGeneration = daily" in source
    station = _read("modShiftHelperStationImport.bas")
    assert "SH_StoreStationMonthFact wb, stationId, factDate" in station


def test_cancelled_or_missing_import_cannot_reuse_stale_daily_values() -> None:
    station = _read("modShiftHelperStationImport.bas")
    assert "If Not SH_ImportGenerationUniversalCore(stationHint) Then GoTo CleanExit" in station
    assert "SH_StoreStationMonthFact" in station
    assert station.index("SH_ImportGenerationUniversalCore") < station.index(
        "SH_StoreStationMonthFact"
    )


def test_completed_month_history_is_not_hard_limited_to_july() -> None:
    source = _read("modShiftHelperStationFacts.bas")

    prefix = 'Private Const SH_MONTH_FACT_PREFIX As String = "report.generation.month_fact."'
    assert prefix in source
    assert "lastKnownMonth = Month(reportDate) - 1" in source
    assert "Application.Min(7, Month(reportDate) - 1)" not in source
    assert "SH_TryStoredStationMonthFact" in source
    assert "raw = main.Cells(monthIndex + 4, 10).Value2" in source
    assert "SH_StoreStationMonthFact" in source


def test_month_rollover_vba_remains_ascii_safe() -> None:
    _read("modShiftHelperStationImport.bas")
    _read("modShiftHelperStationFacts.bas")
