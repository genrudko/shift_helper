"""Browser smoke test for the Shift-Helper event spreadsheet."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def edit_cell(page: Page, field: str, value: str) -> None:
    row = page.locator(".journal-row--draft").first
    cell = row.locator(f'.tabulator-cell[tabulator-field="{field}"]')
    cell.dblclick()
    editor = cell.locator("input, textarea").first
    editor.wait_for(state="visible")
    editor.fill(value)
    if editor.evaluate("element => element.tagName") == "TEXTAREA":
        page.locator("#journal-title").click()
    else:
        page.keyboard.press("Enter")


def run_smoke(url: str, screenshot_path: Path) -> None:
    browser_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
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
            ):
                require(expected in headers, f"Missing spreadsheet column: {expected}")

            require(
                page.locator(".journal-row--draft").count() >= 20,
                "The spreadsheet did not render its draft-row reserve.",
            )
            require(
                page.locator(".tabulator-col-resize-handle").count() >= 8,
                "Resizable column handles are absent.",
            )
            require(
                page.locator(".tabulator-header-filter input").count() >= 8,
                "Column header filters are absent.",
            )

            edit_cell(page, "asset_label", "ВЭУ №11")
            edit_cell(page, "description", "Проверка spreadsheet-интерфейса")

            page.locator('#journal-save-state[data-state="saved"]').wait_for(
                state="visible",
                timeout=15_000,
            )
            page.wait_for_timeout(500)

            page.reload(wait_until="networkidle")
            page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)
            require(
                page.get_by_text("Проверка spreadsheet-интерфейса", exact=True).count() >= 1,
                "A row entered through the grid was not persisted.",
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
            search.fill("")

            description_cell = page.locator(
                '.tabulator-row:not(.journal-row--draft) '
                '.tabulator-cell[tabulator-field="description"]'
            ).first
            description_cell.click()
            page.locator('[data-align-horizontal="center"]').click()
            require(
                description_cell.locator(
                    '.journal-cell-value[data-horizontal="center"]'
                ).count()
                == 1,
                "Per-cell horizontal alignment was not applied.",
            )

            require(not browser_errors, "Browser errors: " + " | ".join(browser_errors))
        except Exception:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_path), full_page=True)
            raise
        finally:
            browser.close()


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: ui_smoke.py <base-url> [screenshot-path]")
    screenshot_path = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-smoke-failure.png")
    run_smoke(sys.argv[1], screenshot_path)
    print("Shift-Helper spreadsheet UI smoke test passed.")


if __name__ == "__main__":
    main()
