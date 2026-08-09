"""Bring the LibreOffice Calc client to the accepted Excel-client contract."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import uno
import unohelper
from com.sun.star.util import XModifyListener

STATION_META = "Станция рапорта"
STATION_KOCH = 1
STATION_KUZ = 2
STATION_NAMES = {
    STATION_KOCH: "Кочубеевская ВЭС",
    STATION_KUZ: "Кузьминская ВЭС",
}
STATION_WTG_COUNTS = {STATION_KOCH: 84, STATION_KUZ: 64}
STATION_STATE_LAST_ROWS = {STATION_KOCH: 98, STATION_KUZ: 74}
STATION_GROUPS = {
    STATION_KOCH: (
        (45, 52, "GVIE0532"),
        (5, 12, "GVIE0534"),
        (13, 20, "GVIE0536"),
        (21, 28, "GVIE0537"),
        (29, 36, "GVIE0538"),
        (37, 44, "GVIE0539"),
        (61, 68, "GVIE0570"),
        (53, 60, "GVIE0571"),
        (69, 76, "GVIE0573"),
        (77, 84, "GVIE0580"),
        (1, 4, "GVIE0891"),
    ),
    STATION_KUZ: (
        (1, 16, "GVIE0531"),
        (17, 24, "GVIE0555"),
        (25, 32, "GVIE0546"),
        (33, 40, "GVIE0543"),
        (41, 48, "GVIE0547"),
        (49, 56, "GVIE0549"),
        (57, 64, "GVIE0545"),
    ),
}
STATION_PLANS_2026 = {
    STATION_KOCH: (
        51934734,
        44351219,
        60732317,
        52076610,
        40421364,
        27046328,
        27830685,
        43191351,
        37219013,
        70499769,
        54347599,
        60625012,
    ),
    STATION_KUZ: (
        36814159,
        33290612,
        45586481,
        39089392,
        30340811,
        20301332,
        20890080,
        31380024,
        27937084,
        52918060,
        40794027,
        45505936,
    ),
}
STATION_FACTS_2026 = {
    STATION_KOCH: (
        49433027,
        60472425,
        47415807,
        30086974,
        33242664,
        12914362,
        14234957,
    ),
    STATION_KUZ: (
        30154342,
        33176283,
        33173000,
        21151677,
        29470109,
        11951418,
        13003670,
    ),
}
STATUSES = ("Работа", "Останов", "Авария", "Ремонт")
REPORT_INPUTS = (
    "Ввод - Основные",
    "Ввод - Аварийные отключения",
    "Ввод - Команды",
    "Ввод - Нарушения",
    "Ввод - Состояние ВЭУ",
    "Ввод - Работы",
    "Ввод - Дефекты",
)
REPORT_OUTPUTS = (
    "Основные данные",
    "Аварийные отключения ЛЭП",
    "Команды по внешней инициативе",
    "Нарушения ОТиПБ + Экология",
    "Состояние ВЭУ",
    "Запланированные работы",
    "Дефекты оборудования",
)
REPORT_TITLES = (
    "",
    "Аварийные отключения ЛЭП на ",
    "Команды по внешней инициативе на ",
    "Нарушения ОТиПБ + Экология на ",
    "Состояние ВЭУ на ",
    "Запланированные работы на ",
    "Дефекты оборудования на ",
)
OUTPUT_OFFSETS = {
    1: ((2, 5), 3),
    2: ((4, 5), 3),
    3: ((3,), 2),
    4: ((9, 10), 3),
    5: ((8, 9), 3),
    6: ((2, 8, 9), 3),
}
MAIL_SPECS = {
    "list:1": ("list", 1, False),
    "list:2": ("list", 2, False),
    "list:3": ("list", 3, False),
    "morning": ("morning", 0, False),
    "foreign-list:1": ("list", 1, True),
    "foreign-list:2": ("list", 2, True),
    "foreign-list:3": ("list", 3, True),
    "foreign-morning": ("morning", 0, True),
    "foreign-sheet": ("foreign", 0, True),
}


def _cell(sheet, address: str):
    return sheet.getCellRangeByName(address)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _sheet_text(sheet, address: str) -> str:
    return str(_cell(sheet, address).getString()).strip()


def _station_from_text(value: str) -> int:
    normalized = unquote(str(value)).casefold()
    if "кузвэс" in normalized or "кузьмин" in normalized or "кузмин" in normalized:
        return STATION_KUZ
    if "квэс" in normalized or "кочуб" in normalized:
        return STATION_KOCH
    return 0


def _ensure_prep(runtime, document):
    sheets = document.getSheets()
    if sheets.hasByName(runtime.INPUT_PREP):
        return sheets.getByName(runtime.INPUT_PREP)
    prep, created = runtime._ensure_sheet(document, runtime.INPUT_PREP)
    runtime._setup_prep(document, prep, created)
    return prep


def _meta(module, runtime, document, key: str, value=...):
    _ensure_prep(runtime, document)
    return module._meta(runtime, document, key, value)


def _station_id(module, runtime, document, *, required: bool = True) -> int:
    try:
        raw = _meta(module, runtime, document, STATION_META)
    except Exception:
        raw = None
    if isinstance(raw, (int, float)) and int(raw) in STATION_NAMES:
        return int(raw)
    detected = _station_from_text(_text(raw))
    if detected:
        return detected

    candidates = [str(getattr(document, "URL", ""))]
    get_url = getattr(document, "getURL", None)
    if callable(get_url):
        try:
            candidates.append(str(get_url()))
        except Exception:
            pass
    sheets = document.getSheets()
    for name, addresses in (
        (runtime.INPUT_MAIN, ("B1", "H3")),
        (runtime.INPUT_STATE, ("B1", "B4")),
    ):
        if not sheets.hasByName(name):
            continue
        sheet = sheets.getByName(name)
        candidates.extend(_sheet_text(sheet, address) for address in addresses)
    for candidate in candidates:
        detected = _station_from_text(candidate)
        if detected:
            _meta(module, runtime, document, STATION_META, float(detected))
            return detected
    if required:
        raise RuntimeError(
            "Не удалось определить станцию. Выберите в Shift-Helper: "
            "«Кочубеевская ВЭС» или «Кузьминская ВЭС»."
        )
    return 0


def _report_date(runtime, document) -> date:
    value, _offset = runtime._prep_settings(document)
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise RuntimeError("Дата рапорта не задана.")


def _sync_report_window(runtime, document) -> date:
    prep = _ensure_prep(runtime, document)
    report_date = _report_date(runtime, document)
    runtime._refresh_prep_window(document, prep, report_date)
    return report_date


def _expected_assets(station_id: int) -> list[str]:
    return [
        f"ВЭУ-{number}"
        for start, end, _code in STATION_GROUPS[station_id]
        for number in range(start, end + 1)
    ]


def _layout_matches(runtime, state, station_id: int) -> bool:
    assets: list[str] = []
    codes: list[str] = []
    last = max(runtime._last_used_row(state), 97)
    for row in range(3, last + 1):
        name = str(state.getCellByPosition(3, row).getString()).strip()
        code = str(state.getCellByPosition(2, row).getString()).strip()
        if name.startswith("ВЭУ-"):
            assets.append(name)
        elif code:
            codes.append(code)
    expected_codes = [item[2] for item in STATION_GROUPS[station_id]]
    return assets == _expected_assets(station_id) and codes[: len(expected_codes)] == expected_codes


def _state_snapshot(runtime, document, state) -> dict[str, tuple[object, ...]]:
    result: dict[str, tuple[object, ...]] = {}
    last = max(runtime._last_used_row(state), 97)
    for row in range(3, last + 1):
        name = str(state.getCellByPosition(3, row).getString()).strip()
        if not name.startswith("ВЭУ-"):
            continue
        result[name] = (
            runtime._cell_value(state.getCellByPosition(4, row), document),
            runtime._cell_value(state.getCellByPosition(5, row), document),
            runtime._cell_value(state.getCellByPosition(6, row), document),
            runtime._cell_value(state.getCellByPosition(8, row), document),
            runtime._cell_value(state.getCellByPosition(9, row), document),
            runtime._cell_value(state.getCellByPosition(10, row), document),
            str(state.getCellByPosition(11, row).getString()).strip(),
        )
    return result


def _clear(range_obj) -> None:
    range_obj.clearContents(1023)


def _copy_row(state, source_row: int, target_row: int) -> None:
    source = state.getCellRangeByPosition(1, source_row, 11, source_row)
    destination = uno.createUnoStruct("com.sun.star.table.CellAddress")
    destination.Sheet = source.getRangeAddress().Sheet
    destination.Column = 1
    destination.Row = target_row
    if target_row != source_row:
        state.copyRange(destination, source.getRangeAddress())
    _clear(state.getCellRangeByPosition(1, target_row, 11, target_row))


def _write(runtime, document, cell, value, format_code: str | None = None) -> None:
    runtime._write_value(cell, value, document, format_code)


def _restore_state_values(runtime, document, state, row: int, values) -> None:
    if not values:
        return
    for column, value in zip((4, 5, 6), values[:3], strict=True):
        if value not in (None, ""):
            _write(runtime, document, state.getCellByPosition(column, row), value)
    for column, value in zip((8, 9, 10), values[3:6], strict=True):
        if value in (None, ""):
            continue
        code = "DD.MM.YYYY HH:MM" if column == 9 else None
        _write(runtime, document, state.getCellByPosition(column, row), value, code)
    status = _text(values[6])
    if status in STATUSES:
        state.getCellByPosition(11, row).setString(status)


def _rebuild_state(runtime, document, state, station_id: int) -> None:
    snapshot = _state_snapshot(runtime, document, state)
    try:
        state.getCellRangeByPosition(1, 3, 2, 219).merge(False)
    except Exception:
        pass
    group_height = state.getRows().getByIndex(3).Height
    child_height = state.getRows().getByIndex(4).Height
    _clear(state.getCellRangeByPosition(1, 3, 11, 219))

    row = 3
    station_name = STATION_NAMES[station_id]
    for start, end, code in STATION_GROUPS[station_id]:
        group_row = row
        _copy_row(state, 3, group_row)
        try:
            state.getRows().getByIndex(group_row).Height = group_height
        except Exception:
            pass
        state.getCellByPosition(1, group_row).setString(
            f"{station_name} (ВЭУ{start}-ВЭУ{end})"
        )
        state.getCellByPosition(2, group_row).setString(code)
        state.getCellByPosition(4, group_row).setValue((end - start + 1) * 2.5)
        row += 1
        for number in range(start, end + 1):
            _copy_row(state, 4, row)
            try:
                state.getRows().getByIndex(row).Height = child_height
            except Exception:
                pass
            name = f"ВЭУ-{number}"
            state.getCellByPosition(3, row).setString(name)
            state.getCellByPosition(4, row).setValue(2.5)
            state.getCellByPosition(5, row).setValue(2.5)
            state.getCellByPosition(6, row).setValue(0.0)
            excel_row = row + 1
            state.getCellByPosition(7, row).setFormula(
                f"=MAX(F{excel_row}-G{excel_row};0)"
            )
            state.getCellByPosition(11, row).setString("Работа")
            _restore_state_values(runtime, document, state, row, snapshot.get(name))
            row += 1
        last_child = row - 1
        for column in (1, 2):
            block = state.getCellRangeByPosition(
                column,
                group_row,
                column,
                last_child,
            )
            try:
                block.merge(True)
            except Exception:
                pass
            try:
                block.setPropertyValue(
                    "HoriJustify",
                    uno.Enum("com.sun.star.table.CellHoriJustify", "CENTER"),
                )
                block.setPropertyValue(
                    "VertJustify",
                    uno.Enum("com.sun.star.table.CellVertJustify", "CENTER"),
                )
                block.setPropertyValue("IsTextWrapped", True)
            except Exception:
                pass

    expected_last = STATION_STATE_LAST_ROWS[station_id] - 1
    if row - 1 != expected_last:
        raise RuntimeError("Количество строк профиля ВЭУ не совпало с контрактом.")
    for index in range(3, 98):
        try:
            state.getRows().getByIndex(index).IsVisible = index <= expected_last
        except Exception:
            pass


def _apply_station_titles(runtime, document, station_id: int) -> None:
    sheets = document.getSheets()
    main = sheets.getByName(runtime.INPUT_MAIN)
    station = STATION_NAMES[station_id]
    prep = "'Подготовка рапорта'"
    if station_id == STATION_KUZ:
        _cell(main, "B1").setFormula(
            '=CONCATENATE("Рапорт НСС на ";'
            f'TEXT({prep}.B3;"DD.MM.YYYY");" {station}. Последние изменения ";'
            'TEXT(NOW();"DD.MM.YYYY, HH:MM:SS"))'
        )
    else:
        _cell(main, "B1").setFormula(
            '=CONCATENATE("Рапорт НСС на ";'
            f'TEXT({prep}.B3;"DD.MM.YYYY");" {station} (";'
            f'{prep}.B7;"). Последние изменения ";'
            'TEXT(NOW();"DD.MM.YYYY, HH:MM:SS"))'
        )
    _cell(main, "H3").setFormula(
        f'=CONCATENATE("План/Факт {station} ";YEAR({prep}.B3))'
    )
    for index, name in enumerate(REPORT_INPUTS[1:], start=1):
        if not sheets.hasByName(name):
            continue
        sheet = sheets.getByName(name)
        title = REPORT_TITLES[index]
        _cell(sheet, "B1").setFormula(
            f'=CONCATENATE("{title}";TEXT({prep}.B3;"DD.MM.YYYY");'
            f'" {station}")'
        )


def _apply_plans_and_facts(runtime, document, station_id: int) -> None:
    main = document.getSheets().getByName(runtime.INPUT_MAIN)
    for month, value in enumerate(STATION_PLANS_2026[station_id], start=1):
        main.getCellByPosition(8, month + 3).setValue(float(value))
    report_date = _report_date(runtime, document)
    if report_date.year != 2026:
        return
    last_known = min(7, report_date.month - 1)
    for month in range(1, last_known + 1):
        main.getCellByPosition(9, month + 3).setValue(
            float(STATION_FACTS_2026[station_id][month - 1])
        )


def _apply_station_formulas(runtime, document, station_id: int) -> None:
    main = document.getSheets().getByName(runtime.INPUT_MAIN)
    last_row = STATION_STATE_LAST_ROWS[station_id]
    for row, status in zip(range(4, 8), ("Останов", "Работа", "Авария", "Ремонт"), strict=True):
        _cell(main, f"F{row}").setFormula(
            f'=COUNTIF(\'Ввод - Состояние ВЭУ\'.L4:L{last_row};"{status}")'
        )
    try:
        document.calculateAll()
    except Exception:
        pass


def _apply_station_profile(module, runtime, document, station_id: int) -> None:
    sheets = document.getSheets()
    if not sheets.hasByName(runtime.INPUT_STATE):
        return
    state = sheets.getByName(runtime.INPUT_STATE)
    if not _layout_matches(runtime, state, station_id):
        _rebuild_state(runtime, document, state, station_id)
    _apply_plans_and_facts(runtime, document, station_id)
    module._apply_formulas(runtime, document)
    _apply_station_titles(runtime, document, station_id)
    _apply_station_formulas(runtime, document, station_id)


def _set_station(module, runtime, station_id: int) -> None:
    if station_id not in STATION_NAMES:
        raise RuntimeError("Неизвестный профиль станции.")
    document = runtime._document()
    _ensure_prep(runtime, document)
    _meta(module, runtime, document, STATION_META, float(station_id))
    if not document.getSheets().hasByName(runtime.INPUT_MAIN):
        runtime._CALC_PARITY_ORIGINAL_PREPARE()
    _sync_report_window(runtime, document)
    _apply_station_profile(module, runtime, document, station_id)
    _install_window_listener(module, runtime, document)
    _install_mail_buttons(module, runtime, document)
    runtime._message(f"Станция рапорта установлена: {STATION_NAMES[station_id]}.")


class _ReportWindowListener(unohelper.Base, XModifyListener):
    def __init__(self, module, runtime, document) -> None:
        self.module = module
        self.runtime = runtime
        self.document = document
        self.guard = False
        self.last_date = self._current()

    def _current(self):
        try:
            return _report_date(self.runtime, self.document)
        except Exception:
            return None

    def modified(self, _event) -> None:
        if self.guard:
            return
        current = self._current()
        if current is None or current == self.last_date:
            return
        self.guard = True
        try:
            self.last_date = current
            _sync_report_window(self.runtime, self.document)
            station_id = _station_id(
                self.module,
                self.runtime,
                self.document,
                required=False,
            )
            if station_id:
                _apply_station_profile(
                    self.module,
                    self.runtime,
                    self.document,
                    station_id,
                )
        finally:
            self.guard = False

    def disposing(self, _event) -> None:
        return None


def _install_window_listener(module, runtime, document) -> None:
    previous = getattr(runtime, "_CALC_PARITY_WINDOW_LISTENER", None)
    if previous is not None and getattr(previous, "document", None) is document:
        return
    if previous is not None:
        try:
            previous.document.removeModifyListener(previous)
        except Exception:
            pass
    listener = _ReportWindowListener(module, runtime, document)
    document.addModifyListener(listener)
    runtime._CALC_PARITY_WINDOW_LISTENER = listener


def _parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _numeric(cell) -> float | None:
    try:
        value = float(cell.getValue())
    except Exception:
        return None
    text = str(cell.getString()).strip()
    formula = str(cell.getFormula()).strip()
    if not text and not formula and value == 0.0:
        return None
    return value


def _read_generation(runtime, path: Path, expected_date: date) -> tuple[float, float, str]:
    source = runtime._open_hidden(path, read_only=True)
    try:
        for _pass in range(2):
            try:
                source.calculateAll()
            except Exception:
                pass
        sheets = source.getSheets()
        if not sheets.hasByName("Сумма ВЭС"):
            raise RuntimeError("В файле генерации отсутствует лист «Сумма ВЭС».")
        sheet = sheets.getByName("Сумма ВЭС")
        j1 = _sheet_text(sheet, "J1").casefold()
        z1 = _sheet_text(sheet, "Z1").casefold()
        daily: float | None = None
        own: float | None = None
        profile = ""
        if "сумма по вэс" in j1 and "потреблен" in z1:
            daily = _numeric(_cell(sheet, "J26"))
            own = _numeric(_cell(sheet, "Z26"))
            if daily is not None and own is not None:
                profile = "kuz"
        if not profile:
            candidate_daily = _numeric(_cell(sheet, "G26"))
            candidate_own = _numeric(_cell(sheet, "Q26"))
            numeric_rows = sum(
                _numeric(_cell(sheet, f"Q{row}")) is not None
                for row in range(2, 26)
            )
            if candidate_daily is not None and candidate_own is not None and numeric_rows >= 20:
                daily = candidate_daily
                own = candidate_own
                profile = "kves"
        if not profile or daily is None or own is None:
            raise RuntimeError(
                "Файл генерации не соответствует форме Кочубеевской или Кузьминской ВЭС."
            )
        source_date = _parse_date(runtime._cell_value(_cell(sheet, "A2"), source))
        if source_date is not None and source_date != expected_date:
            raise RuntimeError("Дата файла генерации не соответствует суткам рапорта.")
        daily = float(round(daily))
        own = float(round(own))
        if not 0 <= daily <= 20_000_000:
            raise RuntimeError("Суточная генерация вне допустимого диапазона.")
        if not 0 <= own <= 5_000_000:
            raise RuntimeError("Собственные нужды вне допустимого диапазона.")
        return daily, own, profile
    finally:
        runtime._close(source)


def _ps(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _setting(module, runtime, document, key: str, default):
    try:
        value = _meta(module, runtime, document, key)
    except Exception:
        value = None
    return default if value in (None, "") else value


def _outlook_attachment(module, runtime, document, report_date: date, station_id: int):
    if os.name != "nt":
        return None, "Outlook COM доступен только в Windows."
    mailbox = str(
        _setting(module, runtime, document, "Outlook: почтовый ящик", "НСС Кочубеевская ВЭС")
    )
    folder_path = str(_setting(module, runtime, document, "Outlook: папка", "Входящие"))
    pattern = str(
        _setting(
            module,
            runtime,
            document,
            "Outlook: маска вложения",
            "Генерация КВЭС за вчера_{date}.xlsx",
        )
    ).replace("{date}", (report_date - timedelta(days=1)).strftime("%d_%m_%Y"))
    subject = str(_setting(module, runtime, document, "Outlook: тема содержит", ""))
    sender = str(_setting(module, runtime, document, "Outlook: отправитель содержит", ""))
    days = int(
        max(
            1,
            min(
                60,
                float(
                    _setting(
                        module,
                        runtime,
                        document,
                        "Outlook: глубина поиска, дней",
                        7,
                    )
                ),
            ),
        )
    )
    station = "kuz" if station_id == STATION_KUZ else "kves"
    expected_token = (report_date - timedelta(days=1)).strftime("%d_%m_%Y")
    cutoff = report_date - timedelta(days=days)
    target_dir = Path(tempfile.gettempdir()) / "ShiftHelper"
    target_dir.mkdir(parents=True, exist_ok=True)
    script = f"""
