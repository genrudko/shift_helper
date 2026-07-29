from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import ConsoleMessage, Locator, Page, sync_playwright

EDITED_DESCRIPTION = "Изменение сохранено из Univer UI V2"
EDITED_START_AT = "2026-07-28T12:45"
EDITED_EVENT_TYPE = "dispatch_command"
CREATED_ASSET = "ВЭУ №18"
CREATED_DESCRIPTION = "Новая запись создана из первой строки Univer"
CREATED_START_AT = "2026-07-29T13:15"
CREATED_EVENT_TYPE = "startup"
BATCH_FIRST_DESCRIPTION = "Пакетное описание первой строки"
BATCH_FIRST_REASON = "Пакетная причина первой строки"
BATCH_SECOND_DESCRIPTION = "Пакетное описание второй строки"
BATCH_SECOND_REASON = "Пакетная причина второй строки"


def _seed_event(page: Page, base_url: str) -> None:
    response = page.request.post(
        f"{base_url}/events/new",
        form={
            "start_at": "2026-07-29T11:30",
            "asset_label": "ВЭУ №17",
            "event_type": "rotor_limit",
            "description": "Проверка чистого Univer UI V2",
            "reason": "Chromium acceptance contract",
            "actions": "Отображение записи в журнале",
            "performer": "Иванов И.И.",
            "error_codes": "214",
            "rotor_limit": "0,80",
            "include_in_report": "on",
        },
    )
    if not response.ok:
        raise AssertionError(f"Не удалось создать тестовую запись: HTTP {response.status}")


def _capture_console_error(message: ConsoleMessage, errors: list[str]) -> None:
    if message.type == "error":
        errors.append(message.text)


def _snapshot(page: Page, base_url: str) -> dict[str, object]:
    response = page.request.get(f"{base_url}/events/api/v2/snapshot")
    if not response.ok:
        raise AssertionError(f"Snapshot API вернул HTTP {response.status}.")
    return response.json()


def _presentation(page: Page, base_url: str) -> dict[str, object]:
    response = page.request.get(f"{base_url}/events/api/v2/presentation")
    if not response.ok:
        raise AssertionError(f"Presentation API вернул HTTP {response.status}.")
    return response.json()


def _wait_for_snapshot(page: Page, base_url: str, predicate, failure_message: str) -> None:
    for _attempt in range(120):
        snapshot = _snapshot(page, base_url)
        records = snapshot.get("records", [])
        if isinstance(records, list) and predicate(records):
            return
        page.wait_for_timeout(100)
    raise AssertionError(failure_message)


def _wait_for_record(
    page: Page,
    base_url: str,
    predicate,
    failure_message: str,
) -> dict[str, object]:
    found: dict[str, object] = {}

    def snapshot_predicate(records: list[object]) -> bool:
        nonlocal found
        for record in records:
            if isinstance(record, dict) and predicate(record, records):
                found = record
                return True
        return False

    _wait_for_snapshot(page, base_url, snapshot_predicate, failure_message)
    return found


def _wait_for_presentation_style(page: Page, base_url: str) -> int:
    for _attempt in range(120):
        state = _presentation(page, base_url)
        revision = state.get("revision")
        presentation = state.get("presentation")
        if isinstance(revision, int) and revision >= 1 and isinstance(presentation, dict):
            sheet = presentation.get("sheet")
            if isinstance(sheet, dict):
                cell_styles = sheet.get("cellStyles")
                if isinstance(cell_styles, dict):
                    row = cell_styles.get("1")
                    if isinstance(row, dict) and "5" in row:
                        return revision
        page.wait_for_timeout(100)
    raise AssertionError("Оформление ячейки F2 не было сохранено presentation API.")


def _assert_incomplete_draft_not_persisted(page: Page, base_url: str) -> None:
    page.wait_for_timeout(500)
    snapshot = _snapshot(page, base_url)
    records = snapshot.get("records", [])
    if not isinstance(records, list) or len(records) != 1:
        raise AssertionError("Незавершённая строка ошибочно создала запись в SQLite.")


