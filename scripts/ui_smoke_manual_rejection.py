"""Manual-rejection regressions derived from the 2026-07-29 operator video."""

from __future__ import annotations

import json
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
            return root?.dataset.operatorRepairReady === 'true'
                && root.dataset.videoAcceptanceRepair === 'ready'
                && root.dataset.selectionModeContract === 'ready'
                && root.dataset.stage4AlignmentContract === 'ready'
                && Boolean(window.shiftHelperFormattingContract);
        }""",
        timeout=20_000,
    )


def visible_rows(page: Page):
    return page.locator(".tabulator-row:visible")


def cell(row, field: str):
    return row.locator(f'.tabulator-cell[tabulator-field="{field}"]')


def test_row_drag_integrity(page: Page) -> None:
    rows = visible_rows(page)
    require(rows.count() >= 8, "Not enough visible rows for drag-selection regression.")

    # Reproduce the video exactly: leave an active cell on a row that the
    # subsequent row-number drag crosses.
    cell(rows.nth(3), "description").click()
    page.wait_for_timeout(120)
    require(
        page.locator(".tabulator-range-active, .tabulator-range-selected").count() > 0,
        "The precondition active cell range was not established.",
    )

    start = rows.nth(0).locator(".journal-row-number")
    end = rows.nth(6).locator(".journal-row-number")
    start_box = start.bounding_box()
    end_box = end.bounding_box()
    require(start_box is not None and end_box is not None, "Row-number drag geometry is unavailable.")

    page.mouse.move(
        start_box["x"] + start_box["width"] / 2,
        start_box["y"] + start_box["height"] / 2,
    )
    page.mouse.down()
    page.mouse.move(
        end_box["x"] + end_box["width"] / 2,
        end_box["y"] + end_box["height"] / 2,
        steps=14,
    )
    page.mouse.up()
    page.wait_for_timeout(300)

    diagnostic = page.evaluate(
        """() => {
            const root = document.getElementById('event-journal');
            const holder = root.querySelector('.tabulator-tableholder');
            const holderRect = holder.getBoundingClientRect();
            const rendered = [...root.querySelectorAll('.tabulator-row')]
                .filter(row => {
                    const rect = row.getBoundingClientRect();
                    return rect.bottom > holderRect.top && rect.top < holderRect.bottom;
                })
                .slice(0, 7)
                .map(row => {
                    const rect = row.getBoundingClientRect();
                    const number = row.querySelector('.journal-row-number');
                    const numberRect = number?.getBoundingClientRect();
                    const cells = [...row.querySelectorAll('.tabulator-cell')];
                    return {
                        key: row.dataset.rowKey || null,
                        selected: row.classList.contains('journal-row--multi-selected'),
                        opacity: getComputedStyle(row).opacity,
                        display: getComputedStyle(row).display,
                        visibility: getComputedStyle(row).visibility,
                        top: rect.top,
                        bottom: rect.bottom,
                        height: rect.height,
                        number: number?.textContent?.trim() || '',
                        numberHeight: numberRect?.height || 0,
                        cellCount: cells.length,
                        visibleCells: cells.filter(cell => {
                            const box = cell.getBoundingClientRect();
                            const style = getComputedStyle(cell);
                            return box.height > 10
                                && style.display !== 'none'
                                && style.visibility !== 'hidden'
                                && style.opacity !== '0';
                        }).length,
                    };
                });
            return {
                mode: root.dataset.selectionMode,
                controllerKeys: [...(window.shiftHelperSelectedRowKeys || [])],
                contractKeys: window.shiftHelperSelectionModeContract?.rowKeys?.() || [],
                visualCount: root.querySelectorAll('.journal-row--multi-selected').length,
                ranges: window.shiftHelperEventGrid.getRanges?.().length || 0,
                rendered,
            };
        }"""
    )

    require(diagnostic["mode"] == "rows", f"Row mode was not entered: {diagnostic}")
    require(
        len(diagnostic["controllerKeys"]) == 7,
        f"Controller selected the wrong number of rows: {diagnostic}",
    )
    require(
        len(diagnostic["contractKeys"]) == 7 and diagnostic["visualCount"] == 7,
        f"Logical and visual row selection diverged: {diagnostic}",
    )
    require(diagnostic["ranges"] == 0, f"Stale cell range survived row mode: {diagnostic}")
    require(len(diagnostic["rendered"]) == 7, f"Selected rows are not all rendered: {diagnostic}")

    for index, metric in enumerate(diagnostic["rendered"], start=1):
        require(metric["selected"], f"Row {index} lost its selection class: {diagnostic}")
        require(metric["opacity"] != "0", f"Row {index} became transparent: {diagnostic}")
        require(metric["display"] != "none", f"Row {index} disappeared: {diagnostic}")
        require(metric["visibility"] != "hidden", f"Row {index} became hidden: {diagnostic}")
        require(metric["height"] > 20, f"Row {index} collapsed: {diagnostic}")
        require(metric["numberHeight"] > 20, f"Row number {index} collapsed: {diagnostic}")
        require(metric["number"] == str(index), f"Row-number continuity broke: {diagnostic}")
        require(metric["cellCount"] >= 10 and metric["visibleCells"] >= 10, (
            f"Row {index} lost its grid cells: {diagnostic}"
        ))

    for previous, current in zip(diagnostic["rendered"], diagnostic["rendered"][1:], strict=False):
        require(
            abs(current["top"] - previous["bottom"]) <= 2,
            f"A blank physical gap remained between selected rows: {diagnostic}",
        )


def formatting_snapshot(page: Page) -> dict:
    return page.evaluate(
        """() => {
            const cell = document.querySelector(
                '.tabulator-row:visible .tabulator-cell[tabulator-field="description"]'
            );
            const value = cell?.querySelector('.journal-cell-value');
            const row = cell?.closest('.tabulator-row');
            const table = window.shiftHelperEventGrid;
            const component = table.getRows('visible').find(
                candidate => candidate.getElement() === row
            )?.getCell('description');
            const rowKey = component?.getRow().getData()._rowKey;
            const read = key => JSON.parse(localStorage.getItem(key) || '{}');
            const style = value ? getComputedStyle(value) : null;
            const cellStyle = cell ? getComputedStyle(cell) : null;
            return {
                rowKey,
                textStore: read('shift-helper-event-cell-text-style-v1'),
                alignmentStore: read('shift-helper-event-cell-alignment-v3'),
                fillStore: read('shift-helper-event-cell-fill-v3'),
                fontWeight: style?.fontWeight || null,
                fontStyle: style?.fontStyle || null,
                color: style?.color || null,
                textAlign: style?.textAlign || null,
                cellTextAlign: cellStyle?.textAlign || null,
                background: cellStyle?.backgroundColor || null,
                horizontal: value?.dataset.horizontal || null,
                vertical: value?.dataset.vertical || null,
                boldActive: document.querySelector(
                    '[data-text-style="bold"].is-active'
                ) !== null,
                italicActive: document.querySelector(
                    '[data-text-style="italic"].is-active'
                ) !== null,
                rightActive: document.querySelector(
                    '[data-align-horizontal="right"].is-active'
                ) !== null,
            };
        }"""
    )


def assert_formatting(snapshot: dict, stage: str) -> None:
    row_key = snapshot["rowKey"]
    require(row_key, f"Formatted cell key is unavailable after {stage}: {snapshot}")
    text = snapshot["textStore"].get(row_key, {}).get("description", {})
    alignment = snapshot["alignmentStore"].get(row_key, {}).get("description", {})
    fill = snapshot["fillStore"].get(row_key, {}).get("description")

    require(text.get("bold") is True, f"Bold was lost after {stage}: {snapshot}")
    require(text.get("italic") is True, f"Italic was lost after {stage}: {snapshot}")
    require(text.get("color", "").lower() == "#c00000", (
        f"Text color was lost after {stage}: {snapshot}"
    ))
    require(alignment.get("horizontal") == "right", (
        f"Alignment was lost after {stage}: {snapshot}"
    ))
    require((fill or "").lower() == "#fff2cc", f"Fill was lost after {stage}: {snapshot}")

    require(snapshot["fontWeight"] in {"700", "bold"}, (
        f"Bold is not rendered after {stage}: {snapshot}"
    ))
    require(snapshot["fontStyle"] == "italic", f"Italic is not rendered after {stage}: {snapshot}")
    require(snapshot["color"] == "rgb(192, 0, 0)", (
        f"Text color is not rendered after {stage}: {snapshot}"
    ))
    require(snapshot["background"] == "rgb(255, 242, 204)", (
        f"Fill is not rendered after {stage}: {snapshot}"
    ))
    require(snapshot["textAlign"] == "right" and snapshot["cellTextAlign"] == "right", (
        f"Alignment is not rendered after {stage}: {snapshot}"
    ))
    require(snapshot["horizontal"] == "right", (
        f"Alignment metadata diverged after {stage}: {snapshot}"
    ))
    require(
        snapshot["boldActive"] and snapshot["italicActive"] and snapshot["rightActive"],
        f"Ribbon state diverged from the cell after {stage}: {snapshot}",
    )


def test_composite_formatting(page: Page) -> None:
    row = visible_rows(page).first
    target = cell(row, "description")
    target.click()
    page.wait_for_timeout(120)

    page.locator('[data-ribbon-tab="home"]').click()
    page.locator('[data-text-style="bold"]:visible').first.click()
    page.locator('[data-text-style="italic"]:visible').first.click()
    page.locator('[data-align-horizontal="right"]:visible').first.click()
    page.locator("#operator-fill-control .operator-fill-main").click()

    page.locator("#operator-text-color-control .operator-fill-arrow").click()
    palette = page.locator('.operator-color-palette[data-owner="text"]')
    palette.wait_for(state="visible", timeout=5_000)
    palette.locator('[title="#c00000"]').click()
    page.wait_for_timeout(350)

    assert_formatting(formatting_snapshot(page), "sequential formatting")

    page.evaluate(
        """() => {
            const table = window.shiftHelperEventGrid;
            const row = table.getRows('visible')[0];
            row.reformat();
            table.redraw(true);
            window.shiftHelperZoom?.apply?.(110, false);
            window.shiftHelperZoom?.apply?.(100, false);
        }"""
    )
    page.wait_for_timeout(500)
    target = cell(visible_rows(page).first, "description")
    target.click()
    page.wait_for_timeout(180)
    assert_formatting(formatting_snapshot(page), "reformat, redraw and zoom")


def run(url: str, screenshot: Path) -> None:
    browser_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
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
            test_row_drag_integrity(page)
            test_composite_formatting(page)
            require(not browser_errors, "Browser errors: " + " | ".join(browser_errors))
        except Exception:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(screenshot), full_page=False, timeout=5_000)
            except Exception as screenshot_error:  # pragma: no cover
                print(f"Diagnostic screenshot failed: {screenshot_error}", file=sys.stderr)
            print(
                "manual rejection diagnostic="
                + json.dumps(
                    page.evaluate(
                        """() => ({
                            dataset: {...document.getElementById('event-journal').dataset},
                            selected: [...(window.shiftHelperSelectedRowKeys || [])],
                            ranges: window.shiftHelperEventGrid.getRanges?.().length || 0,
                            preferences: localStorage.getItem('shift-helper-ui-preferences-v1'),
                        })"""
                    ),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            raise
        finally:
            context.close()
            browser.close()


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: ui_smoke_manual_rejection.py <base-url> [screenshot-path]")
    screenshot = Path(
        sys.argv[2] if len(sys.argv) == 3 else "ui-manual-rejection-failure.png"
    )
    run(sys.argv[1], screenshot)
    print("Shift-Helper 2026-07-29 manual-rejection regressions passed.")


if __name__ == "__main__":
    main()
