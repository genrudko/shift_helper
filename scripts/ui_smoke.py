"""Operator-facing browser smoke test for the Shift-Helper event grid."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Dialog, Locator, Page, sync_playwright


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def draft_row(page: Page, index: int = 0) -> Locator:
    return page.locator(".journal-row--draft").nth(index)


def cell(row: Locator, field: str) -> Locator:
    return row.locator(f'.tabulator-cell[tabulator-field="{field}"]')


def begin_typing(page: Page, target: Locator, seed: str = "1") -> Locator:
    target.click()
    page.keyboard.type(seed)
    editor = target.locator("input.journal-stable-editor, textarea.journal-stable-editor")
    editor.wait_for(state="visible", timeout=5_000)
    return editor


def assert_editor_inside_cell(target: Locator, editor: Locator) -> None:
    target_box = target.bounding_box()
    editor_box = editor.bounding_box()
    require(target_box is not None and editor_box is not None, "Editor geometry is unavailable.")
    tolerance = 5
    center_x = editor_box["x"] + (editor_box["width"] / 2)
    center_y = editor_box["y"] + (editor_box["height"] / 2)
    require(
        target_box["x"] - tolerance
        <= center_x
        <= target_box["x"] + target_box["width"] + tolerance,
        "Editor horizontal center escaped its cell.",
    )
    require(
        target_box["y"] - tolerance
        <= center_y
        <= target_box["y"] + target_box["height"] + tolerance,
        "Editor vertical center escaped its cell.",
    )
    require(
        editor_box["width"] <= target_box["width"] + (tolerance * 2),
        "Editor became wider than its cell.",
    )


def finish_with_enter(page: Page, target: Locator, editor: Locator) -> None:
    page.keyboard.press("Enter")
    editor.wait_for(state="hidden", timeout=5_000)
    require(
        target.locator(".journal-stable-editor").count() == 0,
        "Enter did not close the editor.",
    )
    require(
        "tabulator-editing" not in (target.get_attribute("class") or ""),
        "Cell remained in editing mode after Enter.",
    )


def edit_cell(page: Page, target: Locator, value: str) -> None:
    editor = begin_typing(page, target)
    editor.fill(value)
    assert_editor_inside_cell(target, editor)
    finish_with_enter(page, target, editor)


def assert_blank_draft_dates(page: Page, count: int = 5) -> None:
    rows = page.locator(".journal-row--draft")
    require(rows.count() >= count, "Draft row reserve is missing.")
    for index in range(count):
        row = rows.nth(index)
        require(
            not cell(row, "start_date").inner_text().strip()
            and not cell(row, "start_time").inner_text().strip(),
            f"Draft row {index + 1} received an unsolicited timestamp.",
        )


def assert_context_menus(page: Page, saved_row: Locator) -> None:
    cell(saved_row, "description").click(button="right")
    menu = page.locator(".tabulator-menu").last
    menu.wait_for(state="visible", timeout=5_000)
    require(menu.get_by_text("Копировать", exact=True).count() == 1, "No cell copy command.")
    require(menu.get_by_text("Вставить", exact=True).count() == 1, "No cell paste command.")
    page.keyboard.press("Escape")

    saved_row.locator(".journal-row-number").click(button="right")
    row_menu = page.locator(".journal-row-menu")
    row_menu.wait_for(state="visible", timeout=5_000)
    for label in (
        "Копировать строку",
        "Вырезать строку",
        "Вставить строку",
        "Удалить строку",
    ):
        require(row_menu.get_by_text(label, exact=True).count() == 1, f"No row command: {label}")
    page.keyboard.press("Escape")
    page.locator("#journal-title").click()


def copy_cell(page: Page, saved_row: Locator) -> None:
    source = cell(saved_row, "reason")
    target = cell(saved_row, "actions")
    source.click()
    page.keyboard.press("Control+C")
    target.click()
    page.keyboard.press("Control+V")
    page.wait_for_timeout(500)
    require(
        "Повышенная вибрация" in target.inner_text(),
        "Ctrl+C/Ctrl+V did not copy one cell.",
    )


def whole_row_range_selected(page: Page) -> bool:
    return bool(
        page.evaluate(
            """() => {
                const fields = [
                    "start_date", "start_time", "asset_label", "description",
                    "reason", "actions", "performer", "end_date", "end_time", "author",
                ];
                const range = window.shiftHelperEventGrid?.getRanges?.().at(-1);
                const raw = range?.getCells?.() || [];
                const matrix = raw.length && Array.isArray(raw[0]) ? raw : [raw];
                if (matrix.length !== 1 || matrix[0].length < fields.length) {
                    return false;
                }
                const cells = matrix[0];
                const row = cells[0]?.getRow?.();
                if (!row || cells.some(cell => cell.getRow?.() !== row)) {
                    return false;
                }
                const selected = new Set(cells.map(cell => cell.getField?.()));
                return fields.every(field => selected.has(field));
            }"""
        )
    )


def assert_row_selected(page: Page, row: Locator, message: str) -> None:
    has_visual_class = "journal-row--selected" in (row.get_attribute("class") or "")
    require(has_visual_class or whole_row_range_selected(page), message)


def copy_row(page: Page, saved_row: Locator) -> Locator:
    saved_row.locator(".journal-row-number").click()
    assert_row_selected(page, saved_row, "Row number did not select the complete journal row.")
    page.keyboard.press("Control+C")

    target = draft_row(page)
    target.locator(".journal-row-number").click()
    assert_row_selected(page, target, "Target row was not selected by its row number.")
    page.keyboard.press("Control+V")

    page.locator('#journal-save-state[data-state="saved"]').wait_for(
        state="visible",
        timeout=15_000,
    )
    page.wait_for_timeout(700)
    require(
        page.locator(".tabulator-row:not(.journal-row--draft)").count() >= 2,
        "Copied row was not persisted.",
    )
    copied = page.locator(".tabulator-row:not(.journal-row--draft)").nth(1)
    require("11" in cell(copied, "asset_label").inner_text(), "Row paste lost WTG number.")
    require(
        "Проверка spreadsheet-интерфейса" in cell(copied, "description").inner_text(),
        "Row paste lost description.",
    )
    return copied


def select_range(page: Page, first: Locator, last: Locator) -> None:
    first_box = first.bounding_box()
    last_box = last.bounding_box()
    require(first_box is not None and last_box is not None, "Range cell geometry is unavailable.")
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


def paste_across_selected_range(page: Page) -> None:
    first_row = draft_row(page, 0)
    second_row = draft_row(page, 1)
    select_range(page, cell(first_row, "reason"), cell(second_row, "actions"))
    page.evaluate("navigator.clipboard.writeText('Диапазон')")
    page.keyboard.press("Control+V")
    page.wait_for_timeout(600)
    for row in (first_row, second_row):
        for field in ("reason", "actions"):
            require(
                "Диапазон" in cell(row, field).inner_text(),
                "Paste did not repeat the copied value over the selected range.",
            )


def use_fill_handle(page: Page, saved_row: Locator) -> None:
    source = cell(saved_row, "reason")
    source.click()
    handle = page.locator(".journal-fill-handle")
    handle.wait_for(state="visible", timeout=5_000)
    target = cell(draft_row(page, 2), "reason")
    handle_box = handle.bounding_box()
    target_box = target.bounding_box()
    require(handle_box is not None and target_box is not None, "Fill handle geometry is unavailable.")
    page.mouse.move(
        handle_box["x"] + (handle_box["width"] / 2),
        handle_box["y"] + (handle_box["height"] / 2),
    )
    page.mouse.down()
    page.mouse.move(
        target_box["x"] + (target_box["width"] / 2),
        target_box["y"] + (target_box["height"] / 2),
        steps=10,
    )
    page.mouse.up()
    page.wait_for_timeout(600)
    require(
        "Повышенная вибрация" in target.inner_text(),
        "Fill handle did not extend the selected value downward.",
    )


def accept_dialog(dialog: Dialog) -> None:
    dialog.accept()


def delete_and_cut_rows(page: Page, original: Locator) -> None:
    page.on("dialog", accept_dialog)

    copied = copy_row(page, original)
    copied.locator(".journal-row-number").click(button="right")
    menu = page.locator(".journal-row-menu")
    menu.get_by_text("Удалить строку", exact=True).click()
    page.wait_for_timeout(800)
    require(
        page.locator(".tabulator-row:not(.journal-row--draft)").count() == 1,
        "Row delete did not remove the persisted row.",
    )

    copied = copy_row(page, original)
    copied.locator(".journal-row-number").click()
    assert_row_selected(page, copied, "Copied row was not selected before Ctrl+X.")
    page.keyboard.press("Control+X")
    page.wait_for_timeout(800)
    require(
        page.locator(".tabulator-row:not(.journal-row--draft)").count() == 1,
        "Ctrl+X did not cut the persisted row.",
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
            assert_blank_draft_dates(page)

            row = draft_row(page)
            edit_cell(page, cell(row, "start_date"), "26.07.2026")
            edit_cell(page, cell(row, "start_time"), "18:10")

            equipment = cell(row, "asset_label")
            equipment_editor = begin_typing(page, equipment, seed="1")
            equipment_editor.fill("11")
            assert_editor_inside_cell(equipment, equipment_editor)
            finish_with_enter(page, equipment, equipment_editor)
            require("11" in equipment.inner_text(), "WTG number was not accepted.")

            description = cell(row, "description")
            editor = begin_typing(page, description)
            editor.fill("Проверка spreadsheet-интерфейса")
            assert_editor_inside_cell(description, editor)
            page.keyboard.press("Shift+Enter")
            page.keyboard.insert_text("Вторая строка")
            require("\n" in editor.input_value(), "Shift+Enter did not insert a line break.")
            finish_with_enter(page, description, editor)

            edit_cell(page, cell(row, "reason"), "Повышенная вибрация")

            page.locator('#journal-save-state[data-state="saved"]').wait_for(
                state="visible",
                timeout=15_000,
            )
            page.wait_for_timeout(700)
            assert_blank_draft_dates(page)

            saved_row = page.locator(".tabulator-row:not(.journal-row--draft)").first
            saved_box = saved_row.bounding_box()
            require(
                saved_box is not None and saved_box["height"] > 40,
                "Multiline content did not increase row height.",
            )

            edit_cell(page, cell(saved_row, "end_date"), "26.07.2026")
            edit_cell(page, cell(saved_row, "end_time"), "20:40")
            page.locator('#journal-save-state[data-state="saved"]').wait_for(
                state="visible",
                timeout=15_000,
            )
            page.wait_for_timeout(500)
            losses = page.evaluate(
                """() => window.shiftHelperEventGrid
                    .getData().find(rowData => !rowData._draft).downtime_losses_rub"""
            )
            require(losses == "6250", "Downtime losses were not calculated.")

            assert_context_menus(page, saved_row)
            copy_cell(page, saved_row)
            paste_across_selected_range(page)
            use_fill_handle(page, saved_row)
            delete_and_cut_rows(page, saved_row)

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
    print("Shift-Helper operator grid smoke test passed.")


if __name__ == "__main__":
    main()
