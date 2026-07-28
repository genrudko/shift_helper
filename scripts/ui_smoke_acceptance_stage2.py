"""Focused acceptance checks for formatting persistence and palette lifecycle."""

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
            return root?.dataset.acceptanceStage1 === 'ready'
                && root.dataset.acceptanceStage2 === 'ready'
                && Boolean(window.shiftHelperAcceptanceStage2);
        }""",
        timeout=20_000,
    )


def cell_snapshot(page: Page, row_key: str, field: str) -> dict[str, str]:
    return page.evaluate(
        """([rowKey, field]) => {
            const row = window.shiftHelperEventGrid.getRows()
                .find(item => item.getData()._rowKey === rowKey);
            const cell = row?.getCell(field);
            const element = cell?.getElement?.();
            const value = element?.querySelector('.journal-cell-value');
            if (!element || !value) return {};
            return {
                fontFamily: value.style.fontFamily,
                fontSize: value.style.fontSize,
                fontWeight: value.style.fontWeight,
                fontStyle: value.style.fontStyle,
                textDecoration: value.style.textDecoration,
                color: value.style.color,
                backgroundColor: element.style.backgroundColor,
                horizontal: value.dataset.horizontal || '',
                vertical: value.dataset.vertical || '',
            };
        }""",
        [row_key, field],
    )


def select_description_cell(page: Page) -> tuple[str, str]:
    page.locator('[data-ribbon-tab="home"]').click()
    cell = page.locator(
        '.tabulator-row:visible .tabulator-cell[tabulator-field="description"]'
    ).first
    cell.click()
    page.wait_for_timeout(100)
    row_key = page.evaluate(
        """() => window.shiftHelperEventGrid.getRows('visible')[0].getData()._rowKey"""
    )
    return row_key, "description"


def apply_rich_formatting(page: Page) -> None:
    page.locator("#ribbon-font-family").select_option("Tahoma")
    size = page.locator("#operator-font-size")
    size.fill("18")
    size.press("Enter")
    page.locator('.ribbon-group--font [data-text-style="bold"]').click()
    page.locator('.ribbon-group--font [data-text-style="italic"]').click()
    page.locator('.ribbon-group--font [data-text-style="underline"]').click()

    page.locator(".operator-text-color-arrow").click()
    text_palette = page.locator('.operator-color-palette[data-owner="text"]')
    text_palette.wait_for(state="visible", timeout=5_000)
    text_palette.locator('[title="#c00000"]').click()

    page.locator("#operator-fill-control .operator-fill-arrow").click()
    fill_palette = page.locator('.operator-color-palette:not([data-owner="text"])')
    fill_palette.wait_for(state="visible", timeout=5_000)
    fill_palette.locator('[title="#ffd966"]').click()
    page.wait_for_timeout(250)


def assert_format(snapshot: dict[str, str], stage: str) -> None:
    require("Tahoma" in snapshot.get("fontFamily", ""), f"Font family was lost at {stage}: {snapshot}")
    require(snapshot.get("fontSize") == "18px", f"Font size was lost at {stage}: {snapshot}")
    require(snapshot.get("fontWeight") == "700", f"Bold was lost at {stage}: {snapshot}")
    require(snapshot.get("fontStyle") == "italic", f"Italic was lost at {stage}: {snapshot}")
    require(
        "underline" in snapshot.get("textDecoration", ""),
        f"Underline was lost at {stage}: {snapshot}",
    )
    require(
        snapshot.get("color") in {"rgb(192, 0, 0)", "#c00000"},
        f"Text color was lost at {stage}: {snapshot}",
    )
    require(
        snapshot.get("backgroundColor") in {"rgb(255, 217, 102)", "#ffd966"},
        f"Cell fill was lost at {stage}: {snapshot}",
    )


def test_alignment_preserves_formatting(page: Page) -> None:
    row_key, field = select_description_cell(page)
    apply_rich_formatting(page)
    before = cell_snapshot(page, row_key, field)
    assert_format(before, "initial formatting")

    page.locator('[data-align-horizontal="center"]').click()
    page.wait_for_timeout(350)
    after_horizontal = cell_snapshot(page, row_key, field)
    assert_format(after_horizontal, "horizontal alignment")
    require(
        after_horizontal.get("horizontal") == "center",
        f"Horizontal alignment was not applied: {after_horizontal}",
    )

    page.locator('[data-align-vertical="bottom"]').click()
    page.wait_for_timeout(350)
    after_vertical = cell_snapshot(page, row_key, field)
    assert_format(after_vertical, "vertical alignment")
    require(
        after_vertical.get("vertical") == "bottom",
        f"Vertical alignment was not applied: {after_vertical}",
    )


def test_palette_closes(page: Page) -> None:
    arrow = page.locator(".operator-text-color-arrow")
    arrow.click()
    palette = page.locator('.operator-color-palette[data-owner="text"]')
    palette.wait_for(state="visible", timeout=5_000)
    page.locator("#journal-title").click()
    page.wait_for_timeout(100)
    require(palette.count() == 0, "Text-color palette did not close after an outside click.")

    arrow.click()
    palette = page.locator('.operator-color-palette[data-owner="text"]')
    palette.wait_for(state="visible", timeout=5_000)
    page.keyboard.press("Escape")
    page.wait_for_timeout(100)
    require(palette.count() == 0, "Text-color palette did not close on Escape.")


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
            test_alignment_preserves_formatting(page)
            test_palette_closes(page)
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
        raise SystemExit("Usage: ui_smoke_acceptance_stage2.py <base-url> [screenshot-path]")
    screenshot = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-stage2-failure.png")
    run(sys.argv[1], screenshot)
    print("Shift-Helper acceptance stage 2 smoke passed.")


if __name__ == "__main__":
    main()
