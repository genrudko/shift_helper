"""Focused acceptance checks for the Insert tab and technical symbols."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def wait_ready(page: Page) -> None:
    page.wait_for_function(
        """() => {
            const root = document.getElementById('event-journal');
            return root?.dataset.acceptanceStage5 === 'ready'
                && root.dataset.acceptanceStage5Loaded === 'true'
                && Boolean(window.shiftHelperAcceptanceStage5);
        }""",
        timeout=20_000,
    )


def select_target_cell(page: Page) -> tuple[str, str]:
    target = page.locator(
        '.tabulator-row:visible .tabulator-cell[tabulator-field="description"]'
    ).first
    target.click()
    page.wait_for_timeout(100)
    identity = page.evaluate(
        """() => {
            const cell = window.shiftHelperAcceptanceStage4.selectedCells()[0];
            return {
                rowKey: cell.getRow().getData()._rowKey,
                before: String(cell.getValue() ?? ''),
            };
        }"""
    )
    return identity["rowKey"], identity["before"]


def cell_value(page: Page, row_key: str) -> str:
    return page.evaluate(
        """rowKey => {
            const row = window.shiftHelperEventGrid.getRows('active')
                .find(candidate => candidate.getData()._rowKey === rowKey);
            return String(row.getCell('description').getValue() ?? '');
        }""",
        row_key,
    )


def open_symbol_dialog(page: Page) -> None:
    page.locator('[data-ribbon-tab="insert"]').click()
    require(
        page.locator('[data-ribbon-tab="insert"]').get_attribute("aria-selected") == "true",
        "The Insert tab did not become active.",
    )
    require(
        page.locator('[data-ribbon-panel="insert"]').is_visible(),
        "The Insert panel is not visible.",
    )
    page.locator("#stage5-open-symbols").click()
    page.locator("#stage5-symbol-dialog").wait_for(state="visible", timeout=5_000)


def test_symbol_insertion(page: Page) -> None:
    row_key, before = select_target_cell(page)
    open_symbol_dialog(page)

    require(
        page.locator('#stage5-symbol-category option[value="greek"]').count() == 1,
        "The Greek category is missing.",
    )
    require(
        page.locator('#stage5-symbol-category option[value="roman"]').count() == 1,
        "The Roman category is missing.",
    )
    require(
        page.locator('#stage5-symbol-category option[value="electrical"]').count() == 1,
        "The electrical category is missing.",
    )

    page.locator('#stage5-symbol-grid [data-symbol="Ω"]').first.click()
    page.wait_for_timeout(150)
    require(cell_value(page, row_key) == f"{before}Ω", "Omega was not appended to the selected cell.")
    require(
        page.locator('#stage5-symbol-recent [data-symbol="Ω"]').count() >= 1,
        "Inserted Omega did not appear in recent symbols.",
    )

    page.locator("#stage5-symbol-search").fill("римское IV")
    page.wait_for_timeout(100)
    require(
        page.locator('#stage5-symbol-grid [data-symbol="Ⅳ"]').count() == 1,
        "Roman numeral IV was not found by name.",
    )
    page.locator('#stage5-symbol-grid [data-symbol="Ⅳ"]').click()
    page.wait_for_timeout(150)
    require(cell_value(page, row_key) == f"{before}ΩⅣ", "Roman numeral IV was not inserted.")

    page.keyboard.press("Escape")
    page.locator("#stage5-symbol-dialog").wait_for(state="hidden", timeout=5_000)


def test_quick_symbol(page: Page) -> None:
    row_key, before = select_target_cell(page)
    page.locator('[data-ribbon-tab="insert"]').click()
    page.locator('.stage5-symbol-quick button', has_text="±").click()
    page.wait_for_timeout(150)
    require(cell_value(page, row_key) == f"{before}±", "Quick symbol ± was not inserted.")


def run(url: str, screenshot: Path) -> None:
    browser_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1680, "height": 960})
        page = context.new_page()
        page.on("pageerror", lambda error: browser_errors.append(f"pageerror: {error}"))
        page.on(
            "console",
            lambda message: browser_errors.append(f"console: {message.text}")
            if message.type == "error"
            else None,
        )
        try:
            page.goto(f"{url.rstrip('/')}/events", wait_until="networkidle")
            page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)
            wait_ready(page)
            test_symbol_insertion(page)
            page.reload(wait_until="networkidle")
            page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)
            wait_ready(page)
            require(
                page.evaluate("JSON.parse(localStorage.getItem('shift-helper-recent-symbols-v1') || '[]')")[:2]
                == ["Ⅳ", "Ω"],
                "Recent symbols were not restored after reload.",
            )
            test_quick_symbol(page)
            require(not browser_errors, "Browser errors: " + " | ".join(browser_errors))
        except Exception:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot), full_page=True)
            raise
        finally:
            context.close()
            browser.close()


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: ui_smoke_acceptance_stage5.py <base-url> [screenshot-path]")
    screenshot = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-stage5-failure.png")
    run(sys.argv[1], screenshot)
    print("Shift-Helper acceptance stage 5 smoke passed.")


if __name__ == "__main__":
    main()
