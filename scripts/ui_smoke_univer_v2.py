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


def _wait_for_record(
    page: Page,
    base_url: str,
    predicate,
    failure_message: str,
) -> dict[str, object]:
    for _attempt in range(120):
        snapshot = _snapshot(page, base_url)
        records = snapshot.get("records", [])
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict) and predicate(record, records):
                    return record
        page.wait_for_timeout(100)
    raise AssertionError(failure_message)


def _assert_incomplete_draft_not_persisted(page: Page, base_url: str) -> None:
    page.wait_for_timeout(500)
    snapshot = _snapshot(page, base_url)
    records = snapshot.get("records", [])
    if not isinstance(records, list) or len(records) != 1:
        raise AssertionError("Незавершённая строка ошибочно создала запись в SQLite.")


def _set_control_value(locator: Locator, value: str) -> None:
    locator.fill(value)
    locator.dispatch_event("change")


def main() -> None:
    base_url = os.environ.get("SHIFT_HELPER_BASE_URL", "http://127.0.0.1:17944")
    screenshot_path = Path(
        os.environ.get("SHIFT_HELPER_UI_SCREENSHOT", "ui-v2-smoke/univer-v2.png")
    )
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
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

            canvas_count = page.locator("canvas").count()
            if canvas_count < 1:
                raise AssertionError("Univer не создал ни одного canvas.")

            visible_canvas = False
            for index in range(canvas_count):
                canvas = page.locator("canvas").nth(index)
                box = canvas.bounding_box()
                if box and box["width"] > 500 and box["height"] > 300:
                    visible_canvas = True
                    break
            if not visible_canvas:
                raise AssertionError("Univer canvas не получил рабочую геометрию журнала.")

            sheet_box = page.locator("#univer-sheet").bounding_box()
            if sheet_box is None:
                raise AssertionError("Не удалось определить геометрию контейнера Univer.")
            row_two_y = sheet_box["y"] + 173
            row_three_y = row_two_y + 32
            asset_x = sheet_box["x"] + 340
            description_x = sheet_box["x"] + 690

            # Real canvas editing of an existing persisted row.
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

            # The selected persisted row exposes dedicated date/time/type/report
            # controls. Four rapid changes must serialize revisions without losing
            # either half of the date-time value.
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

            # Select the only draft row and set its dedicated fields before the
            # mandatory spreadsheet cells. This must still create no record.
            page.mouse.click(asset_x, row_three_y)
            page.locator('[data-testid="journal-selection"]').filter(
                has_text="Новая строка"
            ).wait_for(state="visible", timeout=5_000)
            _set_control_value(date_control, "2026-07-29")
            _set_control_value(time_control, "13:15")
            type_control.select_option(CREATED_EVENT_TYPE)
            report_control.uncheck()
            _assert_incomplete_draft_not_persisted(page, base_url)

            # Filling one required cell must not create a partial database row.
            page.mouse.dblclick(asset_x, row_three_y)
            page.keyboard.press("Control+A")
            page.keyboard.type(CREATED_ASSET)
            page.keyboard.press("Enter")
            _assert_incomplete_draft_not_persisted(page, base_url)

            # Completing the second required cell creates exactly one event,
            # converts the draft to a persisted row and appends a fresh draft.
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

            page.locator(".shift-helper-v2__status").filter(
                has_text="Загружено записей: 2"
            ).wait_for(state="visible", timeout=10_000)
            page.locator(".shift-helper-v2__status").filter(
                has_text="все изменения сохранены"
            ).wait_for(state="visible", timeout=10_000)

            if page_errors:
                raise AssertionError("Page errors: " + " | ".join(page_errors))
            if console_errors:
                raise AssertionError("Console errors: " + " | ".join(console_errors))

            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            page.screenshot(path=str(screenshot_path), full_page=True)
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
