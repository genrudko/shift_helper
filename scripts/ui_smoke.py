"""Browser smoke test for the Shift-Helper event spreadsheet."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def draft_cell(page: Page, field: str, row_index: int = 0) -> Locator:
    return page.locator(".journal-row--draft").nth(row_index).locator(
        f'.tabulator-cell[tabulator-field="{field}"]'
    )


def begin_typing(page: Page, cell: Locator, seed: str = "1") -> Locator:
    cell.click()
    page.keyboard.type(seed)
    editor = cell.locator("input.journal-stable-editor, textarea.journal-stable-editor")
    editor.wait_for(state="visible", timeout=5_000)
    return editor


def assert_editor_inside_cell(cell: Locator, editor: Locator) -> None:
    cell_box = cell.bounding_box()
    editor_box = editor.bounding_box()
    require(cell_box is not None and editor_box is not None, "Editor geometry is unavailable.")
    tolerance = 2
    require(
        editor_box["x"] >= cell_box["x"] - tolerance,
        "The editor moved to the left of its cell.",
    )
    require(
        editor_box["y"] >= cell_box["y"] - tolerance,
        "The editor moved above its cell.",
    )
    require(
        editor_box["x"] + editor_box["width"] <= cell_box["x"] + cell_box["width"] + tolerance,
        "The editor moved to the right of its cell.",
    )
    require(
        editor_box["y"] + editor_box["height"] <= cell_box["y"] + cell_box["height"] + tolerance,
        "The editor moved below its cell.",
    )


def direct_edit(page: Page, cell: Locator, value: str) -> None:
    editor = begin_typing(page, cell)
    editor.fill(value)
    assert_editor_inside_cell(cell, editor)
    background = editor.evaluate("element => getComputedStyle(element).backgroundColor")
    require(
        background not in {"rgb(247, 251, 255)", "rgb(255, 255, 255)"},
        "The editor still uses detached white styling.",
    )
    page.keyboard.press("Enter")
    editor.wait_for(state="hidden", timeout=5_000)
    require(
        cell.locator(".journal-stable-editor").count() == 0,
        "Enter did not finish cell editing.",
    )
    require(
        "tabulator-editing" not in (cell.get_attribute("class") or ""),
        "The cell remained in editing state after Enter.",
    )


def assert_blank_draft_dates(page: Page, count: int = 5) -> None:
    rows = page.locator(".journal-row--draft")
    require(rows.count() >= count, "The spreadsheet lost its draft-row reserve.")
    for index in range(count):
        row = rows.nth(index)
        date_text = row.locator(
            '.tabulator-cell[tabulator-field="start_date"]'
        ).inner_text().strip()
        time_text = row.locator(
            '.tabulator-cell[tabulator-field="start_time"]'
        ).inner_text().strip()
        require(
            not date_text and not time_text,
            f"Draft row {index + 1} was unexpectedly seeded with date/time.",
        )


def assert_cell_context_menu(page: Page, cell: Locator) -> None:
    cell.click(button="right")
    menu = page.locator(".tabulator-menu").last
    menu.wait_for(state="visible", timeout=5_000)
    require(
        menu.get_by_text("Копировать", exact=True).count() == 1,
        "Cell context menu has no copy command.",
    )
    require(
        menu.get_by_text("Вставить", exact=True).count() == 1,
        "Cell context menu has no paste command.",
    )
    page.keyboard.press("Escape")


def assert_row_context_menu(page: Page, row: Locator) -> None:
    row.locator(".journal-row-number").click(button="right")
    menu = page.locator(".tabulator-menu").last
    menu.wait_for(state="visible", timeout=5_000)
    require(
        menu.get_by_text("Копировать строку", exact=True).count() == 1,
        "Row context menu has no row-copy command.",
    )
    require(
        menu.get_by_text("Вставить строку", exact=True).count() == 1,
        "Row context menu has no row-paste command.",
    )
    page.keyboard.press("Escape")


def assert_cell_copy_paste(page: Page, row: Locator) -> None:
    source = row.locator('.tabulator-cell[tabulator-field="reason"]')
    target = row.locator('.tabulator-cell[tabulator-field="actions"]')
    source.click()
    page.keyboard.press("Control+C")
    target.click()
    page.keyboard.press("Control+V")
    page.wait_for_timeout(500)
    require(
        "Повышенная вибрация" in target.inner_text(),
        "Cell copy/paste did not transfer the selected value.",
    )


def assert_row_range_selected(row: Locator) -> None:
    selected = row.locator(".tabulator-cell.tabulator-range-selected").count()
    require(selected >= 8, "Clicking the row number did not select the complete journal row.")


def copy_and_paste_row(page: Page, source_row: Locator) -> None:
    source_row.locator(".journal-row-number").click()
    assert_row_range_selected(source_row)
    page.keyboard.press("Control+C")
    page.wait_for_timeout(200)

    target_row = page.locator(".journal-row--draft").first
    target_row.locator(".journal-row-number").click()
    assert_row_range_selected(target_row)
    page.keyboard.press("Control+V")

    page.locator('#journal-save-state[data-state="saved"]').wait_for(
        state="visible",
        timeout=15_000,
    )
    page.wait_for_timeout(700)
    require(
        page.locator(".tabulator-row:not(.journal-row--draft)").count() >= 2,
        "The copied row was not pasted and persisted into the target row.",
    )
    copied = page.locator(".tabulator-row:not(.journal-row--draft)").nth(1)
    require(
        "ВЭУ №11" in copied.locator(
            '.tabulator-cell[tabulator-field="asset_label"]'
        ).inner_text(),
        "Row paste lost the equipment value.",
    )
    require(
        "Проверка spreadsheet-интерфейса" in copied.locator(
            '.tabulator-cell[tabulator-field="description"]'
        ).inner_text(),
        "Row paste lost the description value.",
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

            headers = page.locator(".tabulator-col-title").all_inner_texts()
            for expected in (
                "Дата останова",
                "№ ВЭУ / оборудование",
                "Описание события",
                "Действия персонала",
                "Кто внёс запись",
                "Потери от простоя, руб.",
            ):
                require(expected in headers, f"Missing spreadsheet column: {expected}")

            require(
                page.locator(".tabulator-col-resize-handle").count() >= 8,
                "Resizable column handles are absent.",
            )
            require(
                page.locator(".tabulator-header-filter input").count() >= 8,
                "Column header filters are absent.",
            )
            assert_blank_draft_dates(page)

            direct_edit(page, draft_cell(page, "start_date"), "26.07.2026")
            direct_edit(page, draft_cell(page, "start_time"), "18:10")

            equipment = draft_cell(page, "asset_label")
            equipment_editor = begin_typing(page, equipment, seed="В")
            equipment_editor.fill("ВЭУ №11")
            assert_editor_inside_cell(equipment, equipment_editor)
            page.keyboard.press("Enter")
            equipment_editor.wait_for(state="hidden", timeout=5_000)
            require(
                "ВЭУ №11" in equipment.inner_text(),
                "The WTG/equipment number was not accepted after Enter.",
            )

            description = draft_cell(page, "description")
            editor = begin_typing(page, description)
            editor.fill("Проверка spreadsheet-интерфейса")
            assert_editor_inside_cell(description, editor)
            page.keyboard.press("Shift+Enter")
            page.keyboard.insert_text("Вторая строка")
            require(
                "\n" in editor.input_value(),
                "Shift+Enter did not insert a line break in a multiline cell.",
            )
            page.keyboard.press("Enter")
            editor.wait_for(state="hidden", timeout=5_000)
            require(
                description.locator(".journal-stable-editor").count() == 0,
                "Enter did not close the multiline editor.",
            )

            direct_edit(page, draft_cell(page, "reason"), "Повышенная вибрация")

            page.locator('#journal-save-state[data-state="saved"]').wait_for(
                state="visible",
                timeout=15_000,
            )
            page.wait_for_timeout(500)
            assert_blank_draft_dates(page)

            saved_row = page.locator(".tabulator-row:not(.journal-row--draft)").first
            direct_edit(
                page,
                saved_row.locator('.tabulator-cell[tabulator-field="end_date"]'),
                "26.07.2026",
            )
            direct_edit(
                page,
                saved_row.locator('.tabulator-cell[tabulator-field="end_time"]'),
                "20:40",
            )
            page.locator('#journal-save-state[data-state="saved"]').wait_for(
                state="visible",
                timeout=15_000,
            )
            page.wait_for_timeout(500)
            calculated_losses = page.evaluate(
                """() => window.shiftHelperEventGrid
                    .getData()
                    .find(row => !row._draft)
                    .downtime_losses_rub"""
            )
            require(
                calculated_losses == "6250",
                "Downtime losses were not calculated with the source workbook formula.",
            )

            description_cell = saved_row.locator(
                '.tabulator-cell[tabulator-field="description"]'
            )
            assert_cell_context_menu(page, description_cell)
            assert_row_context_menu(page, saved_row)
            assert_cell_copy_paste(page, saved_row)
            copy_and_paste_row(page, saved_row)

            description_cell.click()
            page.locator("#cell-fill-color").evaluate(
                "element => {"
                " element.value = '#fff2cc';"
                " element.dispatchEvent(new Event('input'));"
                " }"
            )
            page.locator("#apply-cell-fill").click()
            require(
                "rgb(255, 242, 204)" in description_cell.get_attribute("style"),
                "Manual cell fill was not applied.",
            )

            page.reload(wait_until="networkidle")
            page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)
            require(
                page.get_by_text("Проверка spreadsheet-интерфейса", exact=False).count() >= 2,
                "The original and copied rows were not persisted.",
            )

            search = page.locator("#journal-search")
            search.fill("spreadsheet-интерфейса")
            page.wait_for_timeout(250)
            require(
                page.locator(".tabulator-row:not(.journal-row--draft)").count() >= 2,
                "Global journal search did not retain the copied matching records.",
            )
            search.fill("несуществующее-значение")
            page.wait_for_timeout(250)
            require(
                page.locator(".tabulator-row:not(.journal-row--draft)").count() == 0,
                "Global journal search did not hide nonmatching records.",
            )

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
    print("Shift-Helper spreadsheet UI smoke test passed.")


if __name__ == "__main__":
    main()
