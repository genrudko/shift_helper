from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import ConsoleMessage, Page, sync_playwright

EXPECTED_COLUMNS = (
    "Дата останова",
    "Время останова",
    "№ ВЭУ",
    "Описание события",
    "Причина",
    "Действия персонала",
    "Исполнитель",
    "Дата пуска",
    "Время пуска",
    "Простой",
    "Кто внёс запись",
    "Потери",
)
ASSET = "18"
DESCRIPTION = "Проверка утверждённой формы ЖС"
REASON = "Проверка Delete и persistent undo"
END_AT = "2026-07-31T10:25"


def _capture_console_error(message: ConsoleMessage, errors: list[str]) -> None:
    if message.type == "error":
        errors.append(message.text)


def _snapshot(page: Page, base_url: str) -> list[dict[str, object]]:
    response = page.request.get(f"{base_url}/events/api/v3/snapshot")
    if not response.ok:
        raise AssertionError(f"Snapshot v3 вернул HTTP {response.status}.")
    payload = response.json()
    records = payload.get("records")
    if payload.get("schemaVersion") != 2 or not isinstance(records, list):
        raise AssertionError(f"Snapshot v3 имеет неверный формат: {payload!r}")
    return records


def _delete_diagnostics(page: Page) -> dict[str, object]:
    html = page.locator("html")
    status = page.locator(".shift-helper-v2__status")
    return {
        "lastKey": html.get_attribute("data-clear-last-key"),
        "sheetEditing": html.get_attribute("data-clear-sheet-editing"),
        "keyTarget": html.get_attribute("data-clear-key-target"),
        "rangeCount": html.get_attribute("data-clear-range-count"),
        "resolvedRange": html.get_attribute("data-clear-resolved-range"),
        "activeElement": page.evaluate(
            "document.activeElement ? document.activeElement.tagName + '.' + "
            "document.activeElement.className : 'none'"
        ),
        "status": status.text_content() if status.count() else None,
    }


def _wait_for_records(page: Page, base_url: str, predicate, message: str):
    for _attempt in range(200):
        records = _snapshot(page, base_url)
        if predicate(records):
            return records
        page.wait_for_timeout(100)
    raise AssertionError(
        f"{message} Последнее состояние: {_snapshot(page, base_url)!r}; "
        f"Delete diagnostics: {_delete_diagnostics(page)!r}"
    )


def _wait_for_canvas(page: Page) -> dict[str, float]:
    for _attempt in range(120):
        box = page.locator("#univer-sheet").bounding_box()
        if box and box["width"] > 1000 and box["height"] > 400:
            return box
        page.wait_for_timeout(100)
    raise AssertionError("Univer не получил рабочую геометрию листа ЖС.")


def _cell_x(sheet_x: float, column: int) -> float:
    widths = (104, 88, 108, 300, 230, 260, 170, 104, 88, 94, 180, 100)
    return sheet_x + 48 + sum(widths[:column]) + widths[column] / 2


def _edit_cell(page: Page, x: float, y: float, value: str) -> None:
    page.mouse.dblclick(x, y)
    page.keyboard.press("Control+A")
    page.keyboard.type(value)
    page.keyboard.press("Enter")


def _runtime_origin(page: Page) -> float:
    return float(page.evaluate("performance.timeOrigin"))


def _wait_for_reload(page: Page, previous_origin: float) -> None:
    page.wait_for_function(
        "origin => performance.timeOrigin !== origin",
        arg=previous_origin,
        timeout=30_000,
    )
    page.wait_for_load_state("networkidle", timeout=30_000)
    page.locator('html[data-journal-form="approved-js-12"]').wait_for(
        state="attached",
        timeout=30_000,
    )
    _wait_for_canvas(page)


def _select_persisted_row(page: Page, column: int = 4) -> tuple[float, float]:
    box = _wait_for_canvas(page)
    x = _cell_x(box["x"], column)
    selection = page.locator('[data-testid="journal-selection"]')
    start_y = int(box["y"] + 100)
    end_y = int(min(box["y"] + 420, box["y"] + box["height"] - 20))
    for y in range(start_y, end_y, 6):
        page.mouse.click(x, y)
        page.wait_for_timeout(25)
        text = selection.text_content() or ""
        if "Запись №1" in text:
            row_header_x = box["x"] + 24
            page.mouse.click(row_header_x, y)
            page.wait_for_timeout(100)
            return row_header_x, float(y)
    raise AssertionError(
        "Не удалось выбрать сохранённую строку через рабочую область Univer. "
        f"Последний контекст: {selection.text_content()!r}"
    )


