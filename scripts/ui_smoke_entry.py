"""Final browser-smoke entry point with virtualization-safe row checks."""

from __future__ import annotations  # noqa: I001

import runpy
from pathlib import Path

from playwright.sync_api import Locator, Page


RIBBON_SCRIPT = Path(__file__).with_name("ui_smoke_ribbon.py")
RIBBON = runpy.run_path(
    str(RIBBON_SCRIPT),
    run_name="shift_helper_ui_smoke_ribbon_base",
)
BASE_FUNCTION = RIBBON["BASE_FUNCTION"]


def wait_for_full_repair(page: Page) -> None:
    page.wait_for_function(
        """() => {
            const root = document.getElementById('event-journal');
            return root?.dataset.operatorRepairReady === 'true'
                && root?.dataset.contextFallback === 'ready';
        }""",
        timeout=20_000,
    )


def reset_table_viewport(page: Page) -> None:
    holder = page.locator(".tabulator-tableholder")
    holder.evaluate("element => { element.scrollTop = 0; }")
    page.wait_for_timeout(300)


def visible_saved_rows(page: Page) -> Locator:
    return page.locator(".tabulator-row:not(.journal-row--draft):visible")


def click_row_header(
    page: Page,
    row: Locator,
    *,
    button: str = "left",
    shift: bool = False,
) -> None:
    """Click the visual row-header coordinates so browser hit testing is exercised."""

    header = row.locator(".journal-row-number")
    box = header.bounding_box()
    if box is None:
        raise AssertionError("Row-header geometry is unavailable.")
    x = box["x"] + (box["width"] / 2)
    y = box["y"] + (box["height"] / 2)
    if shift:
        page.keyboard.down("Shift")
    try:
        page.mouse.click(x, y, button=button)
    finally:
        if shift:
            page.keyboard.up("Shift")


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

    visible_target = saved_rows(page).nth(2)
    cell(visible_target, "description").click()
    require(
        page.locator(".journal-row--multi-selected").count() == 0,
        "Clicking a visible cell did not leave row-selection mode.",
    )

    reset_table_viewport(page)
    require(
        cell(visible_saved_rows(page).first, "description").is_visible(),
        "The first visible saved row did not return after resetting the viewport.",
    )


def test_multi_row_delete_without_dialog(page: Page) -> None:
    """Exercise grouped row deletion on two rows fully inside the viewport."""

    require = BASE_FUNCTION("require")
    saved_rows = BASE_FUNCTION("saved_rows")
    dialog_messages: list[str] = []
    page.on("dialog", lambda dialog: (dialog_messages.append(dialog.message), dialog.dismiss()))

    reset_table_viewport(page)
    before = saved_rows(page).count()
    rows = visible_saved_rows(page)
    first = rows.nth(1)
    second = rows.nth(2)
    click_row_header(page, first)
    click_row_header(page, second, shift=True)
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


def test_ribbon_contract(page: Page) -> None:
    """Verify Ribbon and context menus using only live virtualized rows."""

    require = BASE_FUNCTION("require")
    cell = BASE_FUNCTION("cell")

    wait_for_full_repair(page)
    reset_table_viewport(page)
    ribbon = page.locator("#journal-ribbon")
    require(ribbon.is_visible(), "The journal ribbon is not visible.")
    require(
        page.locator('[data-ribbon-tab="home"]').get_attribute("aria-selected") == "true",
        "The Home ribbon tab is not active by default.",
    )

    page.locator("#ribbon-collapse").click()
    require(ribbon.get_attribute("data-ribbon-state") == "collapsed", "The ribbon did not collapse.")
    page.locator('[data-ribbon-tab="data"]').click()
    require(
        ribbon.get_attribute("data-ribbon-state") == "temporary",
        "A collapsed ribbon did not open temporarily over the grid.",
    )
    require(
        page.locator('[data-ribbon-panel="data"]').is_visible(),
        "The temporary Data panel is not visible.",
    )
    page.locator("#ribbon-collapse").click()
    require(
        ribbon.get_attribute("data-ribbon-state") == "expanded",
        "The ribbon did not expand from temporary state.",
    )

    rows = visible_saved_rows(page)
    first = rows.nth(0)
    second = rows.nth(1)
    description = cell(first, "description")
    description.click()
    require(
        page.locator("#event-journal").get_attribute("data-selection-mode") == "cells",
        "A cell click did not leave column-selection mode.",
    )
    description.click(button="right")
    shell = page.locator(".journal-context-shell:visible")
    shell.wait_for(state="visible", timeout=5_000)
    require(
        shell.locator(".journal-mini-toolbar").is_visible(),
        "The formatting mini toolbar is missing.",
    )
    page.keyboard.press("Escape")
    shell.wait_for(state="hidden", timeout=5_000)

    click_row_header(page, first)
    click_row_header(page, second, shift=True)
    require(page.locator(".journal-row--multi-selected").count() == 2, "Two rows were not selected.")
    click_row_header(page, second, button="right")
    shell = page.locator(".journal-context-shell:visible")
    shell.wait_for(state="visible", timeout=5_000)
    require(
        page.locator(".journal-row--multi-selected").count() == 2,
        "Right click collapsed row selection.",
    )
    require(
        "2 строк" in shell.locator(".journal-context-menu").inner_text(),
        "Row menu lacks selection count.",
    )
    page.keyboard.press("Escape")
    cell(second, "description").click()
    require(page.locator(".journal-fill-handle").count() <= 1, "More than one fill handle exists.")


smoke_globals = BASE_FUNCTION("run_smoke").__globals__
smoke_globals["test_row_drag_selection"] = test_row_drag_selection
smoke_globals["test_multi_row_delete_without_dialog"] = test_multi_row_delete_without_dialog
RIBBON["wait_for_operator_repair"] = wait_for_full_repair
RIBBON["test_viewport_and_frozen_columns"].__globals__["test_ribbon_contract"] = test_ribbon_contract


def main() -> None:
    RIBBON["main"]()


if __name__ == "__main__":
    main()
