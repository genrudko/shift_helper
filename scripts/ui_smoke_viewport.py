"""Viewport-focused entry point for the Shift-Helper browser smoke suite."""

from __future__ import annotations  # noqa: I001

import json
import runpy
import sys
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


BASE_SCRIPT = Path(__file__).with_name("ui_smoke.py")
BASE = runpy.run_path(str(BASE_SCRIPT), run_name="shift_helper_ui_smoke_base")


def base_function(name: str):
    return BASE[name]


def test_excel_edit_modes(page: Page) -> None:
    saved_rows = base_function("saved_rows")
    cell = base_function("cell")
    require = base_function("require")

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
        box["x"] + 18,
        box["y"] + (box["height"] / 2),
        delay=90,
    )
    editor = description.locator(".journal-stable-editor")
    editor.wait_for(state="visible", timeout=5_000)
    first_caret = editor.evaluate("element => element.selectionStart")
    text_before = editor.input_value()
    require(
        first_caret < len(text_before),
        "Double click placed the caret only at the end.",
    )

    editor_box = editor.bounding_box()
    require(editor_box is not None, "Editor geometry is unavailable.")
    text_width = editor.evaluate(
        """element => {
            const style = getComputedStyle(element);
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
            return context.measureText(element.value).width;
        }"""
    )
    click_offset = max(12, min(editor_box["width"] - 6, text_width * 0.62))
    page.mouse.click(
        editor_box["x"] + click_offset,
        editor_box["y"] + (editor_box["height"] / 2),
    )
    page.wait_for_timeout(80)
    require(editor.is_visible(), "A click inside the editor unexpectedly closed editing.")
    second_caret = editor.evaluate("element => element.selectionStart")
    require(second_caret != first_caret, "A click inside the editor did not move the caret.")
    require(second_caret < len(text_before), "The caret click test landed beyond the text.")

    page.keyboard.press("ArrowRight")
    third_caret = editor.evaluate("element => element.selectionStart")
    require(
        third_caret == min(second_caret + 1, len(text_before)),
        "ArrowRight did not move the caret by one character inside the editor.",
    )
    page.keyboard.insert_text("X")
    expected = f"{text_before[:third_caret]}X{text_before[third_caret:]}"
    page.keyboard.press("Enter")
    editor.wait_for(state="hidden", timeout=5_000)
    require(
        cell(row, "description").inner_text().strip() == expected,
        "The editor did not preserve the click and arrow caret position.",
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


def frozen_fields(page: Page) -> list[str]:
    try:
        page.wait_for_function(
            """() => {
                const root = document.getElementById('event-journal');
                const select = document.getElementById('journal-frozen-through');
                return root?.dataset.frozenColumnsController === 'ready'
                    && root.dataset.frozenColumnsApplied === select?.value;
            }""",
            timeout=10_000,
        )
    except PlaywrightTimeoutError as exc:
        diagnostic = page.evaluate(
            """() => {
                const root = document.getElementById('event-journal');
                const select = document.getElementById('journal-frozen-through');
                const table = window.shiftHelperEventGrid;
                return {
                    dataset: root ? {...root.dataset} : null,
                    selected: select?.value ?? null,
                    updateColumnDefinition: typeof table?.updateColumnDefinition,
                    columns: table?.getColumns?.().map(column => ({
                        field: column.getField(),
                        frozen: column.getDefinition().frozen ?? null,
                    })) ?? null,
                };
            }"""
        )
        raise AssertionError(
            "Frozen-column controller did not settle: "
            + json.dumps(diagnostic, ensure_ascii=False, sort_keys=True)
        ) from exc

    return page.evaluate(
        """() => window.shiftHelperEventGrid.getColumns()
            .filter(column => Boolean(column.getDefinition().frozen))
            .map(column => column.getField())
            .filter(Boolean)"""
    )


def clear_grid_selection(page: Page) -> None:
    page.evaluate(
        """() => {
            for (const range of window.shiftHelperEventGrid.getRanges?.() || []) {
                try {
                    range.remove();
                } catch (_error) {
                    // Ignore an already stale range during a visual assertion.
                }
            }
            document.querySelectorAll('.journal-row--multi-selected').forEach(element => {
                element.classList.remove('journal-row--multi-selected');
            });
            document.querySelectorAll('.tabulator-range-selected').forEach(element => {
                element.classList.remove('tabulator-range-selected');
            });
        }"""
    )
    page.locator("#journal-title").click()
    page.wait_for_timeout(120)


def test_viewport_and_frozen_columns(page: Page) -> None:
    require = base_function("require")
    saved_rows = base_function("saved_rows")
    cell = base_function("cell")

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

    clear_grid_selection(page)
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


BASE["test_excel_edit_modes"] = test_excel_edit_modes
BASE["frozen_fields"] = frozen_fields
BASE["test_viewport_and_frozen_columns"] = test_viewport_and_frozen_columns
base_function("run_smoke").__globals__["test_excel_edit_modes"] = test_excel_edit_modes
base_function("run_smoke").__globals__["test_viewport_and_frozen_columns"] = (
    test_viewport_and_frozen_columns
)


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: ui_smoke_viewport.py <base-url> [screenshot-path]")
    screenshot_path = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-smoke-failure.png")
    base_function("run_smoke")(sys.argv[1], screenshot_path)
    print("Shift-Helper UX-GRID-002 viewport smoke test passed.")


if __name__ == "__main__":
    main()