def main() -> None:
    base_url = os.environ.get("SHIFT_HELPER_BASE_URL", "http://127.0.0.1:17944")
    screenshot_path = Path(
        os.environ.get("SHIFT_HELPER_UI_SCREENSHOT", "ui-v2-smoke/univer-v2.png")
    )
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 2400, "height": 1200},
            device_scale_factor=1,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        page = context.new_page()
        page_errors: list[str] = []
        console_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("console", lambda message: _capture_console_error(message, console_errors))

        try:
            if _snapshot(page, base_url):
                raise AssertionError("Approved ЖС smoke должен начинаться с пустой базы.")

            response = page.goto(f"{base_url}/", wait_until="networkidle")
            if response is None or not response.ok:
                code = response.status if response is not None else "no response"
                raise AssertionError(f"Основной runtime не открылся: {code}")
            if not page.url.endswith("/events/v2"):
                raise AssertionError(f"Launcher route не привёл в Univer: {page.url}")

            html = page.locator("html")
            html.locator('xpath=self::*[@data-journal-form="approved-js-12"]').wait_for(
                state="attached",
                timeout=30_000,
            )
            actual_columns = html.get_attribute("data-journal-columns")
            if actual_columns != "|".join(EXPECTED_COLUMNS):
                raise AssertionError(
                    "Форма ЖС не совпадает с утверждёнными 12 графами: "
                    f"{actual_columns!r}"
                )
            if html.get_attribute("data-editing-model") != "approved-js-row":
                raise AssertionError("Approved ЖС row controller не активирован.")
            if html.get_attribute("data-clear-selection") != "approved-js":
                raise AssertionError("Approved Delete adapter не активирован.")
            if page.locator('[data-testid="journal-close"]').count() != 0:
                raise AssertionError("Старая кнопка завершения события осталась в форме.")

            box = _wait_for_canvas(page)
            row_two_y = box["y"] + 173
            asset_x = _cell_x(box["x"], 2)
            description_x = _cell_x(box["x"], 3)
            reason_x = _cell_x(box["x"], 4)
            end_date_x = _cell_x(box["x"], 7)
            end_time_x = _cell_x(box["x"], 8)

            _edit_cell(page, asset_x, row_two_y, ASSET)
            page.wait_for_timeout(200)
            if _snapshot(page, base_url):
                raise AssertionError("Неполная строка преждевременно создала SQLite-запись.")
            _edit_cell(page, description_x, row_two_y, DESCRIPTION)
            created = _wait_for_records(
                page,
                base_url,
                lambda records: len(records) == 1
                and records[0].get("assetLabel") == ASSET
                and records[0].get("description") == DESCRIPTION,
                "Строка ЖС не была создана после заполнения обязательных граф.",
            )[0]
            if created.get("enteredBy") != "Локальное рабочее место":
                raise AssertionError(f"Автор записи заполнен неверно: {created!r}")

            _edit_cell(page, reason_x, row_two_y, REASON)
            _wait_for_records(
                page,
                base_url,
                lambda records: len(records) == 1 and records[0].get("reason") == REASON,
                "Причина не сохранилась.",
            )
            _edit_cell(page, end_date_x, row_two_y, "31.07.2026")
            _edit_cell(page, end_time_x, row_two_y, "10:25")
            closed = _wait_for_records(
                page,
                base_url,
                lambda records: len(records) == 1
                and records[0].get("endAt") == END_AT
                and records[0].get("status") == "closed",
                "Дата и время пуска не завершили событие в той же строке.",
            )[0]
            if not isinstance(closed.get("downtimeMinutes"), int):
                raise AssertionError(f"Простой не был рассчитан: {closed!r}")

            clear_origin = _runtime_origin(page)
            page.mouse.click(reason_x, row_two_y)
            page.keyboard.press("Delete")
            _wait_for_records(
                page,
                base_url,
                lambda records: len(records) == 1 and records[0].get("reason") is None,
                "Delete не очистил значение ячейки в SQLite.",
            )
            _wait_for_reload(page, clear_origin)

            _select_persisted_row(page)
            delete_origin = _runtime_origin(page)
            page.keyboard.press("Delete")
            _wait_for_records(
                page,
                base_url,
                lambda records: len(records) == 0,
                "Delete выделенной строки не удалил её из рабочего журнала.",
            )
            _wait_for_reload(page, delete_origin)

            page.locator(
                '[data-testid="operation-history"][data-can-undo="true"]'
            ).wait_for(state="visible", timeout=30_000)
            restore_origin = _runtime_origin(page)
            page.keyboard.press("Control+Z")
            restored = _wait_for_records(
                page,
                base_url,
                lambda records: len(records) == 1 and records[0].get("reason") is None,
                "Ctrl+Z не восстановил удалённую строку.",
            )[0]
            if restored.get("description") != DESCRIPTION:
                raise AssertionError("Восстановленная строка потеряла исходные данные.")
            _wait_for_reload(page, restore_origin)

            page.locator(
                '[data-testid="operation-history"][data-can-undo="true"]'
            ).wait_for(state="visible", timeout=30_000)
            reason_origin = _runtime_origin(page)
            page.keyboard.press("Control+Z")
            _wait_for_records(
                page,
                base_url,
                lambda records: len(records) == 1 and records[0].get("reason") == REASON,
                "Второй Ctrl+Z не восстановил очищенное значение ячейки.",
            )
            _wait_for_reload(page, reason_origin)

            page.screenshot(path=str(screenshot_path), full_page=True)
            if page_errors:
                raise AssertionError("Page errors: " + " | ".join(page_errors))
            if console_errors:
                raise AssertionError("Console errors: " + " | ".join(console_errors))
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
