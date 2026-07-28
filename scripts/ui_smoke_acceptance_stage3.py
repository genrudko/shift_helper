"""Focused acceptance checks for Ribbon geometry, font-size dropdown and borders."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def wait_ready(page: Page) -> None:
    page.wait_for_function(
        """() => {
            const root = document.getElementById('event-journal');
            return root?.dataset.acceptanceStage1 === 'ready'
                && root.dataset.acceptanceStage2 === 'ready'
                && root.dataset.acceptanceStage3 === 'ready'
                && Boolean(window.shiftHelperAcceptanceStage3);
        }""",
        timeout=20_000,
    )


def box(locator: Locator) -> dict[str, float]:
    result = locator.bounding_box()
    require(result is not None, f"Control geometry is unavailable for {locator}.")
    return result


def select_description(page: Page) -> str:
    page.locator('[data-ribbon-tab="home"]').click()
    cell = page.locator(
        '.tabulator-row:visible .tabulator-cell[tabulator-field="description"]'
    ).first
    cell.click()
    page.wait_for_timeout(100)
    return page.evaluate(
        """() => window.shiftHelperEventGrid.getRows('visible')[0].getData()._rowKey"""
    )


def cell_font_size(page: Page, row_key: str) -> str:
    return page.evaluate(
        """rowKey => {
            const row = window.shiftHelperEventGrid.getRows()
                .find(item => item.getData()._rowKey === rowKey);
            return row?.getCell('description')?.getElement?.()
                ?.querySelector('.journal-cell-value')?.style.fontSize || '';
        }""",
        row_key,
    )


def border_widths(page: Page, row_key: str) -> dict[str, str]:
    return page.evaluate(
        """rowKey => {
            const row = window.shiftHelperEventGrid.getRows()
                .find(item => item.getData()._rowKey === rowKey);
            const layer = row?.getCell('description')?.getElement?.()
                ?.querySelector(':scope > .stage3-cell-border-layer');
            if (!layer) return {};
            const style = getComputedStyle(layer);
            return {
                top: style.borderTopWidth,
                right: style.borderRightWidth,
                bottom: style.borderBottomWidth,
                left: style.borderLeftWidth,
            };
        }""",
        row_key,
    )


def test_ribbon_geometry(page: Page) -> None:
    controls = [
        box(page.locator("#ribbon-font-family")),
        box(page.locator("#ribbon-font-size")),
        box(page.locator("#operator-font-decrease")),
        box(page.locator("#operator-font-increase")),
    ]
    heights = [item["height"] for item in controls]
    tops = [item["y"] for item in controls]
    require(max(heights) - min(heights) <= 3, f"Ribbon controls have uneven heights: {heights}")
    require(max(tops) - min(tops) <= 3, f"Ribbon controls are vertically misaligned: {tops}")

    ordered = sorted(controls, key=lambda item: item["x"])
    for left, right in zip(ordered, ordered[1:], strict=True):
        require(
            right["x"] >= left["x"] + left["width"] - 1,
            f"Ribbon controls overlap: {left} / {right}",
        )


def test_font_size_dropdown(page: Page, row_key: str) -> None:
    select = page.locator("#ribbon-font-size")
    options = select.locator("option").all_text_contents()
    require(len(options) >= 18, f"Font-size dropdown is incomplete: {options}")
    require("8" in options and "96" in options, f"Font-size limits are missing: {options}")

    select.select_option("24")
    page.wait_for_timeout(150)
    require(cell_font_size(page, row_key) == "24px", "Dropdown size was not applied.")

    page.locator("#operator-font-decrease").click()
    page.wait_for_timeout(100)
    require(cell_font_size(page, row_key) == "23px", "Decrease-font button did not work.")
    page.locator("#operator-font-increase").click()
    page.wait_for_timeout(100)
    require(cell_font_size(page, row_key) == "24px", "Increase-font button did not work.")


def assert_all_borders(widths: dict[str, str], stage: str) -> None:
    require(widths, f"Border layer is missing at {stage}.")
    require(
        all(width == "2px" for width in widths.values()),
        f"All borders were not applied at {stage}: {widths}",
    )


def test_borders(page: Page, row_key: str) -> None:
    arrow = page.locator("#stage3-border-arrow")
    arrow.click()
    menu = page.locator("#stage3-border-menu")
    menu.wait_for(state="visible", timeout=5_000)
    require(menu.locator("button").count() >= 5, "Borders menu is incomplete.")
    menu.locator('[data-border-mode="all"]').click()
    page.wait_for_timeout(150)
    assert_all_borders(border_widths(page, row_key), "initial border application")

    page.locator('[data-align-horizontal="center"]').click()
    page.wait_for_timeout(350)
    assert_all_borders(border_widths(page, row_key), "alignment change")

    arrow.click()
    menu = page.locator("#stage3-border-menu")
    menu.wait_for(state="visible", timeout=5_000)
    page.keyboard.press("Escape")
    page.wait_for_timeout(100)
    require(menu.count() == 0, "Borders menu did not close on Escape.")


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
            row_key = select_description(page)
            test_ribbon_geometry(page)
            test_font_size_dropdown(page, row_key)
            test_borders(page, row_key)
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
        raise SystemExit("Usage: ui_smoke_acceptance_stage3.py <base-url> [screenshot-path]")
    screenshot = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-stage3-failure.png")
    run(sys.argv[1], screenshot)
    print("Shift-Helper acceptance stage 3 smoke passed.")


if __name__ == "__main__":
    main()
