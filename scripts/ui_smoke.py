"""Browser smoke test for the Shift-Helper event spreadsheet."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def draft_cell(page: Page, field: str) -> Locator:
    return page.locator(".journal-row--draft").first.locator(
        f'.tabulator-cell[tabulator-field="{field}"]'
    )


def begin_typing(page: Page, cell: Locator, seed: str = "1") -> Locator:
    cell.click()
    page.keyboard.type(seed)
    editor = cell.locator("input.journal-excel-editor, textarea.journal-excel-editor")
    editor.wait_for(state="visible", timeout=5_000)
    return editor


def direct_edit(page: Page, cell: Locator, value: str) -> None:
    editor = begin_typing(page, cell)
    editor.fill(value)
    page.keyboard.press("Enter")
    editor.wait_for(state="hidden", timeout=5_000)


def assert_blank_draft_dates(page: Page, count: int = 5) -> None:
    rows = page.locator(".journal-row--draft")
    require(rows.count() >= count, "The spreadsheet lost its draft-row reserve.")
    for index in range(count):
        row = rows.nth(index)
        date_text = row.locator(
            '.tabulator-cell[tabulator-field="start_date"]'
        ).inner_text().strip()
        time_text = row.locator(
            '.tabulator-cell[tabulator-field="start_time"]'
        ).inner_text().strip()
        require(
            not date_text and not time_text,
            f"Draft row {index + 1} was unexpectedly seeded with date/time.",
        )


def run_smoke(url: str, screenshot_path: Path) -> None:
    browser_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 900},
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = context.new_page()
        page.on("pageerror", lambda error: browser_errors.append(f"pageerror: {error}"))
        page.on(
            "console",
            lambda message: (
                browser_errors.append(f"console: {message.text}")
                if message.type == "error"
                else None
            ),
        )

        try:
            page.goto(f"{url.rstrip('/')}/events", wait_until="networkidle")
            page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)

            headers = page.locator(".tabulator-col-title").all_inner_texts()
            for expected in (
                "Дата останова",
                "№ ВЭУ / оборудование",
                "Описание события",
                "Действия персонала",
                "Кто внёс запись",
                "Потери от простоя, руб.",
            ):
                require(expected in headers, f"Missing spreadsheet column: {expected}")

            require(
                page.locator(".tabulator-col-resize-handle").count() >= 8,
                "Resizable column handles are absent.",
            )
            require(
                page.locator(".tabulator-header-filter input").count() >= 8,
                "Column header filters are absent.",
            )
            assert_blank_draft_dates(page)

            direct_edit(page, draft_cell(page, "start_date"), "26.07.2026")
            direct_edit(page, draft_cell(page, "start_time"), "18:10")
            direct_edit(page, draft_cell(page, "asset_label"), "ВЭУ №11")

            description = draft_cell(page, "description")
            editor = begin_typing(page, description)
            editor.fill("Проверка spreadsheet-интерфейса")
            page.keyboard.press("Shift+Enter")
            page.keyboard.insert_text("Вторая строка")
            require(
                "\n" in editor.input_value(),
                "Shift+Enter did not insert a line break in a multiline cell.",
            )
            page.keyboard.press("Enter")
            editor.wait_for(state="hidden", timeout=5_000)

            page.locator('#journal-save-state[data-state="saved"]').wait_for(
                state="visible",
                timeout=15_000,
            )
            page.wait_for_timeout(500)
            assert_blank_draft_dates(page)

            saved_row = page.locator(".tabulator-row:not(.journal-row--draft)").first
            direct_edit(
                page,
                saved_row.locator('.tabulator-cell[tabulator-field="end_date"]'),
                "26.07.2026",
            )
            direct_edit(
                page,
                saved_row.locator('.tabulator-cell[tabulator-field="end_time"]'),
                "20:40",
            )
            page.locator('#journal-save-state[data-state="saved"]').wait_for(
                state="visible",
                timeout=15_000,
            )
            page.wait_for_timeout(500)
            require(
                "6 250" in saved_row.locator(
                    '.tabulator-cell[tabulator-field="downtime_losses_rub"]'
                ).inner_text(),
                "Downtime losses were not calculated with the source workbook formula.",
            )

            description_cell = saved_row.locator(
                '.tabulator-cell[tabulator-field="description"]'
            )
            description_cell.click()
            page.locator("#cell-fill-color").evaluate(
                "element => { element.value = '#fff2cc'; element.dispatchEvent(new Event('input')); }"
            )
            page.locator("#apply-cell-fill").click()
            require(
                "rgb(255, 242, 204)" in description_cell.get_attribute("style"),
                "Manual cell fill was not applied.",
            )

            page.reload(wait_until="networkidle")
            page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)
            require(
                page.get_by_text("Проверка spreadsheet-интерфейса", exact=False).count() >= 1,
                "A row entered through direct typing was not persisted.",
            )

            search = page.locator("#journal-search")
            search.fill("spreadsheet-интерфейса")
            page.wait_for_timeout(250)
            require(
                page.locator(".tabulator-row:not(.journal-row--draft)").count() >= 1,
                "Global journal search did not retain the matching record.",
            )
            search.fill("несуществующее-значение")
            page.wait_for_timeout(250)
            require(
                page.locator(".tabulator-row:not(.journal-row--draft)").count() == 0,
                "Global journal search did not hide nonmatching records.",
            )

            require(not browser_errors, "Browser errors: " + " | ".join(browser_errors))
        except Exception:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_path), full_page=True)
            raise
        finally:
            context.close()
            browser.close()


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: ui_smoke.py <base-url> [screenshot-path]")
    screenshot_path = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-smoke-failure.png")
    run_smoke(sys.argv[1], screenshot_path)
    print("Shift-Helper spreadsheet UI smoke test passed.")


if __name__ == "__main__":
    main()
