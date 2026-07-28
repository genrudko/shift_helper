"""Focused acceptance checks for Page Layout and printing."""

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
            return root?.dataset.acceptanceStage6 === 'ready'
                && root.dataset.acceptanceStage6Loaded === 'true'
                && Boolean(window.shiftHelperAcceptanceStage6);
        }""",
        timeout=20_000,
    )


def activate_layout(page: Page) -> None:
    page.locator('[data-ribbon-tab="layout"]').click()
    require(
        page.locator('[data-ribbon-tab="layout"]').get_attribute("aria-selected") == "true",
        "The Page Layout tab did not become active.",
    )
    require(
        page.locator('[data-ribbon-panel="layout"]').is_visible(),
        "The Page Layout panel is not visible.",
    )


def test_page_settings(page: Page) -> None:
    activate_layout(page)
    page.locator("#stage6-paper").select_option("A3")
    page.locator("#stage6-orientation").select_option("portrait")
    page.locator("#stage6-margins").select_option("narrow")
    page.locator("#stage6-fit").select_option("actual")

    page.locator("#stage6-open-setup").click()
    setup = page.locator("#stage6-page-setup-dialog")
    setup.wait_for(state="visible", timeout=5_000)
    page.locator("#stage6-setup-title").fill("Приёмочный журнал")
    page.locator("#stage6-setup-footer").fill("Кочубеевская ВЭС · Stage 6")
    page.locator("#stage6-setup-gridlines").uncheck()
    page.locator("#stage6-setup-repeat").check()
    page.locator("#stage6-save-setup").click()
    setup.wait_for(state="hidden", timeout=5_000)

    state = page.evaluate(
        """() => {
            const root = document.getElementById('event-journal');
            return {
                paper: root.dataset.printPaper,
                orientation: root.dataset.printOrientation,
                margins: root.dataset.printMargins,
                fit: root.dataset.printFit,
                gridlines: root.dataset.printGridlines,
                repeatHeaders: root.dataset.printRepeatHeaders,
                settings: JSON.parse(localStorage.getItem('shift-helper-page-layout-v1') || '{}'),
                pageStyle: document.getElementById('stage6-page-style')?.textContent || '',
            };
        }"""
    )
    require(state["paper"] == "A3", f"Paper size was not applied: {state}")
    require(state["orientation"] == "portrait", f"Orientation was not applied: {state}")
    require(state["margins"] == "narrow", f"Margins were not applied: {state}")
    require(state["fit"] == "actual", f"Print scaling was not applied: {state}")
    require(state["gridlines"] == "false", f"Gridline setting was not applied: {state}")
    require(state["repeatHeaders"] == "true", f"Header repetition was not applied: {state}")
    require(state["settings"].get("title") == "Приёмочный журнал", "Print title was not persisted.")
    require("size: A3 portrait" in state["pageStyle"], f"@page size is incorrect: {state}")
    require("margin: 7mm" in state["pageStyle"], f"@page margin is incorrect: {state}")


def test_preview_and_print(page: Page) -> None:
    page.locator("#stage6-open-preview").click()
    preview = page.locator("#stage6-preview-dialog")
    preview.wait_for(state="visible", timeout=5_000)
    require(
        "A3" in page.locator("#stage6-preview-summary").inner_text(),
        "Preview summary does not contain the paper size.",
    )
    require(
        "книжная" in page.locator("#stage6-preview-summary").inner_text(),
        "Preview summary does not contain the orientation.",
    )
    require(
        page.locator("#stage6-preview-page").get_attribute("data-orientation") == "portrait",
        "Preview page geometry does not match portrait orientation.",
    )
    require(
        page.locator("#stage6-preview-page .stage6-print-table thead th").count() >= 8,
        "Preview does not contain the journal column headers.",
    )
    require(
        page.locator("#stage6-preview-page .stage6-print-table--no-grid").count() == 1,
        "Preview did not hide gridlines.",
    )

    page.evaluate(
        """() => {
            window.print = () => {
                document.getElementById('event-journal').dataset.nativePrintCalled = 'true';
            };
        }"""
    )
    page.locator("#stage6-preview-print").click()
    require(
        page.locator("#event-journal").get_attribute("data-print-invoked") == "true",
        "The Print command did not prepare the print sheet.",
    )
    require(
        page.locator("#event-journal").get_attribute("data-native-print-called") == "true",
        "The Print command did not invoke window.print().",
    )
    require(
        page.locator("#stage6-print-sheet .stage6-print-table thead th").count() >= 8,
        "The semantic print sheet was not built.",
    )
    preview.locator("#stage6-preview-close").click()
    preview.wait_for(state="hidden", timeout=5_000)


def test_restore_and_shortcut(page: Page) -> None:
    page.reload(wait_until="networkidle")
    page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)
    wait_ready(page)
    activate_layout(page)
    require(page.locator("#stage6-paper").input_value() == "A3", "Paper size was not restored.")
    require(
        page.locator("#stage6-orientation").input_value() == "portrait",
        "Orientation was not restored.",
    )
    require(page.locator("#stage6-margins").input_value() == "narrow", "Margins were not restored.")
    require(page.locator("#stage6-fit").input_value() == "actual", "Print scaling was not restored.")

    page.keyboard.press("Control+p")
    page.locator("#stage6-preview-dialog").wait_for(state="visible", timeout=5_000)
    page.locator("#stage6-preview-close").click()


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
            test_page_settings(page)
            test_preview_and_print(page)
            test_restore_and_shortcut(page)
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
        raise SystemExit("Usage: ui_smoke_acceptance_stage6.py <base-url> [screenshot-path]")
    screenshot = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-stage6-failure.png")
    run(sys.argv[1], screenshot)
    print("Shift-Helper acceptance stage 6 smoke passed.")


if __name__ == "__main__":
    main()
