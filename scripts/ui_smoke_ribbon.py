"""Ribbon-aware entry point for the Shift-Helper browser smoke suite."""

from __future__ import annotations  # noqa: I001

import runpy
import sys
from pathlib import Path

from playwright.sync_api import Page


VIEWPORT_SCRIPT = Path(__file__).with_name("ui_smoke_viewport.py")
VIEWPORT = runpy.run_path(
    str(VIEWPORT_SCRIPT),
    run_name="shift_helper_ui_smoke_viewport_base",
)
BASE_FUNCTION = VIEWPORT["base_function"]


def wait_for_operator_repair(page: Page) -> None:
    page.wait_for_function(
        "document.getElementById('event-journal')?.dataset.operatorRepairReady === 'true'",
        timeout=20_000,
    )


def open_view_settings(page: Page) -> None:
    page.locator('[data-ribbon-tab="view"]').click()
    page.locator("#open-view-settings").click()
    page.locator("#journal-view-settings").wait_for(state="visible", timeout=5_000)


def test_operator_repairs(page: Page) -> None:
    require = BASE_FUNCTION("require")
    saved_rows = BASE_FUNCTION("saved_rows")
    cell = BASE_FUNCTION("cell")

    wait_for_operator_repair(page)
    root = page.locator("#event-journal")
    zoom = page.locator("#ribbon-zoom")
    require(zoom.get_attribute("min") == "10", "Zoom minimum is not 10%.")
    require(zoom.get_attribute("max") == "400", "Zoom maximum is not 400%.")

    zoom.fill("100")
    zoom.hover()
    page.mouse.wheel(0, -100)
    page.wait_for_timeout(150)
    require(zoom.input_value() == "105", "Mouse wheel does not change zoom over the slider.")

    first = saved_rows(page).first
    description = cell(first, "description")
    description.click()
    page.locator(".operator-fill-arrow").click()
    palette = page.locator(".operator-color-palette")
    palette.wait_for(state="visible", timeout=5_000)
    palette.locator('[title="#ffd966"]').click()
    page.wait_for_timeout(250)
    require(
        description.evaluate("element => getComputedStyle(element).backgroundColor")
        == "rgb(255, 217, 102)",
        "Manual fill is not visible on the selected cell.",
    )
    page.evaluate("document.getElementById('clear-cell-fill').click()")
    page.wait_for_timeout(150)

    require(
        page.locator("#ribbon-font-family option").count() >= 20,
        "The ribbon still exposes too few font families.",
    )
    require(page.locator("#operator-font-size").is_visible(), "Manual font-size input is missing.")
    require(page.locator("#operator-text-direction").is_visible(), "Text-direction command is missing.")

    page.evaluate("window.shiftHelperEventGrid.setSort('start_date', 'desc')")
    page.wait_for_timeout(500)
    sorted_flags = page.evaluate(
        "window.shiftHelperEventGrid.getRows('active').map(row => Boolean(row.getData()._draft))"
    )
    first_draft = next((index for index, flag in enumerate(sorted_flags) if flag), len(sorted_flags))
    require(
        not any(not flag for flag in sorted_flags[first_draft:]),
        "Reverse sorting placed a real record below draft rows.",
    )
    require(
        root.get_attribute("data-draft-aware-sort") == "ready",
        "Draft-aware sorters were not installed.",
    )

    header = page.locator(
        '.tabulator-col[tabulator-field="description"], '
        '.tabulator-col[data-field="description"]'
    )
    header.click(position={"x": 48, "y": 14})
    require(
        root.get_attribute("data-selection-mode") == "columns",
        "Column header did not select the column.",
    )
    require(
        header.evaluate(
            "element => element.classList.contains('operator-column-selected')"
        ),
        "Selected column header is not marked.",
    )

    holder = page.locator(".tabulator-tableholder")
    before_ranges = page.evaluate("window.shiftHelperEventGrid.getRanges().length")
    box = holder.bounding_box()
    require(box is not None, "Table viewport geometry is unavailable for middle-button panning.")
    start_x = box["x"] + min(300, box["width"] / 2)
    start_y = box["y"] + min(220, box["height"] / 2)
    page.mouse.move(start_x, start_y)
    page.mouse.down(button="middle")
    page.mouse.move(start_x - 80, start_y - 60, steps=5)
    page.mouse.up(button="middle")
    after_ranges = page.evaluate("window.shiftHelperEventGrid.getRanges().length")
    require(after_ranges == before_ranges, "Middle-button panning changed the cell selection.")


def test_ribbon_contract(page: Page) -> None:
    require = BASE_FUNCTION("require")
    saved_rows = BASE_FUNCTION("saved_rows")
    cell = BASE_FUNCTION("cell")

    wait_for_operator_repair(page)
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

    rows = saved_rows(page)
    first = rows.nth(0)
    second = rows.nth(1)
    description = cell(first, "description")
    description.click(button="right")
    shell = page.locator(".journal-context-shell")
    shell.wait_for(state="visible", timeout=5_000)
    require(
        shell.locator(".journal-mini-toolbar").is_visible(),
        "The formatting mini toolbar is missing.",
    )
    page.keyboard.press("Escape")
    shell.wait_for(state="hidden", timeout=5_000)

    first.locator(".journal-row-number").click()
    second.locator(".journal-row-number").click(modifiers=["Shift"])
    require(page.locator(".journal-row--multi-selected").count() == 2, "Two rows were not selected.")
    second.locator(".journal-row-number").click(button="right")
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


