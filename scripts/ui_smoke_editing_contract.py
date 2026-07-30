from __future__ import annotations

import os

from playwright.sync_api import ConsoleMessage, Page, sync_playwright

ROW_TWO_ASSET = "ВЭУ №21"
ROW_TWO_DESCRIPTION = "Запись создана непосредственно в строке 2"
ROW_SIX_ASSET = "ВЭУ №26"
ROW_SIX_DESCRIPTION = "Независимый черновик строки 6"


def _capture_console_error(message: ConsoleMessage, errors: list[str]) -> None:
    if message.type == "error":
        errors.append(message.text)


def _records(page: Page, base_url: str) -> list[dict[str, object]]:
    response = page.request.get(f"{base_url}/events/api/v2/snapshot")
    if not response.ok:
        raise AssertionError(f"Snapshot API вернул HTTP {response.status}.")
    records = response.json().get("records")
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
    page.locator(".shift-helper-v2__status").filter(has_text=text).wait_for(
        state="visible", timeout=5_000
    )


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

            page.locator('html[data-editing-model="native-row"]').wait_for(
                state="attached", timeout=30_000
            )
            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Пустая строка 2"
            ).wait_for(state="visible", timeout=5_000)
            _wait_for_working_canvas(page)
            if _records(page, base_url) != []:
                raise AssertionError("Native-row smoke должен начинаться с пустой базы.")

            sheet_box = page.locator("#univer-sheet").bounding_box()
            if sheet_box is None:
                raise AssertionError("Не удалось определить геометрию контейнера Univer.")

            row_two_y = sheet_box["y"] + 173
            row_six_y = row_two_y + 4 * 32
            date_x = sheet_box["x"] + 150
            time_x = sheet_box["x"] + 230
            asset_x = sheet_box["x"] + 340
            type_x = sheet_box["x"] + 490
            description_x = sheet_box["x"] + 690

            # First edit in an arbitrary blank row materializes a draft in the
            # same row. It must not move the selection to row 2.
            _edit_cell(page, asset_x, row_six_y, ROW_SIX_ASSET)
            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Черновик · строка 6"
            ).wait_for(state="visible", timeout=5_000)
            _assert_status(page, "Черновик в строке 6")
            if _records(page, base_url) != []:
                raise AssertionError("Неполный черновик строки 6 попал в SQLite.")

            # A second draft can be edited independently in row 2.
            _edit_cell(page, date_x, row_two_y, "31.07.2026")
            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Черновик · строка 2"
            ).wait_for(state="visible", timeout=5_000)
            _edit_cell(page, time_x, row_two_y, "10:25")
            _edit_cell(page, type_x, row_two_y, "Пуск")

            # Invalid special values are rejected in place and do not change
            # the draft's model. A following valid value must remain in row 2.
            _edit_cell(page, time_x, row_two_y, "!")
            _assert_status(page, "Время не сохранено")
            _edit_cell(page, time_x, row_two_y, "10:25")
            _edit_cell(page, description_x, row_two_y, ROW_TWO_DESCRIPTION)
            _edit_cell(page, asset_x, row_two_y, ROW_TWO_ASSET)

            first_records = _wait_for_records(page, base_url, 1)
            row_two_record = _find_record(
                first_records, ROW_TWO_ASSET, ROW_TWO_DESCRIPTION
            )
            if row_two_record is None:
                raise AssertionError(f"Строка 2 сохранилась неверно: {first_records!r}")
            if row_two_record.get("startAt") != "2026-07-31T10:25":
                raise AssertionError(f"Дата/время строки 2 неверны: {row_two_record!r}")
            if row_two_record.get("eventType") != "startup":
                raise AssertionError(f"Тип строки 2 неверен: {row_two_record!r}")

            # Row 6 must still be its own draft and complete independently.
            page.mouse.click(asset_x, row_six_y)
            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Черновик · строка 6"
            ).wait_for(state="visible", timeout=5_000)
            _edit_cell(page, description_x, row_six_y, ROW_SIX_DESCRIPTION)

            both_records = _wait_for_records(page, base_url, 2)
            row_six_record = _find_record(
                both_records, ROW_SIX_ASSET, ROW_SIX_DESCRIPTION
            )
            if row_six_record is None:
                raise AssertionError(f"Строка 6 сохранилась неверно: {both_records!r}")
            serialized = repr(both_records)
            if "LEAK" in serialized or "sdsdsd" in serialized:
                raise AssertionError(f"Между строками обнаружена утечка ввода: {both_records!r}")

            # A fresh blank row remains a blank row until editing actually starts.
            page.mouse.click(asset_x, row_two_y + 8 * 32)
            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Пустая строка 10"
            ).wait_for(state="visible", timeout=5_000)
            if len(_records(page, base_url)) != 2:
                raise AssertionError("Обычный клик по пустой строке изменил SQLite.")

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