$ErrorActionPreference = 'Stop'
$mailbox = {_ps(mailbox)}
$folderPath = {_ps(folder_path)}
$pattern = {_ps(pattern)}
$subjectFilter = {_ps(subject)}
$senderFilter = {_ps(sender)}
$station = {_ps(station)}
$expected = {_ps(expected_token)}
$targetDir = {_ps(target_dir)}
$cutoff = [datetime]{_ps(cutoff.isoformat())}
function Station-Match([string]$name) {{
  $n = $name.ToLowerInvariant()
  if ($station -eq 'kuz') {{ return ($n.Contains('кузвэс') -or $n.Contains('кузьмин') -or $n.Contains('кузмин')) }}
  return ($n.Contains('квэс') -or $n.Contains('кочуб'))
}}
function Fallback-Match([string]$name) {{
  if (-not $name.ToLowerInvariant().EndsWith('.xlsx')) {{ return $false }}
  $n = $name.ToLowerInvariant().Replace([char]0xA0, ' ').Replace('.', '_').Replace('-', '_').Replace(' ', '_')
  while ($n.Contains('__')) {{ $n = $n.Replace('__', '_') }}
  return ($n.Contains($expected) -and $n.Contains('генерац') -and (Station-Match $name))
}}
$outlook = New-Object -ComObject Outlook.Application
$ns = $outlook.GetNamespace('MAPI')
$root = $null
$inbox = $null
try {{ if ($mailbox) {{ $root = $ns.Folders.Item($mailbox) }} }} catch {{}}
try {{
  if ($mailbox) {{
    $recip = $ns.CreateRecipient($mailbox)
    $recip.Resolve() | Out-Null
    if ($recip.Resolved) {{ $inbox = $ns.GetSharedDefaultFolder($recip, 6) }}
  }}
}} catch {{}}
try {{ if ($null -eq $inbox -and $null -ne $root) {{ $inbox = $root.Store.GetDefaultFolder(6) }} }} catch {{}}
if ($null -eq $inbox) {{ $inbox = $ns.GetDefaultFolder(6) }}
$folder = $inbox
$parts = @($folderPath -split '[\\/]') | Where-Object {{ $_ -and $_.Trim() }}
if ($parts.Count -gt 0) {{
  $first = $parts[0].Trim()
  $start = 0
  if ($first -ieq 'Inbox' -or $first -ieq 'Входящие' -or $first -ieq $inbox.Name) {{ $start = 1 }}
  for ($i = $start; $i -lt $parts.Count; $i++) {{ $folder = $folder.Folders.Item($parts[$i]) }}
}}
$items = $folder.Items
$items.Sort('[ReceivedTime]', $true)
$messages = 0; $attachments = 0; $xlsx = 0; $samples = New-Object System.Collections.Generic.List[string]
foreach ($item in $items) {{
  try {{
    if ($item.ReceivedTime -lt $cutoff) {{ break }}
    $messages++
    if ($subjectFilter -and ($item.Subject -notlike ('*' + $subjectFilter + '*'))) {{ continue }}
    $senderText = (($item.SenderName | Out-String) + ' ' + ($item.SenderEmailAddress | Out-String))
    if ($senderFilter -and ($senderText -notlike ('*' + $senderFilter + '*'))) {{ continue }}
    foreach ($att in $item.Attachments) {{
      $attachments++
      $name = [string]$att.FileName
      if ($name.ToLowerInvariant().EndsWith('.xlsx')) {{
        $xlsx++
        if ($samples.Count -lt 6) {{ $samples.Add($name) }}
        $exact = ($name -like $pattern) -and (Station-Match $name)
        if ($exact -or (Fallback-Match $name)) {{
          $target = Join-Path $targetDir $name
          if (Test-Path $target) {{ Remove-Item $target -Force }}
          $att.SaveAsFile($target)
          Write-Output ('FOUND::' + $target)
          exit 0
        }}
      }}
    }}
  }} catch {{}}
}}
Write-Output ('DIAG::messages=' + $messages + ';attachments=' + $attachments + ';xlsx=' + $xlsx + ';samples=' + ($samples -join ' | '))
exit 3
"""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=90,
            creationflags=flags,
            check=False,
        )
    except Exception as exc:
        return None, f"Outlook: {exc}"
    found = None
    diagnostic = ""
    for line in completed.stdout.splitlines():
        if line.startswith("FOUND::"):
            found = Path(line[7:].strip())
        elif line.startswith("DIAG::"):
            diagnostic = line[6:].strip()
    details = (
        f"Mailbox: {mailbox}\nFolder: {folder_path}\nStation: {STATION_NAMES[station_id]}\n"
        f"Pattern: {pattern}\nSearch from: {cutoff:%d.%m.%Y}"
    )
    if diagnostic:
        details += "\n" + diagnostic
    if completed.stderr.strip():
        details += "\nOutlook error: " + completed.stderr.strip()
    if found is not None and found.is_file():
        return found, details
    return None, details


def _import_generation(module, runtime, _args=None) -> None:
    try:
        document = runtime._document()
        if not document.getSheets().hasByName(runtime.INPUT_MAIN):
            runtime.prepare_report_input_sheets()
        station_id = _station_id(module, runtime, document)
        _sync_report_window(runtime, document)
        _apply_station_profile(module, runtime, document, station_id)
        report_date = _report_date(runtime, document)
        source, diagnostic = _outlook_attachment(
            module,
            runtime,
            document,
            report_date,
            station_id,
        )
        fallback = float(
            _setting(
                module,
                runtime,
                document,
                "Outlook: ручной выбор при отсутствии",
                1,
            )
            or 0
        )
        if source is None and fallback:
            source = runtime._EXACT_ORIGINAL_PICK_XLSX(
                "Вложение Outlook не найдено. Выберите файл генерации вручную"
            )
        if source is None:
            runtime._message("Подходящее вложение не найдено.\n\n" + diagnostic)
            return
        source = Path(source)
        daily, own, profile = _read_generation(
            runtime,
            source,
            report_date - timedelta(days=1),
        )
        expected_profile = "kuz" if station_id == STATION_KUZ else "kves"
        if profile != expected_profile:
            raise RuntimeError(
                "Выбран файл генерации другой станции: "
                f"ожидалась {STATION_NAMES[station_id]}."
            )
        main = document.getSheets().getByName(runtime.INPUT_MAIN)
        values = runtime._main_map(main, document)
        old_date = values.get("Последняя дата импорта генерации")
        if isinstance(old_date, datetime):
            old_date = old_date.date()
        old_daily = float(values.get("Последняя выработка за сутки") or 0)
        old_own = float(values.get("Последние собственные нужды за сутки") or 0)
        month_generation = float(values.get("Выработка с начала месяца, кВт*ч") or 0)
        month_own = float(values.get("Собственные нужды с начала месяца, кВт*ч") or 0)
        if isinstance(old_date, date) and old_date == report_date:
            month_generation += daily - old_daily
            month_own += own - old_own
        elif (
            isinstance(old_date, date)
            and old_date.year == report_date.year
            and old_date.month == report_date.month
        ):
            month_generation += daily
            month_own += own
        elif report_date.day <= 2:
            month_generation, month_own = daily, own
        else:
            month_generation += daily
            month_own += own
        updates = {
            "Выработка за предыдущие сутки, кВт*ч": daily,
            "Выработка с начала месяца, кВт*ч": month_generation,
            "Собственные нужды за сутки, кВт*ч": own,
            "Собственные нужды с начала месяца, кВт*ч": month_own,
            "Последний файл генерации": source.name,
            "Последняя дата импорта генерации": report_date,
            "Последняя выработка за сутки": daily,
            "Последние собственные нужды за сутки": own,
        }
        for key, value in updates.items():
            runtime._set_main_value(main, key, value, document)
        main.getCellByPosition(9, report_date.month + 3).setValue(month_generation)
        _apply_station_profile(module, runtime, document, station_id)
        runtime._message(
            "Генерация импортирована.\n"
            f"Станция: {STATION_NAMES[station_id]}.\n"
            f"Выработка: {daily:.0f} кВт*ч.\n"
            f"Средняя нагрузка: {daily / 24000:.2f} МВт.\n"
            f"Собственные нужды: {own:.0f} кВт*ч.\n"
            f"Источник: {source.name}"
        )
    except Exception as exc:
        runtime._message(f"Не удалось импортировать генерацию: {exc}", error=True)


def _refresh_outages(runtime, document) -> None:
    sheets = document.getSheets()
    if not sheets.hasByName(runtime.INPUT_OUTAGES):
        return
    report_date = _report_date(runtime, document)
    journal = runtime._read_journal(document)
    if journal.blocking_structure_errors:
        return
    selection = runtime.select_emergency_events(journal.events, report_date)
    target = sheets.getByName(runtime.INPUT_OUTAGES)
    runtime._clear_data(target, 3, 1, 5)
    rows = [
        (
            event.dispatch_name,
            event.started_at,
            event.reason,
            event.description,
            event.ended_at,
        )
        for event in selection.selected_events
    ]
    runtime._write_matrix_rows(
        target,
        3,
        1,
        rows,
        document,
        date_cols=(1, 4),
        time_offset_hours=0.0,
    )


def _used_data(sheet):
    cursor = sheet.createCursor()
    cursor.gotoEndOfUsedArea(True)
    address = cursor.getRangeAddress()
    data_range = sheet.getCellRangeByPosition(
        address.StartColumn,
        address.StartRow,
        address.EndColumn,
        address.EndRow,
    )
    return address, data_range.getDataArray()


def _freeze_imported(target, address, data) -> None:
    target.getCellRangeByPosition(
        address.StartColumn,
        address.StartRow,
        address.EndColumn,
        address.EndRow,
    ).setDataArray(data)


def _shift_output_sheet(sheet, columns: tuple[int, ...], first_row: int, offset: float) -> None:
    cursor = sheet.createCursor()
    cursor.gotoEndOfUsedArea(True)
    last_row = cursor.getRangeAddress().EndRow
    for column in columns:
        for row in range(first_row, last_row + 1):
            cell = sheet.getCellByPosition(column, row)
            if not str(cell.getString()).strip():
                continue
            try:
                value = float(cell.getValue())
            except Exception:
                continue
            if value != 0.0:
                cell.setValue(value + offset / 24.0)


def _property(name: str, value):
    prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    prop.Name = name
    prop.Value = value
    return prop


def _register_generated_report(module, runtime, document, path: Path, station_id: int) -> None:
    sheets = document.getSheets()
    if not sheets.hasByName("Рапорт утро"):
        return
    sheet = sheets.getByName("Рапорт утро")
    sheet.getCellRangeByName("B10").setString(str(path))
    if station_id == STATION_KUZ:
        sheet.getCellRangeByName("B23").setString(str(path))


def _generate_report(module, runtime, _args=None) -> None:
    output_document = None
    try:
        document = runtime._document()
        if not all(document.getSheets().hasByName(name) for name in REPORT_INPUTS):
            runtime.prepare_report_input_sheets()
        station_id = _station_id(module, runtime, document)
        report_date = _sync_report_window(runtime, document)
        _apply_station_profile(module, runtime, document, station_id)
        _refresh_outages(runtime, document)
        _apply_station_titles(runtime, document, station_id)
        try:
            document.calculateAll()
        except Exception:
            pass
        _offset_date, offset = runtime._prep_settings(document)
        output_path = runtime._pick_output(None, report_date)
        if output_path is None:
            return
        output_path = Path(output_path).resolve()
        desktop = runtime.XSCRIPTCONTEXT.getDesktop()
        output_document = desktop.loadComponentFromURL(
            "private:factory/scalc",
            "_blank",
            0,
            (),
        )
        source_sheets = document.getSheets()
        target_sheets = output_document.getSheets()
        for input_name, output_name in zip(REPORT_INPUTS, REPORT_OUTPUTS, strict=True):
            source = source_sheets.getByName(input_name)
            address, data = _used_data(source)
            position = target_sheets.getCount()
            imported = target_sheets.importSheet(document, input_name, position)
            target = target_sheets.getByIndex(imported)
            target.setName(output_name)
            _freeze_imported(target, address, data)
        expected = set(REPORT_OUTPUTS)
        for name in tuple(target_sheets.getElementNames()):
            if name not in expected:
                target_sheets.removeByName(name)
        state = target_sheets.getByName(REPORT_OUTPUTS[4])
        try:
            if _sheet_text(state, "L3") == "Статус ВЭУ":
                state.getColumns().removeByIndex(11, 1)
        except Exception:
            pass
        if station_id == STATION_KUZ:
            try:
                state.getRows().removeByIndex(74, 24)
            except Exception:
                pass
        if float(offset) != 0.0:
            for sheet_index, (columns, first_row) in OUTPUT_OFFSETS.items():
                _shift_output_sheet(
                    target_sheets.getByName(REPORT_OUTPUTS[sheet_index]),
                    columns,
                    first_row,
                    float(offset),
                )
        names = tuple(target_sheets.getElementNames())
        if names != REPORT_OUTPUTS:
            raise RuntimeError(
                "Готовый рапорт должен содержать ровно семь листов в утверждённом порядке."
            )
        output_document.storeAsURL(
            uno.systemPathToFileUrl(str(output_path)),
            (
                _property("FilterName", "Calc MS Excel 2007 XML"),
                _property("Overwrite", True),
            ),
        )
        runtime._close(output_document)
        output_document = None
        _register_generated_report(
            module,
            runtime,
            document,
            output_path,
            station_id,
        )
        runtime._message(f"Утренний рапорт сформирован:\n{output_path}")
    except Exception as exc:
        if output_document is not None:
            try:
                runtime._close(output_document)
            except Exception:
                pass
        runtime._message(f"Не удалось сформировать рапорт: {exc}", error=True)


def _mail_cell(sheet, address: str) -> str:
    return str(_cell(sheet, address).getString())


def _normalize_recipients(value: str) -> str:
    result = value.replace("\r\n", ";").replace("\r", ";").replace("\n", ";")
    result = result.replace(",", ";")
    return ";".join(part.strip() for part in result.split(";") if part.strip())


def _mail_values(document, station_id: int, tag: str):
    kind, list_number, foreign = MAIL_SPECS[tag]
    sheets = document.getSheets()
    if foreign and station_id != STATION_KUZ:
        raise RuntimeError("Рассылка Зарубежнефти доступна только для Кузьминской ВЭС.")
    if kind == "list" and station_id == STATION_KOCH:
        if not sheets.hasByName("Рассылка"):
            raise RuntimeError("Отсутствует лист «Рассылка».")
        sheet = sheets.getByName("Рассылка")
        recipients = {1: "A8", 2: "B8", 3: "C8"}
        subjects = {1: "B2", 2: "B3", 3: "B4"}
        return {
            "sender": _mail_cell(sheet, "B1"),
            "to": _mail_cell(sheet, recipients[list_number]),
            "cc": "",
            "subject": _mail_cell(sheet, subjects[list_number]),
            "body": _mail_cell(sheet, "C2"),
            "attachment": "",
            "signature": True,
        }
    if kind == "list":
        name = f"Список рассылки №{list_number}"
        if not sheets.hasByName(name):
            raise RuntimeError(f"Отсутствует лист «{name}».")
        sheet = sheets.getByName(name)
        if foreign:
            sender, to, cc, subject = "B17", "B18", "B19", "B20"
        else:
            sender, to, cc, subject = "B4", "B5", "", "B7"
        return {
            "sender": _mail_cell(sheet, sender),
            "to": _mail_cell(sheet, to),
            "cc": _mail_cell(sheet, cc) if cc else "",
            "subject": _mail_cell(sheet, subject),
            "body": _mail_cell(sheet, "B8") + _mail_cell(sheet, "B9"),
            "attachment": _mail_cell(sheet, "B10"),
            "signature": False,
        }
    if kind == "morning":
        if not sheets.hasByName("Рапорт утро"):
            raise RuntimeError("Отсутствует лист «Рапорт утро».")
        sheet = sheets.getByName("Рапорт утро")
        if foreign:
            sender, to, cc, subject = "B17", "B18", "B19", "B20"
        else:
            sender, to, cc, subject = "B4", "B5", "", "B7"
        return {
            "sender": _mail_cell(sheet, sender),
            "to": _mail_cell(sheet, to),
            "cc": _mail_cell(sheet, cc) if cc else "",
            "subject": _mail_cell(sheet, subject),
            "body": _mail_cell(sheet, "B8") + _mail_cell(sheet, "B9"),
            "attachment": _mail_cell(sheet, "B10"),
            "signature": False,
        }
    if not sheets.hasByName("Зарубежнефть"):
        raise RuntimeError("Отсутствует лист «Зарубежнефть».")
    sheet = sheets.getByName("Зарубежнефть")
    return {
        "sender": _mail_cell(sheet, "B2"),
        "to": _mail_cell(sheet, "B3"),
        "cc": _mail_cell(sheet, "B4"),
        "subject": _mail_cell(sheet, "B5"),
        "body": _mail_cell(sheet, "B6") + _mail_cell(sheet, "B7"),
        "attachment": _mail_cell(sheet, "B10"),
        "signature": False,
    }


def _create_mail_draft(module, runtime, tag: str) -> None:
    try:
        if os.name != "nt":
            raise RuntimeError("Создание Outlook-писем поддерживается только в Windows.")
        document = runtime._document()
        station_id = _station_id(module, runtime, document)
        values = _mail_values(document, station_id, tag)
        recipient = _normalize_recipients(values["to"])
        cc_value = _normalize_recipients(values["cc"])
        subject = values["subject"].strip()
        if not recipient:
            raise RuntimeError("Не указаны получатели письма.")
        if not subject:
            raise RuntimeError("Не указана тема письма.")
        attachment = values["attachment"].strip()
        if attachment and not Path(attachment).is_file():
            raise RuntimeError(f"Вложение не найдено: {attachment}")
        body = values["body"]
        signature = bool(values["signature"])
        script = f"""
