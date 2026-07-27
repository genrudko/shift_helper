"""Final browser-smoke entry point with virtualization-safe row checks."""

from __future__ import annotations

import runpy
from pathlib import Path

from playwright.sync_api import Page


RIBBON_SCRIPT = Path(__file__).with_name("ui_smoke_ribbon.py")
RIBBON = runpy.run_path(
    str(RIBBON_SCRIPT),
    run_name="shift_helper_ui_smoke_ribbon_base",
)
BASE_FUNCTION = RIBBON["BASE_FUNCTION"]


def reset_table_viewport(page: Page) -> None:
    holder = page.locator(".tabulator-tableholder")
    holder.evaluate("element => { element.scrollTop = 0; }")
    page.wait_for_timeout(300)


def test_row_drag_selection(page: Page) -> None:
    """Verify continuous row selection without clicking a virtualized stale row."""

    require = BASE_FUNCTION("require")
    saved_rows = BASE_FUNCTION("saved_rows")
    cell = BASE_FUNCTION("cell")

    reset_table_viewport(page)
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

    # Tabulator virtualizes rows. After a drag, the first selected row may be just
    # outside the viewport even though its old component is still addressable.
    visible_target = saved_rows(page).nth(2)
    cell(visible_target, "description").click()
    require(
        page.locator(".journal-row--multi-selected").count() == 0,
        "Clicking a visible cell did not leave row-selection mode.",
    )

    reset_table_viewport(page)
    require(
        cell(saved_rows(page).first, "description").is_visible(),
        "The first saved row did not return after resetting the viewport.",
    )


def test_multi_row_delete_without_dialog(page: Page) -> None:
    """Exercise grouped row deletion on two rows fully inside the viewport."""

    require = BASE_FUNCTION("require")
    saved_rows = BASE_FUNCTION("saved_rows")
    dialog_messages: list[str] = []
    page.on("dialog", lambda dialog: (dialog_messages.append(dialog.message), dialog.dismiss()))

    reset_table_viewport(page)
    before = saved_rows(page).count()
    first = saved_rows(page).nth(1)
    second = saved_rows(page).nth(2)
    first.locator(".journal-row-number").click()
    second.locator(".journal-row-number").click(modifiers=["Shift"])
    require(
        page.locator(".journal-row--multi-selected").count() == 2,
        "Shift-click did not select two visible rows.",
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
    reset_table_viewport(page)


smoke_globals = BASE_FUNCTION("run_smoke").__globals__
smoke_globals["test_row_drag_selection"] = test_row_drag_selection
smoke_globals["test_multi_row_delete_without_dialog"] = test_multi_row_delete_without_dialog


def main() -> None:
    RIBBON["main"]()


if __name__ == "__main__":
    main()
