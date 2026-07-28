"""Focused acceptance checks for the operator Repair after video review."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def wait_ready(page: Page) -> None:
    page.wait_for_function(
        """() => {
            const root = document.getElementById('event-journal');
            return root?.dataset.videoAcceptanceRepair === 'ready'
                && root.dataset.operatorRepairReady === 'true'
                && root.dataset.viewportController === 'geometry-only'
                && root.dataset.sheetViewport === 'ready'
                && Boolean(document.getElementById('journal-sheet-viewport'))
                && Boolean(document.getElementById('journal-sheet-layer'))
                && Boolean(window.shiftHelperZoom?.layer?.())
                && Boolean(window.shiftHelperOperatorRepair);
        }""",
        timeout=20_000,
    )


def set_zoom(page: Page, value: int) -> dict[str, float]:
    page.evaluate("(value) => window.shiftHelperZoom.apply(value)", value)
    page.wait_for_function(
        """(value) => {
            const root = document.getElementById('event-journal');
            const layer = document.getElementById('journal-sheet-layer');
            return root?.dataset.sheetZoom === String(value)
                && layer?.dataset.sheetZoom === String(value);
        }""",
        arg=value,
    )
    page.wait_for_timeout(160)
    return page.evaluate(
        """() => {
            const table = window.shiftHelperEventGrid;
            const holder = document.querySelector('.tabulator-tableholder');
            const holderRect = holder?.getBoundingClientRect();
            const row = table.getRows('active').find(candidate => {
                const rect = candidate.getElement()?.getBoundingClientRect();
                return rect && holderRect && rect.bottom > holderRect.top && rect.top < holderRect.bottom;
            }) || table.getRows('active')[0];
            const cell = row?.getCell('description')?.getElement?.();
            const cellRect = cell?.getBoundingClientRect();
            const ribbonRect = document.getElementById('journal-ribbon')?.getBoundingClientRect();
            const undoRect = document.getElementById('journal-undo')?.getBoundingClientRect();
            const viewportRect = document.getElementById('journal-sheet-viewport')?.getBoundingClientRect();
            const layerRect = document.getElementById('journal-sheet-layer')?.getBoundingClientRect();
            return {
                cellWidth: cellRect?.width || 0,
                cellTop: cellRect?.top || 0,
                cellBottom: cellRect?.bottom || 0,
                ribbonWidth: undoRect?.width || 0,
                ribbonHeight: ribbonRect?.height || 0,
                viewportWidth: viewportRect?.width || 0,
                viewportHeight: viewportRect?.height || 0,
                viewportTop: viewportRect?.top || 0,
                viewportBottom: viewportRect?.bottom || 0,
                layerWidth: layerRect?.width || 0,
                layerHeight: layerRect?.height || 0,
            };
        }"""
    )


def test_linear_zoom(page: Page) -> None:
    metrics_100 = set_zoom(page, 100)
    metrics_50 = set_zoom(page, 50)
    metrics_200 = set_zoom(page, 200)
    require(metrics_100["cellWidth"] > 0, f"Sheet cell geometry is unavailable: {metrics_100}")
    require(
        math.isclose(metrics_50["cellWidth"] / metrics_100["cellWidth"], 0.5, rel_tol=0.08),
        f"50% sheet zoom is not linear: {metrics_50=} {metrics_100=}",
    )
    require(
        math.isclose(metrics_200["cellWidth"] / metrics_100["cellWidth"], 2.0, rel_tol=0.08),
        f"200% sheet zoom is not linear: {metrics_200=} {metrics_100=}",
    )
    require(
        math.isclose(metrics_50["ribbonWidth"], metrics_100["ribbonWidth"], rel_tol=0.03)
        and math.isclose(metrics_200["ribbonWidth"], metrics_100["ribbonWidth"], rel_tol=0.03),
        f"Ribbon controls scale together with the sheet: {metrics_50=} {metrics_100=} {metrics_200=}",
    )
    set_zoom(page, 100)


def test_sheet_only_zoom_at_400(page: Page) -> None:
    metrics = set_zoom(page, 400)
    require(metrics["viewportHeight"] >= 180, f"400% zoom collapsed the sheet viewport: {metrics}")
    require(
        metrics["cellBottom"] > metrics["viewportTop"]
        and metrics["cellTop"] < metrics["viewportBottom"],
        f"No usable table row remains in the viewport at 400%: {metrics}",
    )
    require(
        math.isclose(metrics["layerWidth"], metrics["viewportWidth"], rel_tol=0.03)
        and math.isclose(metrics["layerHeight"], metrics["viewportHeight"], rel_tol=0.03),
        f"Inverse sheet-layer sizing does not preserve the viewport: {metrics}",
    )
    require(
        page.locator(".journal-workspace").evaluate("element => element.style.zoom") == "",
        "400% sheet zoom reached the whole workspace and Ribbon.",
    )
    set_zoom(page, 100)


def mark_rows_and_cell(page: Page) -> None:
    page.evaluate(
        """() => {
            const rows = window.shiftHelperEventGrid.getRows('active').slice(0, 5);
            if (rows.length < 5) throw new Error('Not enough visible rows.');
            rows.forEach((row, index) => {
                const number = row.getElement().querySelector('.journal-row-number');
                if (number) number.dataset.stage8Row = String(index);
            });
            const cell = rows[0].getCell('description');
            cell.getElement().dataset.stage8Cell = 'true';
        }"""
    )


def test_row_drag(page: Page) -> None:
    mark_rows_and_cell(page)
    first = page.locator('[data-stage8-row="0"]')
    third = page.locator('[data-stage8-row="2"]')
    first.scroll_into_view_if_needed()
    start = first.bounding_box()
    end = third.bounding_box()
    require(start is not None and end is not None, "Row headers are not visible.")
    page.mouse.move(start["x"] + start["width"] / 2, start["y"] + start["height"] / 2)
    page.mouse.down()
    page.mouse.move(end["x"] + end["width"] / 2, end["y"] + end["height"] / 2, steps=8)
    page.mouse.up()
    page.wait_for_timeout(150)

    selected = page.evaluate("() => [...(window.shiftHelperSelectedRowKeys || [])]")
    require(len(selected) == 3, f"Row drag selected {len(selected)} rows instead of 3: {selected}")
    require(
        page.locator(".journal-row--multi-selected").count() == 3,
        "Visual row selection does not match the controller state.",
    )


def select_description_cell(page: Page) -> None:
    page.evaluate(
        """() => {
            const table = window.shiftHelperEventGrid;
            const rows = table.getRows('active');
            const row = rows[0];
            const cell = row.getCell('description');
            (table.getRanges?.() || []).forEach(range => range.remove());
            table.addRange(cell, cell);
            cell.getElement().click();
            document.getElementById('event-journal').dataset.selectionMode = 'cells';
            window.shiftHelperSelectedRowKeys = [];
            document.querySelectorAll('.journal-row--multi-selected').forEach(
                node => node.classList.remove('journal-row--multi-selected')
            );
        }"""
    )
    page.wait_for_timeout(80)


def test_formatting_survives_alignment(page: Page) -> None:
    select_description_cell(page)
    page.locator('[data-text-style="bold"]').click()
    page.locator("#operator-text-color-control .operator-fill-arrow").click()
    palette = page.locator('.operator-color-palette[data-owner="text"]')
    palette.wait_for(state="visible", timeout=5_000)
    palette.locator('button[title="#c00000"]').click()
    page.wait_for_timeout(80)

    before = page.locator('[data-stage8-cell="true"] .journal-cell-value').evaluate(
        """element => ({
            weight: getComputedStyle(element).fontWeight,
            color: getComputedStyle(element).color,
        })"""
    )
    page.locator('[data-align-horizontal="center"]').click()
    page.wait_for_timeout(80)
    after = page.locator('[data-stage8-cell="true"] .journal-cell-value').evaluate(
        """element => ({
            weight: getComputedStyle(element).fontWeight,
            color: getComputedStyle(element).color,
            horizontal: element.dataset.horizontal,
        })"""
    )
    require(after["horizontal"] == "center", f"Alignment was not applied: {after}")
    require(after["weight"] == before["weight"], f"Bold was reset by alignment: {before} -> {after}")
    require(after["color"] == before["color"], f"Text color was reset by alignment: {before} -> {after}")


def test_palette_closes(page: Page) -> None:
    arrow = page.locator("#operator-text-color-control .operator-fill-arrow")
    arrow.click()
    page.locator('.operator-color-palette[data-owner="text"]').wait_for(state="visible")
    page.locator("#journal-title").click()
    require(
        page.locator('.operator-color-palette[data-owner="text"]').count() == 0,
        "Text palette did not close after an outside click.",
    )

    arrow.click()
    page.locator('.operator-color-palette[data-owner="text"]').wait_for(state="visible")
    page.keyboard.press("Escape")
    require(
        page.locator('.operator-color-palette[data-owner="text"]').count() == 0,
        "Text palette did not close on Escape.",
    )
    require(arrow.get_attribute("aria-expanded") == "false", "Palette trigger remains expanded.")


def test_font_size_dropdown_and_ribbon_geometry(page: Page) -> None:
    select = page.locator("#ribbon-font-size")
    require(select.is_visible(), "Font-size dropdown is hidden.")
    options = select.locator("option").all_text_contents()
    require("8" in options and "96" in options, f"Font-size list is incomplete: {options}")
    select.select_option("14")
    page.locator("#operator-font-increase").click()
    require(select.input_value() == "15", "Increase-font command did not update the dropdown.")
    page.locator("#operator-font-decrease").click()
    require(select.input_value() == "14", "Decrease-font command did not update the dropdown.")

    geometry = page.evaluate(
        """() => {
            const ids = ['ribbon-font-family', 'ribbon-font-size',
                'operator-font-decrease', 'operator-font-increase'];
            return ids.map(id => {
                const rect = document.getElementById(id).getBoundingClientRect();
                return {id, left: rect.left, right: rect.right, top: rect.top,
                    bottom: rect.bottom, width: rect.width, height: rect.height};
            });
        }"""
    )
    require(
        all(item["width"] > 0 and item["height"] > 0 for item in geometry),
        f"Hidden Ribbon control: {geometry}",
    )
    ordered = sorted(geometry, key=lambda item: item["left"])
    for left, right in zip(ordered, ordered[1:], strict=False):
        require(
            right["left"] >= left["right"] - 1,
            f"Ribbon font controls overlap: {left} / {right}",
        )


def run(url: str, screenshot: Path) -> None:
    browser_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1680, "height": 960})
        page = context.new_page()
        page.on("pageerror", lambda error: browser_errors.append(f"pageerror: {error}"))
        page.on(
            "console",
            lambda message: browser_errors.append(f"console: {message.text}")
            if message.type == "error"
            else None,
        )
        try:
            page.goto(f"{url.rstrip('/')}/events", wait_until="networkidle")
            page.locator(".event-grid.tabulator").wait_for(state="visible", timeout=20_000)
            wait_ready(page)
            test_linear_zoom(page)
            test_sheet_only_zoom_at_400(page)
            test_row_drag(page)
            test_formatting_survives_alignment(page)
            test_palette_closes(page)
            test_font_size_dropdown_and_ribbon_geometry(page)
            require(not browser_errors, "Browser errors: " + " | ".join(browser_errors))
        except Exception:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(screenshot), full_page=False, timeout=5_000)
            except Exception as screenshot_error:  # pragma: no cover - best-effort diagnostics
                print(f"Stage 8 diagnostic screenshot failed: {screenshot_error}", file=sys.stderr)
            raise
        finally:
            context.close()
            browser.close()


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: ui_smoke_acceptance_stage8.py <base-url> [screenshot-path]")
    screenshot = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-stage8-failure.png")
    run(sys.argv[1], screenshot)
    print("Shift-Helper acceptance stage 8 Repair smoke passed.")


if __name__ == "__main__":
    main()