$ErrorActionPreference = 'Stop'
$outlook = New-Object -ComObject Outlook.Application
$mail = $outlook.CreateItem(0)
$sender = {_ps(values['sender'].strip())}
if ($sender) {{ $mail.SentOnBehalfOfName = $sender }}
$mail.To = {_ps(recipient)}
$mail.CC = {_ps(cc_value)}
$mail.BCC = ''
$mail.Subject = {_ps(subject)}
$mail.BodyFormat = 2
$body = {_ps(body)}
$attachment = {_ps(attachment)}
if ({'$true' if signature else '$false'}) {{
  $mail.Display()
  $text = $body.Replace("`r`n", "`r").Replace("`n", "`r")
  if ($text.Trim()) {{ $text = $text + "`r`r" }}
  if ($text.Length -gt 0) {{
    $doc = $mail.GetInspector.WordEditor
    $range = $doc.Range(0,0)
    $range.Text = $text
    $inserted = $doc.Range(0,$text.Length)
    $inserted.Font.Name = 'Arial'
    $inserted.Font.Size = 12
  }}
}} else {{
  $mail.HTMLBody = $body
  if ($attachment) {{ [void]$mail.Attachments.Add($attachment) }}
  $mail.Display()
}}
"""
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=45,
            creationflags=flags,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Outlook не создал черновик.")
    except Exception as exc:
        runtime._message(f"Не удалось создать черновик Outlook: {exc}", error=True)


def _button_form(document, sheet):
    forms = sheet.getDrawPage().getForms()
    name = "ShiftHelperMailControls"
    if forms.hasByName(name):
        return forms.getByName(name)
    form = document.createInstance("com.sun.star.form.component.Form")
    form.setPropertyValue("Name", name)
    forms.insertByName(name, form)
    return form


def _ensure_button(document, sheet, name: str, label: str, action: str, anchor: str) -> None:
    draw_page = sheet.getDrawPage()
    form = _button_form(document, sheet)
    if form.hasByName(name):
        model = form.getByName(name)
    else:
        model = document.createInstance("com.sun.star.form.component.CommandButton")
        model.setPropertyValue("Name", name)
        form.insertByName(name, model)
    model.setPropertyValue("Label", label)
    model.setPropertyValue(
        "ButtonType",
        uno.Enum("com.sun.star.form.FormButtonType", "URL"),
    )
    model.setPropertyValue(
        "TargetURL",
        f"service:ru.kves.shifthelper.calc.controls?{action}",
    )
    model.setPropertyValue("TargetFrame", "_self")
    shape = None
    for index in range(draw_page.getCount()):
        candidate = draw_page.getByIndex(index)
        try:
            control = candidate.getControl()
            if str(control.getPropertyValue("Name")) == name:
                shape = candidate
                break
        except Exception:
            continue
    if shape is None:
        shape = document.createInstance("com.sun.star.drawing.ControlShape")
        shape.setControl(model)
        draw_page.add(shape)
    anchor_cell = sheet.getCellRangeByName(anchor)
    point = uno.createUnoStruct("com.sun.star.awt.Point")
    point.X = int(anchor_cell.Position.X) + 120
    point.Y = int(anchor_cell.Position.Y) + 40
    size = uno.createUnoStruct("com.sun.star.awt.Size")
    size.Width = 4200
    size.Height = 900
    shape.setPosition(point)
    shape.setSize(size)


def _install_mail_buttons(module, runtime, document) -> None:
    station_id = _station_id(module, runtime, document, required=False)
    if not station_id:
        return
    sheets = document.getSheets()
    if station_id == STATION_KOCH and sheets.hasByName("Рассылка"):
        sheet = sheets.getByName("Рассылка")
        for number, anchor in ((1, "E3"), (2, "E6"), (3, "E9")):
            _ensure_button(
                document,
                sheet,
                f"ShiftHelperMailList{number}",
                f"Создать письмо — список №{number}",
                f"mail{number}",
                anchor,
            )
    if station_id == STATION_KUZ:
        for number in (1, 2, 3):
            name = f"Список рассылки №{number}"
            if not sheets.hasByName(name):
                continue
            sheet = sheets.getByName(name)
            _ensure_button(
                document,
                sheet,
                f"ShiftHelperMailList{number}",
                "Создать письмо руководству",
                f"mail{number}",
                "E4",
            )
            _ensure_button(
                document,
                sheet,
                f"ShiftHelperForeignList{number}",
                "Создать письмо Зарубежнефть",
                f"foreignmail{number}",
                "E17",
            )
        if sheets.hasByName("Рапорт утро"):
            sheet = sheets.getByName("Рапорт утро")
            _ensure_button(
                document,
                sheet,
                "ShiftHelperMorningMail",
                "Создать письмо руководству",
                "mailmorning",
                "E4",
            )
            _ensure_button(
                document,
                sheet,
                "ShiftHelperForeignMorning",
                "Создать письмо Зарубежнефть",
                "foreignmorning",
                "E17",
            )
        if sheets.hasByName("Зарубежнефть"):
            _ensure_button(
                document,
                sheets.getByName("Зарубежнефть"),
                "ShiftHelperForeignSheet",
                "Создать письмо Зарубежнефть",
                "foreignsheet",
                "E4",
            )


def _refresh_mail_buttons(module, runtime, _args=None) -> None:
    try:
        document = runtime._document()
        _install_mail_buttons(module, runtime, document)
        runtime._message(
            "Кнопки рассылок обновлены. Они используют переносимые service: URL "
            "и не зависят от имени пользователя или пути на компьютере."
        )
    except Exception as exc:
        runtime._message(f"Не удалось обновить кнопки рассылок: {exc}", error=True)


def _prepare(module, runtime, original, _args=None) -> None:
    original(_args)
    document = runtime._document()
    station_id = _station_id(module, runtime, document)
    _sync_report_window(runtime, document)
    _apply_station_profile(module, runtime, document, station_id)
    _install_window_listener(module, runtime, document)
    _install_mail_buttons(module, runtime, document)


def _calendar(module, runtime, original, _args=None) -> None:
    original(_args)
    document = runtime._document()
    station_id = _station_id(module, runtime, document)
    _sync_report_window(runtime, document)
    _apply_station_profile(module, runtime, document, station_id)
    _install_window_listener(module, runtime, document)


def install_calc_excel_parity(module, runtime, _extension_root: Path) -> None:
    """Install accepted Excel semantics over the stabilized Calc runtime."""

    if getattr(runtime, "_CALC_EXCEL_PARITY_APPLIED", False):
        return
    if STATION_META not in tuple(module.META):
        module.META = (*tuple(module.META), STATION_META)

    original_prepare = runtime.prepare_report_input_sheets
    original_calendar = runtime.show_report_date_calendar
    runtime._CALC_PARITY_ORIGINAL_PREPARE = original_prepare
    runtime.prepare_report_input_sheets = lambda _args=None: _prepare(
        module,
        runtime,
        original_prepare,
        _args,
    )
    runtime.show_report_date_calendar = lambda _args=None: _calendar(
        module,
        runtime,
        original_calendar,
        _args,
    )
    runtime.import_generation_from_outlook = lambda _args=None: _import_generation(
        module,
        runtime,
        _args,
    )
    runtime.generate_full_report = lambda _args=None: _generate_report(
        module,
        runtime,
        _args,
    )
    runtime.select_koch_station = lambda _args=None: _set_station(
        module,
        runtime,
        STATION_KOCH,
    )
    runtime.select_kuz_station = lambda _args=None: _set_station(
        module,
        runtime,
        STATION_KUZ,
    )
    runtime.mail_list_1 = lambda _args=None: _create_mail_draft(
        module,
        runtime,
        "list:1",
    )
    runtime.mail_list_2 = lambda _args=None: _create_mail_draft(
        module,
        runtime,
        "list:2",
    )
    runtime.mail_list_3 = lambda _args=None: _create_mail_draft(
        module,
        runtime,
        "list:3",
    )
    runtime.mail_morning = lambda _args=None: _create_mail_draft(
        module,
        runtime,
        "morning",
    )
    runtime.mail_foreign_list_1 = lambda _args=None: _create_mail_draft(
        module,
        runtime,
        "foreign-list:1",
    )
    runtime.mail_foreign_list_2 = lambda _args=None: _create_mail_draft(
        module,
        runtime,
        "foreign-list:2",
    )
    runtime.mail_foreign_list_3 = lambda _args=None: _create_mail_draft(
        module,
        runtime,
        "foreign-list:3",
    )
    runtime.mail_foreign_morning = lambda _args=None: _create_mail_draft(
        module,
        runtime,
        "foreign-morning",
    )
    runtime.mail_foreign_sheet = lambda _args=None: _create_mail_draft(
        module,
        runtime,
        "foreign-sheet",
    )
    runtime.refresh_mail_buttons = lambda _args=None: _refresh_mail_buttons(
        module,
        runtime,
        _args,
    )
    runtime._CALC_EXCEL_PARITY_APPLIED = True
