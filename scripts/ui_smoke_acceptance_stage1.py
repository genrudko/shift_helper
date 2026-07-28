"""Focused acceptance checks for zoom linearity and row selection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import Page, TimeoutError, sync_playwright


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def wait_ready(page: Page) -> None:
    page.wait_for_function(
        """() => {
            const root = document.getElementById('event-journal');
            return root?.dataset.acceptanceStage1 === 'ready'
                && root.dataset.zoomApplying !== 'true'
                && Boolean(window.shiftHelperAcceptanceStage1);
        }""",
        timeout=20_000,
    )


def set_zoom(page: Page, value: int) -> None:
    page.evaluate("value => window.shiftHelperAcceptanceStage1.setZoom(value)", value)
    try:
        page.wait_for_function(
            """value => {
                const root = document.getElementById('event-journal');
                return root?.dataset.sheetZoom === String(value)
                    && root.dataset.zoomApplying !== 'true';
            }""",
            arg=value,
            timeout=10_000,
        )
    except TimeoutError as exc:
        diagnostic = page.evaluate(
            """expected => {
                const root = document.getElementById('event-journal');
                const fields = ['start_date', 'start_time', 'asset_label', 'description'];
                const customSlider = document.getElementById('acceptance-ribbon-zoom');
                return {
                    expected,
                    dataset: root ? {...root.dataset} : null,
                    nativeJournal: document.getElementById('journal-zoom')?.value ?? null,
                    nativeRibbon: document.getElementById('ribbon-zoom')?.value ?? null,
                    customZoom: customSlider?.dataset.zoom ?? null,
                    customPosition: customSlider?.dataset.position ?? null,
                    widths: Object.fromEntries(fields.map(field => [
                        field,
                        Number(window.shiftHelperEventGrid.getColumn(field)?.getWidth?.() || 0),
                    ])),
                    fontSize: getComputedStyle(document.documentElement)
                        .getPropertyValue('--journal-font-size').trim(),
                    rowHeight: getComputedStyle(document.documentElement)
                        .getPropertyValue('--journal-row-height').trim(),
                    preferences: localStorage.getItem('shift-helper-ui-preferences-v1'),
                    legacyZoom: localStorage.getItem('shift-helper-operator-zoom-v1'),
                };
            }""",
            value,
        )
        raise AssertionError(
            "Zoom application timed out: "
            + json.dumps(diagnostic, ensure_ascii=False, sort_keys=True)
        ) from exc


def zoom_metrics(page: Page) -> dict[str, float]:
    return page.evaluate(
        """() => {
            const fields = ['start_date', 'start_time', 'asset_label', 'description'];
            const result = {};
            for (const field of fields) {
                const column = window.shiftHelperEventGrid.getColumn(field);
                result[field] = Number(column?.getWidth?.() || 0);
            }
            result.fontSize = Number.parseFloat(
                getComputedStyle(document.documentElement)
                    .getPropertyValue('--journal-font-size')
            );
            result.rowHeight = Number.parseFloat(
                getComputedStyle(document.documentElement)
                    .getPropertyValue('--journal-row-height')
            );
            return result;
        }"""
    )


def assert_same_metrics(first: dict[str, float], second: dict[str, float]) -> None:
    require(first.keys() == second.keys(), "Zoom metric keys changed between equal zoom levels.")
    for key in first:
        require(
            abs(first[key] - second[key]) <= 1,
            f"125% geometry depends on the previous zoom path for {key}: "
            f"{first[key]} != {second[key]}",
        )


def selected_keys(page: Page) -> list[str]:
    return page.evaluate("() => [...(window.shiftHelperSelectedRowKeys || [])]")


def assert_row_mode(page: Page, expected_count: int, stage: str) -> None:
    root = page.locator("#event-journal")
    require(
        root.get_attribute("data-selection-mode") == "rows",
        f"Row mode was not active after {stage}.",
    )
    require(
        len(selected_keys(page)) == expected_count,
        f"Unexpected selected-row count after {stage}: {selected_keys(page)}",
    )
    require(
        page.locator(".journal-active-cell").count() == 0,
        f"An active cell remained over row selection after {stage}.",
    )
    require(
        page.locator(".journal-fill-handle:visible").count() == 0,
        f"The fill handle remained visible after {stage}.",
    )


def test_zoom_path(page: Page) -> None:
    slider = page.locator("#acceptance-ribbon-zoom")
    slider.wait_for(state="visible", timeout=10_000)

    set_zoom(page, 100)
    position = float(slider.get_attribute("data-position") or "-1")
    require(abs(position - 50) <= 0.5, f"100% is not centered on the zoom track: {position}%")

    set_zoom(page, 125)
    first_125 = zoom_metrics(page)
    set_zoom(page, 80)
    set_zoom(page, 125)
    second_125 = zoom_metrics(page)
    assert_same_metrics(first_125, second_125)

    set_zoom(page, 10)
    require(
        abs(float(slider.get_attribute("data-position") or "-1")) <= 0.5,
        "10% is not at the left end of the zoom track.",
    )
    set_zoom(page, 400)
    require(
        abs(float(slider.get_attribute("data-position") or "-1") - 100) <= 0.5,
        "400% is not at the right end of the zoom track.",
    )
    set_zoom(page, 100)


def test_row_selection(page: Page) -> None:
    holder = page.locator(".tabulator-tableholder")
    holder.evaluate("element => { element.scrollTop = 0; element.scrollLeft = 0; }")
    page.wait_for_timeout(250)

    headers = page.locator(".tabulator-row:visible .journal-row-number")
    require(headers.count() >= 6, "Too few visible row headers for acceptance checks.")

    first = headers.nth(0)
    second = headers.nth(1)
    third = headers.nth(2)
    fifth = headers.nth(4)

    first.click()
    page.wait_for_timeout(100)
    assert_row_mode(page, 1, "plain row click")

    third.click(modifiers=["Control"])
    page.wait_for_timeout(100)
    assert_row_mode(page, 2, "Ctrl row click")

    fifth.click(modifiers=["Shift"])
    page.wait_for_timeout(100)
    assert_row_mode(page, 3, "Shift range selection")

    second.click()
    page.wait_for_timeout(100)
    assert_row_mode(page, 1, "selection reset by plain click")

    start = second.bounding_box()
    end = fifth.bounding_box()
    require(start is not None and end is not None, "Row-header geometry is unavailable.")
    page.mouse.move(start["x"] + start["width"] / 2, start["y"] + start["height"] / 2)
    page.mouse.down()
    page.mouse.move(
        end["x"] + end["width"] / 2,
        end["y"] + end["height"] / 2,
        steps=8,
    )
    page.mouse.up()
    page.wait_for_timeout(150)
    assert_row_mode(page, 4, "row-header drag")

    cell = page.locator(
        '.tabulator-row:visible .tabulator-cell[tabulator-field="asset_label"]'
    ).nth(1)
    cell.click()
    page.wait_for_timeout(100)
    require(not selected_keys(page), "A cell click did not clear row selection.")
    require(
        page.locator("#event-journal").get_attribute("data-selection-mode") == "cells",
        "A cell click did not restore cell-selection mode.",
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
            test_zoom_path(page)
            test_row_selection(page)
            require(not browser_errors, "Browser errors: " + " | ".join(browser_errors))
        except Exception:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot), full_page=True)
            raise
        finally:
            context.close()
            browser.close()


def main() -> None:
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: ui_smoke_acceptance_stage1.py <base-url> [screenshot-path]")
    screenshot = Path(sys.argv[2] if len(sys.argv) == 3 else "ui-stage1-failure.png")
    run(sys.argv[1], screenshot)
    print("Shift-Helper acceptance stage 1 smoke passed.")


if __name__ == "__main__":
    main()
