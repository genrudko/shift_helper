"""Focused acceptance checks for configurable per-column dropdown lists."""

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
            return root?.dataset.acceptanceStage7 === 'ready'
                && root.dataset.acceptanceStage7Loaded === 'true'
                && Boolean(window.shiftHelperAcceptanceStage7);
        }""",
        timeout=20_000,
    )


def configure_performer_list(page: Page) -> None:
    page.locator('[data-ribbon-tab="data"]').click()
    page.locator("#stage7-open-lists").click()
    dialog = page.locator("#stage7-list-dialog")
    dialog.wait_for(state="visible", timeout=5_000)

    page.locator("#stage7-list-field").select_option("performer")
    page.locator("#stage7-list-values").fill(
        "Иванов И.И.\nПетров П.П.\nСидоров С.С."
    )
    page.locator("#stage7-list-enabled").check()
    page.locator("#stage7-list-autocomplete").check()
    page.locator("#stage7-list-custom").uncheck()
    page.locator("#stage7-save-list").click()
    dialog.wait_for(state="hidden", timeout=5_000)

    config = page.evaluate(
        """() => JSON.parse(
            localStorage.getItem('shift-helper-column-lists-v1') || '{}'
        ).performer"""
    )
    require(config["enabled"] is True, f"Performer list was not enabled: {config}")
    require(config["autocomplete"] is True, f"Autocomplete was not enabled: {config}")
    require(config["allowCustom"] is False, f"Custom values remain enabled: {config}")
    require(
        config["values"] == ["Иванов И.И.", "Петров П.П.", "Сидоров С.С."],
        f"Configured values are incorrect: {config}",
    )
    require(
        page.locator(
            '.tabulator-cell[tabulator-field="performer"].stage7-list-cell'
        ).count()
        >= 1,
        "Configured performer cells do not show a dropdown indicator.",
    )


def mark_draft_performer(page: Page) -> str:
    row_key = page.evaluate(
        """async () => {
            const row = window.shiftHelperEventGrid.getRows('active')
                .find(candidate => candidate.getData()._draft);
            if (!row) throw new Error('No draft row is available.');
            await row.scrollTo('center', false);
            const cell = row.getCell('performer');
            cell.getElement().dataset.stage7Target = 'true';
            return row.getData()._rowKey;
        }"""
    )
    target = page.locator('[data-stage7-target="true"]')
    target.wait_for(state="visible", timeout=5_000)
    target.click()
    page.wait_for_timeout(100)
    return row_key


def target_value(page: Page, row_key: str) -> str:
    return page.evaluate(
        """rowKey => {
            const row = window.shiftHelperEventGrid.getRows('active')
                .find(candidate => candidate.getData()._rowKey === rowKey);
            return String(row.getCell('performer').getValue() ?? '');
        }""",
        row_key,
    )


def open_target_editor(page: Page) -> None:
    target = page.locator('[data-stage7-target="true"]')
    target.click()
    page.keyboard.press("F2")
    page.locator(".journal-stable-editor").wait_for(state="visible", timeout=5_000)
    page.locator("#stage7-list-popup").wait_for(state="visible", timeout=5_000)


def test_autocomplete_selection(page: Page) -> tuple[str, str]:
    row_key = mark_draft_performer(page)
    open_target_editor(page)
    editor = page.locator(".journal-stable-editor")
    editor.fill("Пе")
    page.wait_for_timeout(120)

    options = page.locator("#stage7-list-popup button")
    require(options.count() == 1, "Autocomplete did not reduce the list to one value.")
    require(options.first.inner_text() == "Петров П.П.", "Autocomplete returned the wrong value.")
    options.first.click()
    require(editor.input_value() == "Петров П.П.", "Popup selection did not fill the editor.")
    editor.press("Enter")
    page.wait_for_timeout(250)
    require(
        target_value(page, row_key) == "Петров П.П.",
        "Selected performer was not committed to the cell.",
    )
    return row_key, "Петров П.П."


def test_invalid_value_reverts(page: Page, row_key: str, expected: str) -> None:
    open_target_editor(page)
    editor = page.locator(".journal-stable-editor")
    editor.fill("Неизвестный сотрудник")
    editor.press("Enter")
    page.wait_for_timeout(300)

    require(
        target_value(page, row_key) == expected,
        "A value outside the strict list was not reverted.",
    )
    root = page.locator("#event-journal")
    require(
        root.get_attribute("data-list-validation-error") == "performer",
        "Strict-list validation did not report the performer field.",
    )
    require(
        page.locator('[data-stage7-target="true"].stage7-list-invalid').count() == 1,
        "The rejected cell was not visually marked.",
    )


def test_restore_and_alt_down(page: Page) -> None:
    page.reload(wait_until="networkidle")
    page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)
    wait_ready(page)

    config = page.evaluate(
        """() => window.shiftHelperAcceptanceStage7.configFor('performer')"""
    )
    require(config["enabled"] is True, "The performer list was not restored after reload.")
    require(config["allowCustom"] is False, "Strict validation was not restored after reload.")
    require(
        page.locator(
            '.tabulator-cell[tabulator-field="performer"].stage7-list-cell'
        ).count()
        >= 1,
        "Dropdown indicators were not restored after reload.",
    )

    mark_draft_performer(page)
    page.keyboard.press("Alt+ArrowDown")
    page.locator(".journal-stable-editor").wait_for(state="visible", timeout=5_000)
    popup = page.locator("#stage7-list-popup")
    popup.wait_for(state="visible", timeout=5_000)
    require(
        popup.locator("button").count() == 3,
        "Alt+Down did not open the full configured list.",
    )
    page.keyboard.press("Escape")
    popup.wait_for(state="hidden", timeout=5_000)


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
            configure_performer_list(page)
            row_key, expected = test_autocomplete_selection(page)
            test_invalid_value_reverts(page, row_key, expected)
            test_restore_and_alt_down(page)
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
        raise SystemExit("Usage: ui_smoke_acceptance_stage7.py <base-url> [screenshot-path]")
    screenshot = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-stage7-failure.png")
    run(sys.argv[1], screenshot)
    print("Shift-Helper acceptance stage 7 smoke passed.")


if __name__ == "__main__":
    main()
