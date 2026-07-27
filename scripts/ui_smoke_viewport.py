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


BASE["test_excel_edit_modes"] = test_excel_edit_modes
BASE["frozen_fields"] = frozen_fields
base_function("run_smoke").__globals__["test_excel_edit_modes"] = test_excel_edit_modes
base_function("test_viewport_and_frozen_columns").__globals__["frozen_fields"] = frozen_fields


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: ui_smoke_viewport.py <base-url> [screenshot-path]")
    screenshot_path = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-smoke-failure.png")
    base_function("run_smoke")(sys.argv[1], screenshot_path)
    print("Shift-Helper UX-GRID-002 viewport smoke test passed.")


if __name__ == "__main__":
    main()
