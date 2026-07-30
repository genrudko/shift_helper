from __future__ import annotations

import os

from playwright.sync_api import ConsoleMessage, Page, sync_playwright

DIRECT_DATE = "31.07.2026"
DIRECT_TIME = "10:25"
DIRECT_TYPE = "Пуск"
FIRST_ASSET = "ВЭУ №21"
FIRST_DESCRIPTION = "Первая запись без утечки ввода"
SECOND_ASSET = "ВЭУ №22"
SECOND_DESCRIPTION = "Вторая запись после пустой строки"


def _capture_console_error(message: ConsoleMessage, errors: list[str]) -> None:
    if message.type == "error":
        errors.append(message.text)


def _snapshot(page: Page, base_url: str) -> dict[str, object]:
    response = page.request.get(f"{base_url}/events/api/v2/snapshot")
    if not response.ok:
        raise AssertionError(f"Snapshot API вернул HTTP {response.status}.")
    return response.json()


def _records(page: Page, base_url: str) -> list[dict[str, object]]:
    records = _snapshot(page, base_url).get("records")
    if not isinstance(records, list):
        raise AssertionError("Snapshot API не вернул список записей.")
    return records


def _wait_for_records(page: Page, base_url: str, count: int) -> list[dict[str, object]]:
    for _attempt in range(150):
        records = _records(page, base_url)
        if len(records) == count:
            return records
        page.wait_for_timeout(100)
    raise AssertionError(f"Количество записей не стало равным {count}.")


def _find_record(
    records: list[dict[str, object]], asset: str, description: str
) -> dict[str, object] | None:
    return next(
        (
            record
            for record in records
            if record.get("assetLabel") == asset
            and record.get("description") == description
        ),
        None,
    )


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


def _assert_status(page: Page, text: str) -> None:
    page.locator('.shift-helper-v2__status[data-editing-contract="error"]').filter(
        has_text=text
    ).wait_for(state="visible", timeout=5_000)


def _wait_for_control_value(page: Page, selector: str, expected: str) -> None:
    page.locator(selector).wait_for(state="visible", timeout=5_000)
    for _attempt in range(50):
        if page.locator(selector).input_value() == expected:
            return
        page.wait_for_timeout(100)
    actual = page.locator(selector).input_value()
    raise AssertionError(f"Значение {selector} не восстановилось: {actual!r} != {expected!r}")


def main() -> None:
    base_url = os.environ.get("SHIFT_HELPER_BASE_URL", "http://127.0.0.1:17945")

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

            if _records(page, base_url) != []:
                raise AssertionError("Editing contract smoke должен начинаться с пустой базы.")

            initial_date = page.locator('[data-testid="journal-date"]').input_value()
            initial_time = page.locator('[data-testid="journal-time"]').input_value()
            initial_type = page.locator('[data-testid="journal-event-type"]').input_value()

            sheet_box = page.locator("#univer-sheet").bounding_box()
            if sheet_box is None:
                raise AssertionError("Не удалось определить геометрию контейнера Univer.")

            row_two_y = sheet_box["y"] + 173
            row_three_y = row_two_y + 32
            row_six_y = row_two_y + 4 * 32
            row_twelve_y = row_two_y + 10 * 32
            date_x = sheet_box["x"] + 150
            time_x = sheet_box["x"] + 230
            asset_x = sheet_box["x"] + 340
            type_x = sheet_box["x"] + 490
            description_x = sheet_box["x"] + 690

            page.mouse.dblclick(asset_x, row_six_y)
            page.keyboard.insert_text("LEAK-FROM-ROW-6")
            page.keyboard.press("Enter")
            _assert_status(page, "Строка 6 не является строкой новой записи")
            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Выберите строку"
            ).wait_for(state="visible", timeout=5_000)
            if _records(page, base_url) != []:
                raise AssertionError("Ввод в пустой строке создал запись в SQLite.")

            _edit_cell(page, date_x, row_two_y, "!")
            _assert_status(page, "Дата не сохранена")
            _wait_for_control_value(page, '[data-testid="journal-date"]', initial_date)

            _edit_cell(page, time_x, row_two_y, "!")
            _assert_status(page, "Время не сохранено")
            _wait_for_control_value(page, '[data-testid="journal-time"]', initial_time)

            _edit_cell(page, type_x, row_two_y, "sd")
            _assert_status(page, "Тип события не сохранён")
            _wait_for_control_value(page, '[data-testid="journal-event-type"]', initial_type)

            _edit_cell(page, date_x, row_two_y, DIRECT_DATE)
            _wait_for_control_value(page, '[data-testid="journal-date"]', DIRECT_DATE)

            _edit_cell(page, time_x, row_two_y, DIRECT_TIME)
            _wait_for_control_value(page, '[data-testid="journal-time"]', DIRECT_TIME)

            _edit_cell(page, type_x, row_two_y, DIRECT_TYPE)
            _wait_for_control_value(page, '[data-testid="journal-event-type"]', "startup")

            _edit_cell(page, description_x, row_two_y, FIRST_DESCRIPTION)
            _edit_cell(page, asset_x, row_two_y, FIRST_ASSET)
            first_records = _wait_for_records(page, base_url, 1)
            first = _find_record(first_records, FIRST_ASSET, FIRST_DESCRIPTION)
            if first is None:
                raise AssertionError(f"Первая запись содержит утёкший ввод: {first_records!r}")
            if first.get("startAt") != "2026-07-31T10:25" or first.get("eventType") != "startup":
                raise AssertionError(f"Специальные поля первой записи сохранены неверно: {first!r}")

            page.locator('html[data-draft-row="2"]').wait_for(
                state="attached", timeout=10_000
            )
            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Новая строка №2"
            ).wait_for(state="visible", timeout=10_000)

            page.mouse.dblclick(description_x, row_twelve_y)
            page.keyboard.insert_text("LEAK-FROM-ROW-12")
            page.keyboard.press("Enter")
            _assert_status(page, "Строка 12 не является строкой новой записи")
            if len(_records(page, base_url)) != 1:
                raise AssertionError("Ввод в далёкой пустой строке создал вторую запись.")

            _edit_cell(page, description_x, row_three_y, SECOND_DESCRIPTION)
            _edit_cell(page, asset_x, row_three_y, SECOND_ASSET)
            second_records = _wait_for_records(page, base_url, 2)
            second = _find_record(second_records, SECOND_ASSET, SECOND_DESCRIPTION)
            if second is None:
                raise AssertionError(f"Вторая запись содержит утёкший ввод: {second_records!r}")
            serialized_records = repr(second_records)
            if "LEAK-FROM-ROW-6" in serialized_records or "LEAK-FROM-ROW-12" in serialized_records:
                raise AssertionError(f"В SQLite обнаружен утёкший ввод: {second_records!r}")

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
