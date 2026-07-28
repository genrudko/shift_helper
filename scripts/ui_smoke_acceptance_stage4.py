"""Focused acceptance checks for Clear and Find/Replace."""

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
            return root?.dataset.acceptanceStage4 === 'ready'
                && root.dataset.acceptanceStage4Loaded === 'true'
                && Boolean(window.shiftHelperAcceptanceStage4);
        }""",
        timeout=20_000,
    )


def prepare_draft_cell(page: Page, value: str) -> str:
    row_key = page.evaluate(
        """async value => {
            const table = window.shiftHelperEventGrid;
            const row = table.getRows('active').find(candidate => candidate.getData()._draft);
            if (!row) throw new Error('No draft row is available.');
            await row.scrollTo('center', false);
            const cell = row.getCell('description');
            cell.setValue(value, true);
            cell.getElement().dataset.stage4Target = 'true';
            return row.getData()._rowKey;
        }""",
        value,
    )
    target = page.locator('[data-stage4-target="true"]')
    target.wait_for(state="visible", timeout=5_000)
    target.click()
    page.wait_for_timeout(120)
    require(
        page.evaluate(
            """() => {
                const range = window.shiftHelperEventGrid.getRanges().at(-1);
                const raw = range?.getCells?.() || [];
                const cells = raw.length && Array.isArray(raw[0]) ? raw.flat() : raw;
                return cells.some(cell => cell.getElement?.()?.dataset.stage4Target === 'true');
            }"""
        ),
        "A real cell click did not move the Tabulator range to the Stage 4 target.",
    )
    return row_key


def cell_snapshot(page: Page, row_key: str, field: str = "description") -> dict:
    return page.evaluate(
        """({rowKey, field}) => {
            const row = window.shiftHelperEventGrid.getRows('active')
                .find(candidate => candidate.getData()._rowKey === rowKey);
            const cell = row.getCell(field);
            const element = cell.getElement();
            const value = element.querySelector('.journal-cell-value');
            return {
                text: String(cell.getValue() ?? ''),
                fontWeight: value.style.fontWeight,
                background: getComputedStyle(element).backgroundColor,
                textAlign: element.style.textAlign || value.style.textAlign,
                borderLayer: Boolean(element.querySelector('.stage3-cell-border-layer')),
            };
        }""",
        {"rowKey": row_key, "field": field},
    )


def open_clear_menu(page: Page) -> None:
    page.locator("#stage4-clear-arrow").click()
    page.locator("#stage4-clear-menu").wait_for(state="visible", timeout=5_000)


def test_clear_menu(page: Page) -> None:
    initial = "STAGE4_FORMAT_KEEP"
    row_key = prepare_draft_cell(page, initial)

    page.locator('[data-text-style="bold"]').first.click()
    page.evaluate(
        """() => {
            const input = document.getElementById('cell-fill-color');
            input.value = '#ffd966';
            document.getElementById('apply-cell-fill').click();
        }"""
    )
    page.locator('[data-align-horizontal="center"]').click()
    page.locator("#stage3-border-arrow").click()
    page.locator('#stage3-border-menu [data-border-mode="all"]').click()
    page.wait_for_timeout(250)

    formatted = cell_snapshot(page, row_key)
    require(formatted["text"] == initial, "Formatting changed the cell value.")
    require(formatted["fontWeight"] == "700", "Bold formatting was not applied.")
    require(formatted["background"] == "rgb(255, 217, 102)", "Fill was not applied.")
    require(formatted["textAlign"] == "center", "Horizontal alignment was not applied.")
    require(formatted["borderLayer"], "Cell borders were not applied.")

    open_clear_menu(page)
    page.locator('#stage4-clear-menu [data-clear-mode="formats"]').click()
    page.wait_for_timeout(300)

    cleared = cell_snapshot(page, row_key)
    require(cleared["text"] == initial, "Clear formatting removed the cell content.")
    require(cleared["fontWeight"] != "700", "Clear formatting left bold text behind.")
    require(cleared["background"] != "rgb(255, 217, 102)", "Clear formatting left fill behind.")
    require(cleared["textAlign"] == "left", "Clear formatting did not restore default alignment.")
    require(not cleared["borderLayer"], "Clear formatting left cell borders behind.")

    stores = page.evaluate(
        """({rowKey}) => {
            const read = key => JSON.parse(localStorage.getItem(key) || '{}');
            return {
                text: read('shift-helper-event-cell-text-style-v1')[rowKey]?.description || null,
                alignment: read('shift-helper-event-cell-alignment-v3')[rowKey]?.description || null,
                fill: read('shift-helper-event-cell-fill-v3')[rowKey]?.description || null,
                border: read('shift-helper-event-cell-border-v1')[rowKey]?.description || null,
            };
        }""",
        {"rowKey": row_key},
    )
    require(not any(stores.values()), f"Formatting stores were not cleared: {stores}")

    open_clear_menu(page)
    page.locator('#stage4-clear-menu [data-clear-mode="contents"]').click()
    page.wait_for_timeout(200)
    require(cell_snapshot(page, row_key)["text"] == "", "Clear contents did not empty the cell.")


def prepare_search_values(page: Page) -> list[str]:
    return page.evaluate(
        """async () => {
            const rows = window.shiftHelperEventGrid.getRows('active')
                .filter(row => row.getData()._draft)
                .slice(0, 2);
            if (rows.length < 2) throw new Error('Two draft rows are required.');
            const values = ['STAGE4_FIND_TOKEN one', 'prefix STAGE4_FIND_TOKEN two'];
            for (let index = 0; index < rows.length; index += 1) {
                rows[index].getCell('description').setValue(values[index], true);
            }
            return rows.map(row => row.getData()._rowKey);
        }"""
    )


def test_find_replace(page: Page) -> None:
    row_keys = prepare_search_values(page)
    page.locator('[data-ribbon-tab="data"]').click()
    page.locator("#stage4-open-find").click()
    dialog = page.locator("#stage4-find-dialog")
    dialog.wait_for(state="visible", timeout=5_000)

    page.locator("#stage4-find-text").fill("STAGE4_FIND_TOKEN")
    page.locator("#stage4-replace-text").fill("STAGE4_REPLACED")
    page.locator("#stage4-find-all").click()
    page.wait_for_timeout(150)
    require(
        "2" in page.locator("#stage4-find-status").inner_text(),
        "Find all did not report both matching cells.",
    )
    require(page.locator(".stage4-find-match").count() >= 1, "Find all did not mark visible matches.")

    page.locator("#stage4-replace-all").click()
    page.wait_for_timeout(300)
    values = page.evaluate(
        """rowKeys => rowKeys.map(rowKey => {
            const row = window.shiftHelperEventGrid.getRows('active')
                .find(candidate => candidate.getData()._rowKey === rowKey);
            return String(row.getCell('description').getValue() ?? '');
        })""",
        row_keys,
    )
    require(all("STAGE4_REPLACED" in value for value in values), f"Replace all failed: {values}")
    require(all("STAGE4_FIND_TOKEN" not in value for value in values), f"Old text remains: {values}")

    dialog.locator(".stage4-find-close").click()
    dialog.wait_for(state="hidden", timeout=5_000)
    page.keyboard.press("Control+f")
    dialog.wait_for(state="visible", timeout=5_000)
    require(
        page.locator("#stage4-find-text").evaluate(
            "element => document.activeElement === element"
        ),
        "Ctrl+F did not focus the Find field.",
    )
    dialog.locator(".stage4-find-close").click()


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
            test_clear_menu(page)
            test_find_replace(page)
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
        raise SystemExit("Usage: ui_smoke_acceptance_stage4.py <base-url> [screenshot-path]")
    screenshot = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-stage4-failure.png")
    run(sys.argv[1], screenshot)
    print("Shift-Helper acceptance stage 4 smoke passed.")


if __name__ == "__main__":
    main()