def _set_control_value(locator: Locator, value: str) -> None:
    locator.fill(value)
    locator.dispatch_event("change")


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
    screenshot_path = Path(
        os.environ.get("SHIFT_HELPER_UI_SCREENSHOT", "ui-v2-smoke/univer-v2.png")
    )
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            device_scale_factor=1,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        context.grant_permissions(
            ["clipboard-read", "clipboard-write"],
            origin=base_url,
        )
        page = context.new_page()
        page_errors: list[str] = []
        console_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("console", lambda message: _capture_console_error(message, console_errors))

        try:
            _seed_event(page, base_url)
            response = page.goto(f"{base_url}/events/v2", wait_until="networkidle")
            if response is None or not response.ok:
                status = response.status if response is not None else "no response"
                raise AssertionError(f"Journal UI V2 не открылся: {status}")

            page.locator(".shift-helper-v2__status").filter(
                has_text="Загружено записей: 1"
            ).wait_for(state="visible", timeout=30_000)
            page.locator(".shift-helper-v2__error").wait_for(state="detached", timeout=5_000)
            _wait_for_working_canvas(page)

            sheet_box = page.locator("#univer-sheet").bounding_box()
            if sheet_box is None:
                raise AssertionError("Не удалось определить геометрию контейнера Univer.")
            row_two_y = sheet_box["y"] + 173
            row_three_y = row_two_y + 32
            asset_x = sheet_box["x"] + 340
            description_x = sheet_box["x"] + 690

            page.mouse.dblclick(description_x, row_two_y)
            page.keyboard.press("Control+A")
            page.keyboard.type(EDITED_DESCRIPTION)
            page.keyboard.press("Enter")
            _wait_for_record(
                page,
                base_url,
                lambda record, records: (
                    len(records) == 1
                    and record.get("id") == 1
                    and record.get("description") == EDITED_DESCRIPTION
                    and record.get("revision") == 2
                ),
                "Редактирование Univer не было сохранено через optimistic PATCH API.",
            )

            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Событие №1"
            ).wait_for(state="visible", timeout=5_000)
            date_control = page.locator('[data-testid="journal-date"]')
            time_control = page.locator('[data-testid="journal-time"]')
            type_control = page.locator('[data-testid="journal-event-type"]')
            report_control = page.locator('[data-testid="journal-report"]')
            close_control = page.locator('[data-testid="journal-close"]')
            _set_control_value(date_control, "2026-07-28")
            _set_control_value(time_control, "12:45")
            type_control.select_option(EDITED_EVENT_TYPE)
            report_control.uncheck()

            _wait_for_record(
                page,
                base_url,
                lambda record, records: (
                    len(records) == 1
                    and record.get("id") == 1
                    and record.get("startAt") == EDITED_START_AT
                    and record.get("eventType") == EDITED_EVENT_TYPE
                    and record.get("eventTypeLabel") == "Диспетчерская команда"
                    and record.get("includeInReport") is False
                    and int(record.get("revision", 0)) >= 6
                ),
                "Специализированные редакторы не сохранили дату, время, тип и рапорт.",
            )

            close_control.click()
            _wait_for_record(
                page,
                base_url,
                lambda record, records: (
                    len(records) == 1
                    and record.get("id") == 1
                    and record.get("status") == "closed"
                    and record.get("endAt") is not None
                    and int(record.get("revision", 0)) >= 7
                ),
                "Явный переход завершения события не был сохранён.",
            )
            close_control.filter(has_text="Событие завершено").wait_for(
                state="visible", timeout=5_000
            )
            if not close_control.is_disabled():
                raise AssertionError("Кнопка завершения осталась доступна для закрытой записи.")

            page.mouse.click(asset_x, row_three_y)
            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Новая строка"
            ).wait_for(state="visible", timeout=5_000)
            _set_control_value(date_control, "2026-07-29")
            _set_control_value(time_control, "13:15")
            type_control.select_option(CREATED_EVENT_TYPE)
            report_control.uncheck()
            _assert_incomplete_draft_not_persisted(page, base_url)

            page.mouse.dblclick(asset_x, row_three_y)
            page.keyboard.press("Control+A")
            page.keyboard.type(CREATED_ASSET)
            page.keyboard.press("Enter")
            _assert_incomplete_draft_not_persisted(page, base_url)

            page.mouse.dblclick(description_x, row_three_y)
            page.keyboard.press("Control+A")
            page.keyboard.type(CREATED_DESCRIPTION)
            page.keyboard.press("Enter")
            _wait_for_record(
                page,
                base_url,
                lambda record, records: (
                    len(records) == 2
                    and record.get("assetLabel") == CREATED_ASSET
                    and record.get("description") == CREATED_DESCRIPTION
                    and record.get("startAt") == CREATED_START_AT
                    and record.get("eventType") == CREATED_EVENT_TYPE
                    and record.get("eventTypeLabel") == "Пуск"
                    and record.get("revision") == 1
                    and record.get("includeInReport") is False
                    and record.get("status") == "open"
                ),
                "Новая строка Univer не была создана через POST API с параметрами редактора.",
            )

            batch_text = (
                f"{BATCH_FIRST_DESCRIPTION}\t{BATCH_FIRST_REASON}\n"
                f"{BATCH_SECOND_DESCRIPTION}\t{BATCH_SECOND_REASON}"
            )
            page.mouse.click(description_x, row_two_y)
            page.evaluate("text => navigator.clipboard.writeText(text)", batch_text)
            page.keyboard.press("Control+V")
            _wait_for_snapshot(
                page,
                base_url,
                lambda records: (
                    len(records) == 2
                    and records[0].get("description") == BATCH_FIRST_DESCRIPTION
                    and records[0].get("reason") == BATCH_FIRST_REASON
                    and int(records[0].get("revision", 0)) >= 8
                    and records[1].get("description") == BATCH_SECOND_DESCRIPTION
                    and records[1].get("reason") == BATCH_SECOND_REASON
                    and records[1].get("revision") == 2
                ),
                "Ctrl+V не был сохранён одной транзакционной batch-операцией.",
            )

            page.locator(".shift-helper-v2__status").filter(
                has_text="Загружено записей: 2"
            ).wait_for(state="visible", timeout=10_000)
            page.locator(".shift-helper-v2__status").filter(
                has_text="все изменения сохранены"
            ).wait_for(state="visible", timeout=10_000)

            page.mouse.click(description_x, row_two_y)
            page.keyboard.press("Control+B")
            presentation_revision = _wait_for_presentation_style(page, base_url)
            page.locator('.shift-helper-v2__status[data-presentation-state="saved"]').wait_for(
                state="visible", timeout=10_000
            )

            page.reload(wait_until="networkidle")
            page.locator(".shift-helper-v2__status").filter(
                has_text="Загружено записей: 2"
            ).wait_for(state="visible", timeout=30_000)
            _wait_for_working_canvas(page)
            reloaded_presentation = _presentation(page, base_url)
            if reloaded_presentation.get("revision") != presentation_revision:
                raise AssertionError("Ревизия оформления изменилась или потерялась после reload.")

            if page_errors:
                raise AssertionError("Page errors: " + " | ".join(page_errors))
            if console_errors:
                raise AssertionError("Console errors: " + " | ".join(console_errors))

            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            page.screenshot(path=str(screenshot_path), full_page=True)
            raise
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