def test_viewport_and_frozen_columns(page: Page) -> None:
    require = BASE_FUNCTION("require")
    saved_rows = BASE_FUNCTION("saved_rows")
    cell = BASE_FUNCTION("cell")
    frozen_fields = VIEWPORT["frozen_fields"]
    clear_grid_selection = VIEWPORT["clear_grid_selection"]

    test_operator_repairs(page)
    page.evaluate("window.shiftHelperEventGrid.clearSort()")
    test_ribbon_contract(page)
    open_view_settings(page)
    dialog = page.locator("#journal-view-settings")

    page.locator("#journal-theme").select_option("dark")
    page.locator("#journal-zoom").fill("400")
    page.locator("#journal-font-size").fill("15")
    page.locator("#journal-font-family").select_option("Tahoma")
    page.locator("#journal-frozen-through").select_option("none")
    page.wait_for_timeout(700)

    require(
        page.locator("body").evaluate("element => element.style.zoom") == "",
        "CSS zoom reached the page body.",
    )
    require(
        page.locator("html").evaluate(
            "element => getComputedStyle(element).getPropertyValue('--ui-scale-factor').trim()"
        ) == "1",
        "Application chrome is still being scaled with the sheet.",
    )
    require(
        page.locator("#event-journal").evaluate("element => element.style.zoom") == "",
        "CSS zoom reached the table container.",
    )
    require(
        page.locator("#event-journal").get_attribute("data-sheet-zoom") == "400",
        "The table sheet did not reach 400% zoom.",
    )
    require(
        page.locator("html").evaluate(
            "element => getComputedStyle(element).getPropertyValue('--journal-font-size').trim()"
        ) == "15px",
        "Sheet zoom changed the stored base font metric and would double-scale text.",
    )
    require(not frozen_fields(page), "Frozen columns were not fully disabled.")

    dialog.locator('button[value="close"]').last.click()
    dialog.wait_for(state="hidden", timeout=5_000)
    page.set_viewport_size({"width": 1180, "height": 760})
    page.wait_for_timeout(600)
    require(
        page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 2"),
        "The ribbon causes page-level horizontal overflow after scaling.",
    )

    clear_grid_selection(page)
    first = saved_rows(page).first
    start_cell = cell(first, "start_date")
    description = cell(first, "description")
    start_background = start_cell.evaluate("element => getComputedStyle(element).backgroundColor")
    description_background = description.evaluate("element => getComputedStyle(element).backgroundColor")
    require(
        start_background == description_background,
        "Dark theme palettes differ across table sections.",
    )

    description.click()
    handle = page.locator(".journal-fill-handle:not([hidden])")
    handle.wait_for(state="visible", timeout=5_000)
    page.wait_for_timeout(250)
    cell_box = description.bounding_box()
    handle_box = handle.bounding_box()
    require(cell_box is not None and handle_box is not None, "Fill-handle geometry is unavailable.")
    require(
        abs((handle_box["x"] + handle_box["width"] / 2) - (cell_box["x"] + cell_box["width"])) <= 6,
        "Fill handle moved horizontally after scaling.",
    )
    require(
        abs((handle_box["y"] + handle_box["height"] / 2) - (cell_box["y"] + cell_box["height"])) <= 6,
        "Fill handle moved vertically after scaling.",
    )

    open_view_settings(page)
    page.locator("#journal-frozen-through").select_option("asset_label")
    page.wait_for_timeout(700)
    require(
        frozen_fields(page) == ["start_date", "start_time", "asset_label"],
        "The configurable frozen-column boundary was not applied.",
    )

    page.locator("#journal-theme").select_option("light")
    page.locator("#journal-zoom").fill("110")
    page.wait_for_timeout(350)
    preferences = page.evaluate("JSON.parse(localStorage.getItem('shift-helper-ui-preferences-v1'))")
    require(preferences["zoom"] == 110, "Interface scale was not saved.")
    require(preferences["fontSize"] == 15, "Font size was not saved.")
    require(preferences["fontFamily"] == "Tahoma", "Font family was not saved.")
    require(preferences["frozenThrough"] == "asset_label", "Frozen-column preference was not saved.")

    dialog.locator('button[value="close"]').last.click()
    dialog.wait_for(state="hidden", timeout=5_000)
    page.set_viewport_size({"width": 1680, "height": 960})
    page.reload(wait_until="networkidle")
    page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)
    wait_for_operator_repair(page)
    require(page.locator("html").get_attribute("data-theme") == "light", "Theme was not persisted.")
    require(
        page.locator("body").evaluate("element => element.style.zoom") == "",
        "CSS zoom returned on body.",
    )
    require(
        page.locator("#event-journal").evaluate("element => element.style.zoom") == "",
        "CSS zoom returned on the table container.",
    )
    require(
        page.locator("#event-journal").get_attribute("data-sheet-zoom") == "110",
        "Table zoom was not restored after reload.",
    )
    require(
        frozen_fields(page) == ["start_date", "start_time", "asset_label"],
        "Frozen-column preference was not restored after reload.",
    )


BASE_FUNCTION("run_smoke").__globals__[
    "test_viewport_and_frozen_columns"
] = test_viewport_and_frozen_columns


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: ui_smoke_ribbon.py <base-url> [screenshot-path]")
    screenshot_path = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-smoke-failure.png")
    BASE_FUNCTION("run_smoke")(sys.argv[1], screenshot_path)
    print("Shift-Helper UX-GRID-002 ribbon smoke test passed.")


if __name__ == "__main__":
    main()
