from __future__ import annotations

import os

from playwright.sync_api import ConsoleMessage, Page, sync_playwright

EDITED_DESCRIPTION = "Изменение сохранено из native Univer row"
CREATED_DESCRIPTION = "Новая запись создана в выбранной пустой строке"
CREATED_REASON = "Независимый черновик выбранной строки"
BATCH_FIRST_DESCRIPTION = "Пакетное описание первой строки"
BATCH_FIRST_REASON = "Пакетная причина первой строки"
BATCH_SECOND_DESCRIPTION = "Пакетное описание второй строки"
BATCH_SECOND_REASON = "Пакетная причина второй строки"


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


def _operation_state(page: Page, base_url: str) -> dict[str, object]:
    response = page.request.get(f"{base_url}/events/api/v2/operations/state")
    if not response.ok:
        raise AssertionError(f"Operation state вернул HTTP {response.status}.")
    return response.json()


def _wait_for_history_controls(page: Page, *, can_undo: bool, can_redo: bool) -> None:
    selector = (
        '[data-testid="operation-history"]'
        f'[data-can-undo="{str(can_undo).lower()}"]'
        f'[data-can-redo="{str(can_redo).lower()}"]'
    )
    page.locator(selector).wait_for(state="visible", timeout=30_000)


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
                raise AssertionError("Undo smoke ожидает две записи.")
            if before[0].get("description") != BATCH_FIRST_DESCRIPTION:
                raise AssertionError("Первая запись не находится в пакетном состоянии.")
            if before[1].get("description") != BATCH_SECOND_DESCRIPTION:
                raise AssertionError("Вторая запись не находится в пакетном состоянии.")

            response = page.goto(f"{base_url}/events/v2", wait_until="networkidle")
            if response is None or not response.ok:
                code = response.status if response is not None else "no response"
                raise AssertionError(f"Journal UI V2 не открылся: {code}")
            _wait_for_history_controls(page, can_undo=True, can_redo=False)

            undo = page.locator('[data-testid="journal-undo"]')
            if undo.is_disabled():
                raise AssertionError("Защищённая кнопка отмены недоступна.")
            with page.expect_navigation(wait_until="networkidle", timeout=30_000):
                undo.click()

            _wait_for_history_controls(page, can_undo=False, can_redo=True)
            undone = _records(page, base_url)
            if undone[0].get("description") != EDITED_DESCRIPTION:
                raise AssertionError("Undo не восстановил описание первой записи.")
            if undone[0].get("reason") != "Chromium acceptance contract":
                raise AssertionError("Undo не восстановил причину первой записи.")
            if undone[1].get("description") != CREATED_DESCRIPTION:
                raise AssertionError("Undo не восстановил описание второй записи.")
            if undone[1].get("reason") != CREATED_REASON:
                raise AssertionError("Undo не восстановил причину второй записи.")
            if int(undone[0].get("revision", 0)) <= int(before[0].get("revision", 0)):
                raise AssertionError("Undo не повысил ревизию первой записи.")
            if int(undone[1].get("revision", 0)) <= int(before[1].get("revision", 0)):
                raise AssertionError("Undo не повысил ревизию второй записи.")

            with page.expect_navigation(wait_until="networkidle", timeout=30_000):
                page.keyboard.press("Control+Y")

            _wait_for_history_controls(page, can_undo=True, can_redo=False)
            redone = _records(page, base_url)
            if redone[0].get("description") != BATCH_FIRST_DESCRIPTION:
                raise AssertionError("Redo не восстановил описание первой записи.")
            if redone[0].get("reason") != BATCH_FIRST_REASON:
                raise AssertionError("Redo не восстановил причину первой записи.")
            if redone[1].get("description") != BATCH_SECOND_DESCRIPTION:
                raise AssertionError("Redo не восстановил описание второй записи.")
            if redone[1].get("reason") != BATCH_SECOND_REASON:
                raise AssertionError("Redo не восстановил причину второй записи.")

            state = _operation_state(page, base_url)
            if state.get("canUndo") is not True or state.get("canRedo") is not False:
                raise AssertionError("История после redo имеет неверное состояние.")

            if page_errors:
                raise AssertionError("Page errors: " + " | ".join(page_errors))
            if console_errors:
                raise AssertionError("Console errors: " + " | ".join(console_errors))
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
