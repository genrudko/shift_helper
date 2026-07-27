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


def open_view_settings(page: Page) -> None:
    page.locator('[data-ribbon-tab="view"]').click()
    page.locator("#open-view-settings").click()
    page.locator("#journal-view-settings").wait_for(state="visible", timeout=5_000)


def test_ribbon_contract(page: Page) -> None:
    require = BASE_FUNCTION("require")
    saved_rows = BASE_FUNCTION("saved_rows")
    cell = BASE_FUNCTION("cell")

    ribbon = page.locator("#journal-ribbon")
    require(ribbon.is_visible(), "The journal ribbon is not visible.")
    require(
        page.locator('[data-ribbon-tab="home"]').get_attribute("aria-selected") == "true",
        "The Home ribbon tab is not active by default.",
    )

    page.locator("#ribbon-collapse").click()
    require(
        ribbon.get_attribute("data-ribbon-state") == "collapsed",
        "The ribbon did not collapse.",
    )
    page.locator('[data-ribbon-tab="data"]').click()
    require(
        ribbon.get_attribute("data-ribbon-state") == "temporary",
        "A collapsed ribbon did not open temporarily over the grid.",
    )
    require(
        page.locator('[data-ribbon-panel="data"]').is_visible(),
        "The temporary Data ribbon panel is not visible.",
    )
    page.locator("#ribbon-collapse").click()
    require(
        ribbon.get_attribute("data-ribbon-state") == "expanded",
        "The ribbon did not return to the expanded state.",
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
        "The formatting mini toolbar is missing above the context menu.",
    )
    page.keyboard.press("Escape")
    shell.wait_for(state="hidden", timeout=5_000)

    first.locator(".journal-row-number").click()
    second.locator(".journal-row-number").click(modifiers=["Shift"])
    require(
        page.locator(".journal-row--multi-selected").count() == 2,
        "Two rows were not selected before the context-menu check.",
    )
    second.locator(".journal-row-number").click(button="right")
    shell.wait_for(state="visible", timeout=5_000)
    require(
        page.locator(".journal-row--multi-selected").count() == 2,
        "Right click collapsed the existing multi-row selection.",
    )
    require(
        "2 строк" in shell.locator(".journal-context-menu").inner_text(),
        "The row context menu does not state how many rows it will affect.",
    )
    page.keyboard.press("Escape")
    cell(second, "description").click()

    require(
        page.locator(".journal-fill-handle").count() <= 1,
        "More than one fill handle exists in the document.",
    )


def test_viewport_and_frozen_columns(page: Page) -> None:
    require = BASE_FUNCTION("require")
    saved_rows = BASE_FUNCTION("saved_rows")
    cell = BASE_FUNCTION("cell")
    frozen_fields = VIEWPORT["frozen_fields"]
    clear_grid_selection = VIEWPORT["clear_grid_selection"]

    test_ribbon_contract(page)
    open_view_settings(page)
    dialog = page.locator("#journal-view-settings")

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
            "element => getComputedStyle(element)"
            ".getPropertyValue('--ui-scale-factor').trim()"
        )
        == "1.4",
        "Dimension-based interface scale was not applied.",
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
    start_background = start_cell.evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
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
    require(
        cell_box is not None and handle_box is not None,
        "Fill-handle geometry is unavailable.",
    )
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
    require(
        page.locator("html").get_attribute("data-theme") == "light",
        "Theme was not persisted.",
    )
    require(
        page.locator("body").evaluate("element => element.style.zoom") == "",
        "CSS zoom returned after page reload.",
    )
    require(
        frozen_fields(page) == ["start_date", "start_time", "asset_label"],
        "Frozen-column preference was not restored after reload.",
    )


BASE_FUNCTION("run_smoke").__globals__["test_viewport_and_frozen_columns"] = (
    test_viewport_and_frozen_columns
)


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: ui_smoke_ribbon.py <base-url> [screenshot-path]")
    screenshot_path = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-smoke-failure.png")
    BASE_FUNCTION("run_smoke")(sys.argv[1], screenshot_path)
    print("Shift-Helper UX-GRID-002 ribbon smoke test passed.")


if __name__ == "__main__":
    main()
