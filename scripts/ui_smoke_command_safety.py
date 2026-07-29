from __future__ import annotations

import os

from playwright.sync_api import ConsoleMessage, Page, sync_playwright


def _capture_console_error(message: ConsoleMessage, errors: list[str]) -> None:
    if message.type == "error":
        errors.append(message.text)


def _records(page: Page, base_url: str) -> list[dict[str, object]]:
    response = page.request.get(f"{base_url}/events/api/v2/snapshot")
    if not response.ok:
        raise AssertionError(f"Snapshot API вернул HTTP {response.status}.")
    payload = response.json()
    records = payload.get("records")
    if not isinstance(records, list):
        raise AssertionError("Snapshot API не вернул массив записей.")
    return records


def _wait_for_working_canvas(page: Page) -> None:
    for _attempt in range(100):
        canvases = page.locator("canvas")
        for index in range(canvases.count()):
            box = canvases.nth(index).bounding_box()
            if box and box["width"] > 500 and box["height"] > 300:
                return
        page.wait_for_timeout(100)
    raise AssertionError("Univer canvas не получил рабочую геометрию журнала.")


def _assert_menu_command_hidden(page: Page, command_id: str) -> None:
    locator = page.locator(f'[data-u-command="{command_id}"]')
    for index in range(locator.count()):
        if locator.nth(index).is_visible():
            raise AssertionError(f"Опасная команда осталась видимой: {command_id}")


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
            before_records = _records(page, base_url)
            if len(before_records) != 2:
                raise AssertionError("Safety smoke ожидает две записи после основного UI smoke.")

            response = page.goto(f"{base_url}/events/v2", wait_until="networkidle")
            if response is None or not response.ok:
                status = response.status if response is not None else "no response"
                raise AssertionError(f"Journal UI V2 не открылся: {status}")

            page.locator(".shift-helper-v2__status").filter(
                has_text="Загружено записей: 2"
            ).wait_for(state="visible", timeout=30_000)
            _wait_for_working_canvas(page)

            command_safety = page.locator("html").get_attribute("data-command-safety")
            if command_safety != "active":
                raise AssertionError("Command safety не активирован.")
            clear_adapter = page.locator("html").get_attribute("data-clear-selection")
            if clear_adapter != "active":
                raise AssertionError("Clear-selection adapter не активирован.")
            date_placeholder = page.locator('[data-testid="journal-date"]').get_attribute(
                "placeholder"
            )
            if date_placeholder != "дд.мм.гггг":
                raise AssertionError("Поле даты не использует локализованный формат.")

            _assert_menu_command_hidden(page, "univer.command.undo")
            _assert_menu_command_hidden(page, "univer.command.redo")
            _assert_menu_command_hidden(page, "sheet.command.cut")
            _assert_menu_command_hidden(page, "sheet.command.remove-row-confirm")
            _assert_menu_command_hidden(page, "sheet.command.clear-selection-content")

            sheet_box = page.locator("#univer-sheet").bounding_box()
            if sheet_box is None:
                raise AssertionError("Не удалось определить геометрию контейнера Univer.")
            reason_x = sheet_box["x"] + 930
            row_two_y = sheet_box["y"] + 173

            page.mouse.click(reason_x, row_two_y)
            page.keyboard.press("Control+X")
            page.locator(".shift-helper-v2__safety-toast").filter(
                has_text="Вырезание диапазона"
            ).wait_for(state="visible", timeout=5_000)
            page.wait_for_timeout(300)
            if _records(page, base_url) != before_records:
                raise AssertionError("Заблокированное вырезание изменило SQLite.")

            if page_errors:
                raise AssertionError("Page errors: " + " | ".join(page_errors))
            if console_errors:
                raise AssertionError("Console errors: " + " | ".join(console_errors))
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
