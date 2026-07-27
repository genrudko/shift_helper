"""Viewport-focused entry point for the Shift-Helper browser smoke suite."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from playwright.sync_api import Page


BASE_SCRIPT = Path(__file__).with_name("ui_smoke.py")
SPEC = importlib.util.spec_from_file_location("shift_helper_ui_smoke_base", BASE_SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load the base UI smoke module.")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)


def test_excel_edit_modes(page: Page) -> None:
    row = BASE.saved_rows(page).first
    description = BASE.cell(row, "description")

    description.click()
    BASE.require(
        description.locator(".journal-stable-editor").count() == 0,
        "A single click unexpectedly entered edit mode.",
    )

    box = description.bounding_box()
    BASE.require(box is not None, "Description cell geometry is unavailable.")
    page.mouse.dblclick(
        box["x"] + 24,
        box["y"] + (box["height"] / 2),
        delay=90,
    )
    editor = description.locator(".journal-stable-editor")
    editor.wait_for(state="visible", timeout=5_000)
    first_caret = editor.evaluate("element => element.selectionStart")
    text_before = editor.input_value()
    BASE.require(
        first_caret < len(text_before),
        "Double click placed the caret only at the end.",
    )

    editor_box = editor.bounding_box()
    BASE.require(editor_box is not None, "Editor geometry is unavailable.")
    page.mouse.click(
        editor_box["x"] + (editor_box["width"] * 0.52),
        editor_box["y"] + (editor_box["height"] / 2),
    )
    BASE.require(editor.is_visible(), "A click inside the editor unexpectedly closed editing.")
    second_caret = editor.evaluate("element => element.selectionStart")
    BASE.require(second_caret != first_caret, "A click inside the editor did not move the caret.")
    BASE.require(second_caret < len(text_before), "The caret click test landed beyond the text.")

    page.keyboard.press("ArrowRight")
    third_caret = editor.evaluate("element => element.selectionStart")
    BASE.require(
        third_caret == min(second_caret + 1, len(text_before)),
        "ArrowRight did not move the caret by one character inside the editor.",
    )
    page.keyboard.insert_text("X")
    expected = f"{text_before[:third_caret]}X{text_before[third_caret:]}"
    page.keyboard.press("Enter")
    editor.wait_for(state="hidden", timeout=5_000)
    BASE.require(
        BASE.cell(row, "description").inner_text().strip() == expected,
        "The editor did not preserve the click and arrow caret position.",
    )

    reason = BASE.cell(row, "reason")
    reason.click()
    page.keyboard.press("F2")
    reason_editor = reason.locator(".journal-stable-editor")
    reason_editor.wait_for(state="visible", timeout=5_000)
    BASE.require(
        reason_editor.evaluate("element => element.selectionStart")
        == len(reason_editor.input_value()),
        "F2 did not place the caret at the end.",
    )
    page.keyboard.press("Escape")


BASE.test_excel_edit_modes = test_excel_edit_modes


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: ui_smoke_viewport.py <base-url> [screenshot-path]")
    screenshot_path = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-smoke-failure.png")
    BASE.run_smoke(sys.argv[1], screenshot_path)
    print("Shift-Helper UX-GRID-002 viewport smoke test passed.")


if __name__ == "__main__":
    main()
