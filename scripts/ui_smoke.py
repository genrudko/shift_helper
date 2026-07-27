"""Operator-facing browser smoke test for the Shift-Helper event grid."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def cell(row: Locator, field: str) -> Locator:
    return row.locator(f'.tabulator-cell[tabulator-field="{field}"]')


def saved_rows(page: Page) -> Locator:
    return page.locator(".tabulator-row:not(.journal-row--draft)")


def create_event(page: Page, base_url: str, index: int) -> None:
    response = page.request.post(
        f"{base_url.rstrip('/')}/events/rows",
        data={
            "start_date": "26.07.2026",
            "start_time": f"{18 + index:02d}:10",
            "asset_label": f"ВЭУ №{10 + index}",
            "description": "ABCDEFGH" if index == 0 else f"Тестовая запись {index + 1}",
            "reason": f"Причина {index + 1}",
            "actions": f"Действия {index + 1}",
            "performer": "Иванов И.И.",
            "end_date": "",
            "end_time": "",
            "author": "Петров П.П.",
            "revision": 0,
        },
    )
    require(response.ok, f"Unable to seed event {index + 1}: {response.text()}")


def select_range(page: Page, first: Locator, last: Locator) -> None:
    first_box = first.bounding_box()
    last_box = last.bounding_box()
    require(first_box is not None and last_box is not None, "Range geometry is unavailable.")
    page.mouse.move(
        first_box["x"] + (first_box["width"] / 2),
        first_box["y"] + (first_box["height"] / 2),
    )
    page.mouse.down()
    page.mouse.move(
        last_box["x"] + (last_box["width"] / 2),
        last_box["y"] + (last_box["height"] / 2),
        steps=8,
    )
    page.mouse.up()


def wait_saved(page: Page) -> None:
    page.locator('#journal-save-state[data-state="saved"]').wait_for(
        state="visible",
        timeout=15_000,
    )
    page.wait_for_timeout(450)


def test_excel_edit_modes(page: Page) -> None:
    row = saved_rows(page).first
    description = cell(row, "description")

    description.click()
    require(
        description.locator(".journal-stable-editor").count() == 0,
        "A single click unexpectedly entered edit mode.",
    )

    box = description.bounding_box()
    require(box is not None, "Description cell geometry is unavailable.")
    page.mouse.dblclick(
        box["x"] + 24,
        box["y"] + (box["height"] / 2),
        delay=90,
    )
    editor = description.locator(".journal-stable-editor")
    editor.wait_for(state="visible", timeout=5_000)
    first_caret = editor.evaluate("element => element.selectionStart")
    require(
        first_caret < len(editor.input_value()),
        "Double click placed the caret only at the end.",
    )

    editor_box = editor.bounding_box()
    require(editor_box is not None, "Editor geometry is unavailable.")
    page.mouse.click(
        editor_box["x"] + (editor_box["width"] * 0.78),
        editor_box["y"] + (editor_box["height"] / 2),
    )
    require(editor.is_visible(), "A click inside the editor unexpectedly closed editing.")
    second_caret = editor.evaluate("element => element.selectionStart")
    require(second_caret != first_caret, "A click inside the editor did not move the caret.")

    page.keyboard.press("ArrowRight")
    page.keyboard.insert_text("X")
    page.keyboard.press("Enter")
    editor.wait_for(state="hidden", timeout=5_000)
    require(
        cell(row, "description").inner_text().strip() != "ABCDEFGHX",
        "Arrow keys did not move the caret inside the editor.",
    )

    reason = cell(row, "reason")
    reason.click()
    page.keyboard.press("F2")
    reason_editor = reason.locator(".journal-stable-editor")
    reason_editor.wait_for(state="visible", timeout=5_000)
    require(
        reason_editor.evaluate("element => element.selectionStart")
        == len(reason_editor.input_value()),
        "F2 did not place the caret at the end.",
    )
    page.keyboard.press("Escape")


def test_row_drag_selection(page: Page) -> None:
    first_number = saved_rows(page).nth(0).locator(".journal-row-number")
    third_number = saved_rows(page).nth(2).locator(".journal-row-number")
    first_box = first_number.bounding_box()
    third_box = third_number.bounding_box()
    require(first_box is not None and third_box is not None, "Row-number geometry is unavailable.")

    page.mouse.move(
        first_box["x"] + (first_box["width"] / 2),
        first_box["y"] + (first_box["height"] / 2),
    )
    page.mouse.down()
    page.mouse.move(
        third_box["x"] + (third_box["width"] / 2),
        third_box["y"] + (third_box["height"] / 2),
        steps=12,
    )
    page.mouse.up()
    require(
        page.locator(".journal-row--multi-selected").count() >= 3,
        "Dragging over row numbers did not select a continuous row range.",
    )
    cell(saved_rows(page).first, "description").click()


def test_range_delete_and_history(page: Page) -> None:
    rows = saved_rows(page)
    first = rows.nth(0)
    second = rows.nth(1)
    select_range(page, cell(first, "reason"), cell(second, "actions"))
    page.keyboard.press("Delete")
    page.wait_for_timeout(450)

    for row in (first, second):
        for field in ("reason", "actions"):
            require(not cell(row, field).inner_text().strip(), "Delete did not clear the range.")

    require(not page.locator("#journal-undo").is_disabled(), "Undo remained disabled.")
    page.keyboard.press("Control+Z")
    page.wait_for_timeout(500)
    require("Причина 1" in cell(first, "reason").inner_text(), "Undo did not restore cells.")
    require("Действия 2" in cell(second, "actions").inner_text(), "Undo lost range data.")

    page.keyboard.press("Control+Y")
    page.wait_for_timeout(500)
    require(not cell(first, "reason").inner_text().strip(), "Redo did not clear cells again.")

    page.keyboard.press("Control+Z")
    wait_saved(page)


def test_multi_row_delete_without_dialog(page: Page) -> None:
    dialog_messages: list[str] = []
    page.on("dialog", lambda dialog: (dialog_messages.append(dialog.message), dialog.dismiss()))

    before = saved_rows(page).count()
    first = saved_rows(page).nth(0)
    second = saved_rows(page).nth(1)
    first.locator(".journal-row-number").click()
    second.locator(".journal-row-number").click(modifiers=["Shift"])
    require(
        page.locator(".journal-row--multi-selected").count() == 2,
        "Shift-click did not select two rows.",
    )

    page.keyboard.press("Delete")
    page.wait_for_timeout(900)
    require(not dialog_messages, "Deletion still opened a confirmation dialog.")
    require(saved_rows(page).count() == before - 2, "Multiple rows were not deleted.")

    page.keyboard.press("Control+Z")
    page.wait_for_timeout(1_000)
    require(saved_rows(page).count() == before, "Undo did not restore deleted rows.")

    page.keyboard.press("Control+Y")
    page.wait_for_timeout(900)
    require(saved_rows(page).count() == before - 2, "Redo did not delete rows again.")

    page.keyboard.press("Control+Z")
    page.wait_for_timeout(1_000)
    require(saved_rows(page).count() == before, "Final undo did not restore rows.")


def frozen_fields(page: Page) -> list[str]:
    return page.evaluate(
        """() => window.shiftHelperEventGrid.getColumnLayout()
            .filter(column => column.frozen)
            .map(column => column.field)"""
    )


def test_viewport_and_frozen_columns(page: Page) -> None:
    page.locator("#open-view-settings").click()
    dialog = page.locator("#journal-view-settings")
    dialog.wait_for(state="visible", timeout=5_000)

    page.locator("#journal-theme").select_option("dark")
    page.locator("#journal-zoom").fill("140")
    page.locator("#journal-font-size").fill("15")
    page.locator("#journal-font-family").select_option("Tahoma")
    page.locator("#journal-frozen-through").select_option("none")
    page.wait_for_timeout(700)

    require(
        page.locator("body").evaluate("element => element.style.zoom") == "",
        "CSS zoom is still being applied to the page.",
    )
    require(
        page.locator("html").evaluate(
            "element => getComputedStyle(element).getPropertyValue('--ui-scale-factor').trim()"
        ) == "1.4",
        "Dimension-based interface scale was not applied.",
    )
    require(not frozen_fields(page), "Frozen columns were not fully disabled.")

    dialog.locator('button[value="close"]').last.click()
    dialog.wait_for(state="hidden", timeout=5_000)
    page.set_viewport_size({"width": 1180, "height": 760})
    page.wait_for_timeout(600)
    toolbar_fits = page.locator(".journal-toolbar").evaluate(
        "element => element.scrollWidth <= element.clientWidth + 2"
    )
    require(toolbar_fits, "The toolbar overflows the window after scaling.")

    first = saved_rows(page).first
    start_cell = cell(first, "start_date")
    description = cell(first, "description")
    start_background = start_cell.evaluate("element => getComputedStyle(element).backgroundColor")
    description_background = description.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    require(
        start_background == description_background,
        "Dark theme uses different row palettes in frozen and scrollable sections.",
    )

    description.click()
    handle = page.locator(".journal-fill-handle:not([hidden])")
    handle.wait_for(state="visible", timeout=5_000)
    page.wait_for_timeout(250)
    cell_box = description.bounding_box()
    handle_box = handle.bounding_box()
    require(cell_box is not None and handle_box is not None, "Fill-handle geometry is unavailable.")
    handle_center_x = handle_box["x"] + (handle_box["width"] / 2)
    handle_center_y = handle_box["y"] + (handle_box["height"] / 2)
    require(
        abs(handle_center_x - (cell_box["x"] + cell_box["width"])) <= 5,
        "Fill handle moved away from the selected cell after scaling.",
    )
    require(
        abs(handle_center_y - (cell_box["y"] + cell_box["height"])) <= 5,
        "Fill handle vertical position broke after scaling.",
    )

    page.locator("#open-view-settings").click()
    dialog.wait_for(state="visible", timeout=5_000)
    page.locator("#journal-frozen-through").select_option("asset_label")
    page.wait_for_timeout(700)
    require(
        frozen_fields(page) == ["start_date", "start_time", "asset_label"],
        "The configurable frozen-column boundary was not applied.",
    )

    page.locator("#journal-theme").select_option("light")
    page.locator("#journal-zoom").fill("110")
    page.wait_for_timeout(350)
    preferences = page.evaluate(
        "JSON.parse(localStorage.getItem('shift-helper-ui-preferences-v1'))"
    )
    require(preferences["zoom"] == 110, "Interface scale was not saved.")
    require(preferences["fontSize"] == 15, "Font size was not saved.")
    require(preferences["fontFamily"] == "Tahoma", "Font family was not saved.")
    require(
        preferences["frozenThrough"] == "asset_label",
        "Frozen-column preference was not saved.",
    )

    dialog.locator('button[value="close"]').last.click()
    dialog.wait_for(state="hidden", timeout=5_000)
    page.set_viewport_size({"width": 1680, "height": 960})
    page.reload(wait_until="networkidle")
    page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)
    require(page.locator("html").get_attribute("data-theme") == "light", "Theme was not persisted.")
    require(
        page.locator("body").evaluate("element => element.style.zoom") == "",
        "CSS zoom returned after page reload.",
    )
    require(
        frozen_fields(page) == ["start_date", "start_time", "asset_label"],
        "Frozen-column preference was not restored after reload.",
    )


def run_smoke(url: str, screenshot_path: Path) -> None:
    browser_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1680, "height": 960},
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
            for index in range(4):
                create_event(page, url, index)

            page.goto(f"{url.rstrip('/')}/events", wait_until="networkidle")
            page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)
            require(saved_rows(page).count() == 4, "Seeded rows are missing.")
            require(page.locator("#journal-undo").is_disabled(), "Undo should start disabled.")
            require(page.locator("#journal-redo").is_disabled(), "Redo should start disabled.")

            test_excel_edit_modes(page)
            wait_saved(page)
            test_row_drag_selection(page)
            test_range_delete_and_history(page)
            test_multi_row_delete_without_dialog(page)
            test_viewport_and_frozen_columns(page)

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
    print("Shift-Helper UX-GRID-002 viewport smoke test passed.")


if __name__ == "__main__":
    main()
