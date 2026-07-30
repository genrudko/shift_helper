from __future__ import annotations

import os

from playwright.sync_api import ConsoleMessage, Page, sync_playwright

DIRECT_DATE = "31.07.2026"
DIRECT_TIME = "10:25"
DIRECT_TYPE = "Пуск"
DIRECT_ASSET = "ВЭУ №21"


def _capture_console_error(message: ConsoleMessage, errors: list[str]) -> None:
    if message.type == "error":
        errors.append(message.text)


def _snapshot(page: Page, base_url: str) -> dict[str, object]:
    response = page.request.get(f"{base_url}/events/api/v2/snapshot")
    if not response.ok:
        raise AssertionError(f"Snapshot API вернул HTTP {response.status}.")
    return response.json()


def _wait_for_working_canvas(page: Page) -> None:
    for _attempt in range(100):
        canvases = page.locator("canvas")
        for index in range(canvases.count()):
            box = canvases.nth(index).bounding_box()
            if box and box["width"] > 500 and box["height"] > 300:
                return
        page.wait_for_timeout(100)
    raise AssertionError("Univer canvas не получил рабочую геометрию журнала.")


def _edit_cell(page: Page, x: float, y: float, value: str) -> None:
    page.mouse.dblclick(x, y)
    page.keyboard.press("Control+A")
    page.keyboard.insert_text(value)
    page.keyboard.press("Enter")


def main() -> None:
    base_url = os.environ.get("SHIFT_HELPER_BASE_URL", "http://127.0.0.1:17944")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
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
            response = page.goto(f"{base_url}/", wait_until="networkidle")
            if response is None or not response.ok:
                code = response.status if response is not None else "no response"
                raise AssertionError(f"Основной интерфейс не открылся: {code}")
            if not page.url.endswith("/events/v2"):
                raise AssertionError(f"Основной маршрут не открыл Univer: {page.url}")

            page.locator('html[data-editing-contract="active"]').wait_for(
                state="attached", timeout=30_000
            )
            page.locator('html[data-draft-row="1"]').wait_for(
                state="attached", timeout=30_000
            )
            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Новая строка №1"
            ).wait_for(state="visible", timeout=5_000)
            _wait_for_working_canvas(page)

            if _snapshot(page, base_url).get("records") != []:
                raise AssertionError("Editing contract smoke должен начинаться с пустой базы.")

            sheet_box = page.locator("#univer-sheet").bounding_box()
            if sheet_box is None:
                raise AssertionError("Не удалось определить геометрию контейнера Univer.")

            row_two_y = sheet_box["y"] + 173
            row_three_y = row_two_y + 32
            date_x = sheet_box["x"] + 150
            time_x = sheet_box["x"] + 230
            asset_x = sheet_box["x"] + 340
            type_x = sheet_box["x"] + 490
            description_x = sheet_box["x"] + 690

            page.mouse.dblclick(description_x, row_three_y)
            page.locator('.shift-helper-v2__status[data-editing-contract="error"]').filter(
                has_text="Строка 3 пока не активна"
            ).wait_for(state="visible", timeout=5_000)
            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Новая строка №1"
            ).wait_for(state="visible", timeout=5_000)
            if _snapshot(page, base_url).get("records") != []:
                raise AssertionError("Клик по неактивной пустой строке изменил SQLite.")

            _edit_cell(page, date_x, row_two_y, DIRECT_DATE)
            if page.locator('[data-testid="journal-date"]').input_value() != DIRECT_DATE:
                raise AssertionError("Прямая дата не синхронизировалась с редактором строки.")

            _edit_cell(page, time_x, row_two_y, DIRECT_TIME)
            if page.locator('[data-testid="journal-time"]').input_value() != DIRECT_TIME:
                raise AssertionError("Прямое время не синхронизировалось с редактором строки.")

            _edit_cell(page, type_x, row_two_y, DIRECT_TYPE)
            if page.locator('[data-testid="journal-event-type"]').input_value() != "startup":
                raise AssertionError("Прямой тип события не синхронизировался с доменной моделью.")

            _edit_cell(page, asset_x, row_two_y, DIRECT_ASSET)
            page.wait_for_timeout(300)
            if _snapshot(page, base_url).get("records") != []:
                raise AssertionError("Неполный draft преждевременно попал в SQLite.")

            page.mouse.click(time_x, row_two_y)
            page.wait_for_timeout(300)
            body_text = page.locator("body").inner_text()
            if "sheets-ui.info.error" in body_text or "sheets-ui.info.forceStringInfo" in body_text:
                raise AssertionError("В интерфейсе остались необработанные locale keys Univer.")

            if page_errors:
                raise AssertionError("Page errors: " + " | ".join(page_errors))
            if console_errors:
                raise AssertionError("Console errors: " + " | ".join(console_errors))
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
