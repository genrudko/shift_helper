"""Compatibility wrapper for the full smoke suite after adding two color palettes."""

from __future__ import annotations  # noqa: I001

import runpy
from pathlib import Path

from playwright.sync_api import Page

ENTRY_SCRIPT = Path(__file__).with_name("ui_smoke_entry.py")
ENTRY = runpy.run_path(str(ENTRY_SCRIPT), run_name="shift_helper_ui_smoke_entry_base")
RIBBON = ENTRY["RIBBON"]
BASE_FUNCTION = RIBBON["BASE_FUNCTION"]


def wait_for_complete_view(page: Page) -> None:
    """Wait until repaired controllers and persisted sheet geometry agree."""

    page.wait_for_function(
        """() => {
            const root = document.getElementById('event-journal');
            let preferences = {};
            try {
                preferences = JSON.parse(
                    localStorage.getItem('shift-helper-ui-preferences-v1') || '{}'
                );
            } catch (_error) {
                return false;
            }
            const expectedZoom = String(Number(preferences.zoom) || 100);
            return root?.dataset.operatorRepairReady === 'true'
                && root.dataset.videoAcceptanceRepair === 'ready'
                && root.dataset.liveViewPreferences === 'ready'
                && root.dataset.contextFallback === 'ready'
                && root.dataset.zoomApplying !== 'true'
                && root.dataset.sheetZoom === expectedZoom;
        }""",
        timeout=20_000,
    )


def test_operator_repairs(page: Page) -> None:
    """Run the original operator checks with an explicit fill-palette selector."""

    require = BASE_FUNCTION("require")
    saved_rows = BASE_FUNCTION("saved_rows")
    cell = BASE_FUNCTION("cell")
    wait_for_complete_view(page)

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
    page.locator("#operator-fill-control .operator-fill-arrow").click()
    palette = page.locator('.operator-color-palette:not([data-owner="text"])')
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
        header.evaluate("element => element.classList.contains('operator-column-selected')"),
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


RIBBON["wait_for_operator_repair"] = wait_for_complete_view
RIBBON["test_viewport_and_frozen_columns"].__globals__["wait_for_operator_repair"] = (
    wait_for_complete_view
)
RIBBON["test_operator_repairs"] = test_operator_repairs
RIBBON["test_viewport_and_frozen_columns"].__globals__["test_operator_repairs"] = test_operator_repairs


if __name__ == "__main__":
    ENTRY["main"]()
