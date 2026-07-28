"""Browser regression checks derived from the 2026-07-28 operator video."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def wait_repair(page: Page) -> None:
    page.wait_for_function(
        """() => {
            const root = document.getElementById('event-journal');
            return root?.dataset.videoAcceptanceRepair === 'ready'
                && root?.dataset.operatorRepairReady === 'true';
        }""",
        timeout=20_000,
    )


def set_zoom(page: Page, value: int) -> None:
    immediate = page.evaluate(
        """value => {
            const input = document.getElementById('ribbon-zoom');
            const root = document.getElementById('event-journal');
            input.value = String(value);
            input.dispatchEvent(new Event('input', {bubbles: true}));
            return {
                rows: root.querySelectorAll('.tabulator-row').length,
                width: root.getBoundingClientRect().width,
                height: root.getBoundingClientRect().height,
                display: getComputedStyle(root).display,
            };
        }""",
        value,
    )
    require(immediate["rows"] > 0, "Zoom temporarily removed all rendered rows.")
    require(immediate["width"] > 100 and immediate["height"] > 100, "Zoom collapsed the grid.")
    require(immediate["display"] != "none", "Zoom hid the grid container.")
    page.wait_for_function(
        """value => {
            const root = document.getElementById('event-journal');
            return root?.dataset.sheetZoom === String(value)
                && root.dataset.zoomApplying !== 'true';
        }""",
        value,
        timeout=10_000,
    )


def disable_frozen_columns(page: Page) -> None:
    page.locator('[data-ribbon-tab="view"]').click()
    page.locator("#open-view-settings").click()
    dialog = page.locator("#journal-view-settings")
    dialog.wait_for(state="visible", timeout=5_000)
    page.locator("#journal-frozen-through").select_option("none")
    page.wait_for_function(
        """() => {
            const root = document.getElementById('event-journal');
            return root?.dataset.frozenColumnsApplied === 'none';
        }""",
        timeout=10_000,
    )
    dialog.locator('button[value="close"]').last.click()
    dialog.wait_for(state="hidden", timeout=5_000)


def geometry_snapshot(page: Page) -> dict:
    return page.evaluate(
        """() => {
            const root = document.getElementById('event-journal');
            const holder = root.querySelector('.tabulator-tableholder');
            const holderRect = holder.getBoundingClientRect();
            const rows = [...root.querySelectorAll('.tabulator-row')].filter(row => {
                const rect = row.getBoundingClientRect();
                return rect.bottom > holderRect.top + 8 && rect.top < holderRect.bottom - 8;
            });
            const row = rows[Math.floor(rows.length / 2)];
            const fields = ['start_date', 'start_time', 'asset_label', 'description'];
            const result = {rowCount: rows.length, fields: {}};
            for (const field of fields) {
                const header = root.querySelector(`.tabulator-col[tabulator-field="${field}"]`);
                const cell = row?.querySelector(`.tabulator-cell[tabulator-field="${field}"]`);
                if (!header || !cell) continue;
                const h = header.getBoundingClientRect();
                const c = cell.getBoundingClientRect();
                result.fields[field] = {
                    headerLeft: h.left,
                    headerWidth: h.width,
                    cellLeft: c.left,
                    cellWidth: c.width,
                };
            }
            return result;
        }"""
    )


def assert_aligned(snapshot: dict, stage: str) -> None:
    require(snapshot["rowCount"] > 0, f"No visible rows at {stage}.")
    require(len(snapshot["fields"]) == 4, f"Required cells are missing at {stage}.")
    for field, metric in snapshot["fields"].items():
        require(
            abs(metric["headerLeft"] - metric["cellLeft"]) <= 2,
            f"{field} left edge diverged after {stage}: {metric}",
        )
        require(
            abs(metric["headerWidth"] - metric["cellWidth"]) <= 2,
            f"{field} width diverged after {stage}: {metric}",
        )


def test_virtualized_geometry(page: Page) -> None:
    holder = page.locator(".tabulator-tableholder")
    set_zoom(page, 150)
    require(
        page.locator("body").evaluate("element => element.style.zoom") == "",
        "Body CSS zoom returned.",
    )
    require(
        page.locator("#event-journal").evaluate("element => element.style.zoom") == "",
        "Grid CSS zoom returned.",
    )
    assert_aligned(geometry_snapshot(page), "initial 150% rendering")

    holder.evaluate("element => { element.scrollTop = Math.max(0, element.scrollHeight * 0.55); }")
    page.wait_for_timeout(500)
    assert_aligned(geometry_snapshot(page), "deep vertical virtualization")

    holder.evaluate("element => { element.scrollTop = Math.max(0, element.scrollHeight * 0.82); }")
    page.wait_for_timeout(500)
    assert_aligned(geometry_snapshot(page), "second virtualized row batch")

    set_zoom(page, 90)
    assert_aligned(geometry_snapshot(page), "90% zoom after scrolling")
    set_zoom(page, 100)
    assert_aligned(geometry_snapshot(page), "100% zoom restoration")


def test_exclusive_selection(page: Page) -> None:
    holder = page.locator(".tabulator-tableholder")
    holder.evaluate("element => { element.scrollTop = 0; element.scrollLeft = 0; }")
    page.wait_for_timeout(300)
    root = page.locator("#event-journal")
    header = page.locator('.tabulator-col[tabulator-field="description"]')
    header.click(position={"x": 42, "y": 14})
    page.wait_for_timeout(100)
    require(
        root.get_attribute("data-selection-mode") == "columns",
        "Column selection mode was not entered.",
    )
    require(
        page.locator(".operator-column-selected").count() == 1,
        "Column header selection is ambiguous.",
    )
    require(
        page.locator(".journal-active-cell").count() == 0,
        "An active cell remained over a selected column.",
    )
    require(
        page.locator(".journal-fill-handle:visible").count() == 0,
        "The fill handle remained visible in column mode.",
    )

    row = page.locator(".tabulator-row:visible").nth(1)
    cell = row.locator('.tabulator-cell[tabulator-field="asset_label"]')
    cell.click()
    page.wait_for_timeout(150)
    require(
        root.get_attribute("data-selection-mode") == "cells",
        "Cell click did not leave column mode.",
    )
    require(
        page.locator(".operator-column-selected").count() == 0,
        "Column highlight remained after cell click.",
    )
    require(
        page.locator(".journal-active-cell").count() == 1,
        "Exactly one active cell was not established.",
    )
    require(page.locator(".journal-fill-handle").count() <= 1, "Multiple fill handles exist.")

    row.locator(".journal-row-number").click()
    page.wait_for_timeout(150)
    require(
        root.get_attribute("data-selection-mode") == "rows",
        "Row click did not enter row mode.",
    )
    require(
        page.locator(".operator-column-selected").count() == 0,
        "Column highlight remained in row mode.",
    )
    require(
        page.locator(".journal-active-cell").count() == 0,
        "Active-cell outline remained in row mode.",
    )
    require(
        page.locator(".journal-fill-handle:visible").count() == 0,
        "Fill handle remained in row mode.",
    )


def test_text_color_palette(page: Page) -> None:
    page.locator('[data-ribbon-tab="home"]').click()
    native = page.locator("#ribbon-text-color")
    require(
        native.locator("xpath=ancestor::label[1]").evaluate(
            "element => getComputedStyle(element).display === 'none'"
        ),
        "The native text Color Picker is still exposed.",
    )
    page.locator(".operator-text-color-arrow").click()
    palette = page.locator('.operator-color-palette[data-owner="text"]')
    palette.wait_for(state="visible", timeout=5_000)
    require(palette.locator(".operator-color-swatch").count() >= 32, "Text palette is incomplete.")
    palette.locator('[title="#c00000"]').click()


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
            wait_repair(page)
            disable_frozen_columns(page)
            test_virtualized_geometry(page)
            test_exclusive_selection(page)
            test_text_color_palette(page)
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
        raise SystemExit("Usage: ui_smoke_video_regression.py <base-url> [screenshot-path]")
    screenshot = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-video-regression-failure.png")
    run(sys.argv[1], screenshot)
    print("Shift-Helper operator-video regression smoke passed.")


if __name__ == "__main__":
    main()
