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
    records = response.json().get("records")
    if not isinstance(records, list):
        raise AssertionError("Snapshot API не вернул записи.")
    return records


def _wait_for_reasons(
    page: Page,
    base_url: str,
    first_reason: object,
    second_reason: object,
    *,
    timeout_ms: int = 10_000,
) -> list[dict[str, object]]:
    attempts = max(1, timeout_ms // 100)
    for _attempt in range(attempts):
        records = _records(page, base_url)
        if (
            len(records) == 2
            and records[0].get("reason") == first_reason
            and records[1].get("reason") == second_reason
        ):
            return records
        page.wait_for_timeout(100)

    status = page.locator(".shift-helper-v2__status")
    status_text = status.text_content() if status.count() else "статус отсутствует"
    records = _records(page, base_url)
    raise AssertionError(
        "Состояние причин не изменилось за отведённое время. "
        f"Статус UI: {status_text!r}; записи: {records!r}"
    )


def _wait_for_history_controls(page: Page, *, can_undo: bool, can_redo: bool) -> None:
    selector = (
        '[data-testid="operation-history"]'
        f'[data-can-undo="{str(can_undo).lower()}"]'
        f'[data-can-redo="{str(can_redo).lower()}"]'
    )
    page.locator(selector).wait_for(state="visible", timeout=30_000)


def _wait_for_working_canvas(page: Page) -> None:
    for _attempt in range(100):
        canvases = page.locator("canvas")
        for index in range(canvases.count()):
            box = canvases.nth(index).bounding_box()
            if box and box["width"] > 500 and box["height"] > 300:
                return
        page.wait_for_timeout(100)
    raise AssertionError("Univer canvas не получил рабочую геометрию журнала.")


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
            before = _records(page, base_url)
            if len(before) != 2:
                raise AssertionError("Clear smoke ожидает две записи.")
            first_reason = before[0].get("reason")
            second_reason = before[1].get("reason")
            if not isinstance(first_reason, str) or not first_reason:
                raise AssertionError("Первая причина должна быть непустой перед очисткой.")
            if not isinstance(second_reason, str) or not second_reason:
                raise AssertionError("Вторая причина должна быть непустой перед очисткой.")

            response = page.goto(f"{base_url}/events/v2", wait_until="networkidle")
            if response is None or not response.ok:
                code = response.status if response is not None else "no response"
                raise AssertionError(f"Journal UI V2 не открылся: {code}")
            _wait_for_history_controls(page, can_undo=True, can_redo=False)
            _wait_for_working_canvas(page)

            sheet_box = page.locator("#univer-sheet").bounding_box()
            if sheet_box is None:
                raise AssertionError("Не удалось определить геометрию контейнера Univer.")
            reason_x = sheet_box["x"] + 930
            description_x = sheet_box["x"] + 690
            row_two_y = sheet_box["y"] + 173

            page.mouse.click(reason_x, row_two_y)
            page.keyboard.press("Shift+ArrowDown")
            page.keyboard.press("Delete")

            cleared = _wait_for_reasons(page, base_url, None, None)
            page.wait_for_load_state("networkidle", timeout=30_000)
            _wait_for_history_controls(page, can_undo=True, can_redo=False)
            if cleared[0].get("description") != before[0].get("description"):
                raise AssertionError("Очистка диапазона изменила описание первой записи.")
            if cleared[1].get("description") != before[1].get("description"):
                raise AssertionError("Очистка диапазона изменила описание второй записи.")
            if int(cleared[0].get("revision", 0)) <= int(before[0].get("revision", 0)):
                raise AssertionError("Очистка не повысила ревизию первой записи.")
            if int(cleared[1].get("revision", 0)) <= int(before[1].get("revision", 0)):
                raise AssertionError("Очистка не повысила ревизию второй записи.")

            page.keyboard.press("Control+Z")
            restored = _wait_for_reasons(
                page,
                base_url,
                first_reason,
                second_reason,
            )
            page.wait_for_load_state("networkidle", timeout=30_000)
            _wait_for_history_controls(page, can_undo=True, can_redo=True)

            page.mouse.click(description_x, row_two_y)
            page.keyboard.press("Delete")
            page.locator('.shift-helper-v2__status[data-clear-state="error"]').filter(
                has_text="обязательную или защищённую колонку"
            ).wait_for(state="visible", timeout=5_000)
            page.wait_for_timeout(300)
            after_protected_delete = _records(page, base_url)
            if after_protected_delete != restored:
                raise AssertionError("Delete в обязательной колонке изменил SQLite.")

            if page_errors:
                raise AssertionError("Page errors: " + " | ".join(page_errors))
            if console_errors:
                raise AssertionError("Console errors: " + " | ".join(console_errors))
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
