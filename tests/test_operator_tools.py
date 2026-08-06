from datetime import datetime

import pytest

from shift_helper.core.operator_tools import (
    absolute_a1_references,
    active_rotor_limits,
    inspection_message,
    inspection_shift,
    maintenance_text,
    merge_nonempty,
    normalize_spaces,
    parse_wtg_numbers,
    rotor_repair_power,
    russian_year_word,
    sort_key_for_time,
)


def test_normalize_and_merge_text() -> None:
    assert normalize_spaces("  A\tB\r\nC\u00a0 D  ") == "A B C D"
    assert merge_nonempty([" A ", "", None, "B\nC"]) == "A B C"


@pytest.mark.parametrize(
    ("number", "word"),
    [(1, "год"), (2, "года"), (5, "лет"), (11, "лет"), (22, "года")],
)
def test_russian_year_word(number: int, word: str) -> None:
    assert russian_year_word(number) == word


def test_parse_wtg_numbers_deduplicates_and_validates() -> None:
    assert parse_wtg_numbers("ВЭУ-1, 2; 2 84") == [1, 2, 84]
    with pytest.raises(ValueError):
        parse_wtg_numbers("85")
    with pytest.raises(ValueError):
        parse_wtg_numbers("ВЭУ-X")


def test_maintenance_text_preserves_legacy_wording() -> None:
    half_year = maintenance_text(54, half_year=True)
    assert half_year.startswith("ВЭУ-54: базовая платформа")
    assert "ТО-6 месяцев" in half_year
    years = maintenance_text(54, years=5, bolt_torque_check=True)
    assert "ТО 5 лет" in years
    assert "проверка моментов затяжки" in years


@pytest.mark.parametrize(
    ("limit_value", "repair"),
    [
        (0.65, 2.5),
        (0.70, 1.4),
        (0.75, 1.2),
        (0.80, 1.0),
        (0.85, 0.75),
        (0.90, 0.55),
        (0.92, 0.45),
        (0.95, 0.0),
    ],
)
def test_rotor_repair_mapping(limit_value: float, repair: float) -> None:
    assert rotor_repair_power(limit_value) == repair


def test_active_rotor_limits_honours_later_removal() -> None:
    end = datetime(2026, 8, 7, 7)
    rows = [
        (
            datetime(2026, 8, 6, 8),
            1,
            "Установлено ограничение по оборотам 0,85",
        ),
        (datetime(2026, 8, 6, 12), 2, "Установлено ограничение оборотов 0.9"),
        (datetime(2026, 8, 6, 20), 1, "Снято ограничение по оборотам"),
        (datetime(2026, 8, 7, 8), 3, "Установлено ограничение оборотов 0,8"),
    ]
    active = active_rotor_limits(rows, end_time=end)
    assert set(active) == {2}
    assert active[2].limit_value == 0.9


def test_absolute_formula_conversion_skips_function_names() -> None:
    formula = "=K5+N6+SUM(A1:B2)+LOG10(A1)"
    assert absolute_a1_references(formula) == (
        "=$K$5+$N$6+SUM($A$1:$B$2)+LOG10($A$1)"
    )


def test_time_sort_key() -> None:
    assert sort_key_for_time(0.5) < sort_key_for_time("abc")
    assert sort_key_for_time("07:30") < sort_key_for_time("12:00")
    assert sort_key_for_time("")[0] == 2


def test_inspection_shift_and_message() -> None:
    daytime = datetime(2026, 8, 6, 11, 0)
    assert inspection_shift(daytime) == ("Д", "с 08:00 до 20:00")
    message = inspection_message(daytime, [("5", "12", None)])
    assert "смена Д" in message
    assert "М.К. 5 > КТП {12}" in message
