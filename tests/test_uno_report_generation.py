from datetime import date, time

import pytest

from shift_helper.uno_adapter.report_generation import (
    default_report_filename,
    normalize_event_row,
    parse_report_date,
    read_uno_journal,
    update_report_title,
)


def _headers(**overrides):
    values = {
        "B": "Дата останова ВЭУ",
        "C": "Время останова ВЭУ",
        "D": "40",
        "E": "Описание",
        "F": "Причины возникновения",
        "I": "Дата пуска ВЭУ",
        "J": "Время пуска ВЭУ",
    }
    values.update(overrides)
    return values


def _row(day=date(2026, 7, 26), clock=time(10, 15), asset=40, **overrides):
    values = {
        "B": day,
        "C": clock,
        "D": asset,
        "E": "Авария - ошибка в работе",
        "F": "Перегрев",
        "I": None,
        "J": None,
    }
    values.update(overrides)
    return values


def test_parse_report_date_accepts_ru_and_iso() -> None:
    expected = date(2026, 7, 27)
    assert parse_report_date("27.07.2026") == expected
    assert parse_report_date("2026-07-27") == expected


def test_parse_report_date_rejects_impossible_date() -> None:
    with pytest.raises(ValueError, match="ДД.ММ.ГГГГ"):
        parse_report_date("31.02.2026")


def test_output_name_and_title_use_report_date() -> None:
    report_date = date(2026, 7, 27)
    assert default_report_filename(report_date) == (
        "Рапорт НСС Кочубеевская ВЭС от 2026-07-27.xlsx"
    )
    assert update_report_title("Рапорт на 30.07.2026", report_date) == (
        "Рапорт на 27.07.2026"
    )


def test_normalize_event_row_matches_journal_contract() -> None:
    event, issues = normalize_event_row(3794, _row())
    assert event is not None
    assert event.source_row == 3794
    assert event.dispatch_name == "ВЭУ №40"
    assert event.started_at.strftime("%d.%m.%Y %H:%M") == "26.07.2026 10:15"
    assert issues == []


def test_partial_end_is_ignored_with_error() -> None:
    event, issues = normalize_event_row(10, _row(I=date(2026, 7, 26)))
    assert event is None
    assert [issue.code for issue in issues] == ["journal.row.partial_end"]


def test_known_leading_outlier_is_excluded() -> None:
    result = read_uno_journal(
        headers=_headers(),
        rows=[
            (2, _row(day=date(2026, 2, 20), asset=1)),
            (3, _row(day=date(2026, 1, 1), asset=2)),
            (4, _row(day=date(2026, 1, 2), asset=3)),
        ],
    )
    assert [event.source_row for event in result.events] == [3, 4]
    assert result.ignored_rows == [2]
    assert any(
        issue.code == "journal.row.leading_chronology_outlier"
        for issue in result.issues
    )
    assert any(issue.code == "journal.header.asset_mismatch" for issue in result.issues)


def test_structural_header_error_blocks_report() -> None:
    result = read_uno_journal(headers=_headers(B="Дата"), rows=[])
    assert [issue.code for issue in result.blocking_structure_errors] == [
        "journal.header.mismatch"
    ]
