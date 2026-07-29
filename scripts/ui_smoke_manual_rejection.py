"""Regressions derived from the 2026-07-29 manual Windows rejection video."""

from __future__ import annotations

import json
import re
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
                && root.dataset.rowNumberContract === 'ready'
                && root.dataset.stage4AlignmentContract === 'ready'
                && root.dataset.acceptanceStage6 === 'ready'
                && root.dataset.printDraftContract === 'ready'
                && Boolean(window.shiftHelperFormattingContract)
                && Boolean(window.shiftHelperAcceptanceStage6);
        }""",
        timeout=20_000,
    )


def visible_rows(page: Page):
    return page.locator(".tabulator-row:visible")


def cell(row, field: str):
    return row.locator(f'.tabulator-cell[tabulator-field="{field}"]')


def row_visual_diagnostic(page: Page, limit: int = 12) -> dict:
    return page.evaluate(
        """limit => {
            const root = document.getElementById('event-journal');
            const table = window.shiftHelperEventGrid;
            const rows = table.getRows('active');
            const rendered = rows.map((row, index) => {
                const element = row.getElement?.();
                if (!(element instanceof Element) || !element.isConnected) return null;
                const number = element.querySelector('.journal-row-number');
                const rect = element.getBoundingClientRect();
                return {
                    key: row.getData()._rowKey,
                    expected: String(index + 1),
                    number: number?.textContent?.trim() || '',
                    top: rect.top,
                    bottom: rect.bottom,
                    height: rect.height,
                    selected: element.classList.contains('journal-row--multi-selected'),
                    cellCount: element.querySelectorAll('.tabulator-cell').length,
                };
            }).filter(Boolean).slice(0, limit);
            return {
                mode: root.dataset.selectionMode,
                activeCount: rows.length,
                selected: [...(window.shiftHelperSelectedRowKeys || [])],
                contractSelected: window.shiftHelperSelectionModeContract?.rowKeys?.() || [],
                ranges: table.getRanges?.().length || 0,
                rendered,
            };
        }""",
        limit,
    )


def assert_contiguous_rows(diagnostic: dict, stage: str) -> None:
    rows = diagnostic["rendered"]
    require(rows, f"No rendered active rows after {stage}: {diagnostic}")
    for row in rows:
        require(
            row["number"] == row["expected"],
            f"Visible row numbering diverged after {stage}: {diagnostic}",
        )
        require(
            row["height"] > 20 and row["cellCount"] >= 10,
            f"A rendered row collapsed after {stage}: {diagnostic}",
        )
    for previous, current in zip(rows, rows[1:], strict=False):
        require(
            abs(current["top"] - previous["bottom"]) <= 2,
            f"A physical blank gap remained after {stage}: {diagnostic}",
        )


def test_row_drag_integrity(page: Page) -> None:
    rows = visible_rows(page)
    require(rows.count() >= 8, "Not enough visible rows for row-drag regression.")

    cell(rows.nth(3), "description").click()
    page.wait_for_timeout(120)
    require(
        page.locator(".tabulator-range-active, .tabulator-range-selected").count() > 0,
        "The active cell precondition was not established.",
    )

    start = rows.nth(0).locator(".journal-row-number")
    end = rows.nth(6).locator(".journal-row-number")
    start_box = start.bounding_box()
    end_box = end.bounding_box()
    require(start_box is not None and end_box is not None, "Row-drag geometry is unavailable.")

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
    page.wait_for_timeout(350)

    diagnostic = row_visual_diagnostic(page, 7)
    require(diagnostic["mode"] == "rows", f"Row mode was not entered: {diagnostic}")
    require(
        len(diagnostic["selected"]) == 7
        and diagnostic["selected"] == diagnostic["contractSelected"],
        f"Logical and visual row selection diverged: {diagnostic}",
    )
    require(diagnostic["ranges"] == 0, f"A stale cell range survived row mode: {diagnostic}")
    require(
        len(diagnostic["rendered"]) == 7
        and all(row["selected"] for row in diagnostic["rendered"]),
        f"The dragged row block is not contiguous: {diagnostic}",
    )
    assert_contiguous_rows(diagnostic, "row drag")


def select_draft_row(page: Page) -> dict:
    return page.evaluate(
        """async () => {
            const table = window.shiftHelperEventGrid;
            const row = table.getRows('active').find(candidate => candidate.getData()._draft);
            if (!row) throw new Error('No draft row is available for delete regression');
            await table.scrollToRow(row, 'center', false);
            const number = row.getElement()?.querySelector('.journal-row-number');
            if (!number) throw new Error('Draft row number is not rendered');
            number.dispatchEvent(new PointerEvent('pointerdown', {
                bubbles: true,
                cancelable: true,
                composed: true,
                button: 0,
                buttons: 1,
            }));
            number.dispatchEvent(new PointerEvent('pointerup', {
                bubbles: true,
                cancelable: true,
                composed: true,
                button: 0,
                buttons: 0,
            }));
            return {
                key: row.getData()._rowKey,
                activeCount: table.getRows('active').length,
            };
        }"""
    )


def test_delete_renumbers_rows(page: Page) -> None:
    target = select_draft_row(page)
    page.wait_for_function(
        """key => document.getElementById('event-journal').dataset.selectionMode === 'rows'
            && (window.shiftHelperSelectedRowKeys || []).includes(key)""",
        arg=target["key"],
        timeout=5_000,
    )

    page.keyboard.press("Delete")
    page.wait_for_function(
        """target => {
            const rows = window.shiftHelperEventGrid.getRows('active');
            return rows.length === target.activeCount - 1
                && !rows.some(row => row.getData()._rowKey === target.key);
        }""",
        arg=target,
        timeout=10_000,
    )
    page.wait_for_timeout(250)
    assert_contiguous_rows(row_visual_diagnostic(page), "row deletion")

    page.keyboard.press("Control+z")
    page.wait_for_function(
        """target => {
            const rows = window.shiftHelperEventGrid.getRows('active');
            return rows.length === target.activeCount
                && rows.some(row => row.getData()._rowKey === target.key);
        }""",
        arg=target,
        timeout=10_000,
    )
    page.wait_for_timeout(300)
    assert_contiguous_rows(row_visual_diagnostic(page), "undo row deletion")


def formatting_snapshot(page: Page) -> dict:
    return page.evaluate(
        """() => {
            const root = document.getElementById('event-journal');
            const holder = root.querySelector('.tabulator-tableholder');
            const holderRect = holder.getBoundingClientRect();
            const rowElement = [...root.querySelectorAll('.tabulator-row')].find(row => {
                const rect = row.getBoundingClientRect();
                const style = getComputedStyle(row);
                return rect.bottom > holderRect.top
                    && rect.top < holderRect.bottom
                    && style.display !== 'none'
                    && style.visibility !== 'hidden';
            });
            const target = rowElement?.querySelector(
                '.tabulator-cell[tabulator-field="description"]'
            );
            const value = target?.querySelector('.journal-cell-value');
            const row = window.shiftHelperEventGrid.getRows('visible').find(
                candidate => candidate.getElement() === rowElement
            );
            const component = row?.getCell('description');
            const rowKey = component?.getRow().getData()._rowKey;
            const read = key => JSON.parse(localStorage.getItem(key) || '{}');
            const style = value ? getComputedStyle(value) : null;
            const cellStyle = target ? getComputedStyle(target) : null;
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
    require(
        text.get("color", "").lower() == "#c00000",
        f"Text color was lost after {stage}: {snapshot}",
    )
    require(
        alignment.get("horizontal") == "right",
        f"Alignment was lost after {stage}: {snapshot}",
    )
    require((fill or "").lower() == "#fff2cc", f"Fill was lost after {stage}: {snapshot}")
    require(snapshot["fontWeight"] in {"700", "bold"}, f"Bold is not rendered: {snapshot}")
    require(snapshot["fontStyle"] == "italic", f"Italic is not rendered: {snapshot}")
    require(snapshot["color"] == "rgb(192, 0, 0)", f"Text color is not rendered: {snapshot}")
    require(
        snapshot["background"] == "rgb(255, 242, 204)",
        f"Fill is not rendered: {snapshot}",
    )
    require(
        snapshot["textAlign"] == "right" and snapshot["cellTextAlign"] == "right",
        f"Alignment is not rendered after {stage}: {snapshot}",
    )
    require(snapshot["horizontal"] == "right", f"Alignment metadata diverged: {snapshot}")
    require(
        snapshot["boldActive"] and snapshot["italicActive"] and snapshot["rightActive"],
        f"Ribbon state diverged after {stage}: {snapshot}",
    )


def test_composite_formatting(page: Page) -> None:
    target = cell(visible_rows(page).first, "description")
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
    cell(visible_rows(page).first, "description").click()
    page.wait_for_timeout(180)
    assert_formatting(formatting_snapshot(page), "reformat, redraw and zoom")


def test_preview_includes_incomplete_draft(page: Page) -> None:
    marker = "Незавершённая запись для предпросмотра 2026-07-29"
    draft = page.evaluate(
        """marker => {
            const table = window.shiftHelperEventGrid;
            const fields = [
                'asset_label', 'description', 'reason', 'actions', 'performer',
                'end_date', 'end_time', 'author'
            ];
            const row = table.getRows('active').find(candidate => {
                const data = candidate.getData();
                return data._draft && fields.every(field => !String(data[field] || '').trim());
            });
            if (!row) throw new Error('No blank draft row is available for print regression');
            row.getCell('description').setValue(marker, true);
            return {
                key: row.getData()._rowKey,
                draft: row.getData()._draft,
                description: row.getData().description,
            };
        }""",
        marker,
    )
    require(draft["draft"] is True and draft["description"] == marker, f"Draft setup failed: {draft}")
    page.wait_for_timeout(250)
    require(
        page.evaluate(
            """key => window.shiftHelperEventGrid.getRow(key)?.getData()._draft === true""",
            draft["key"],
        ),
        "The incomplete row unexpectedly became a persisted record before preview.",
    )

    page.evaluate("() => window.shiftHelperAcceptanceStage6.openPreview()")
    preview = page.locator("#stage6-preview-dialog")
    preview.wait_for(state="visible", timeout=5_000)
    page_text = page.locator("#stage6-preview-page").inner_text()
    require(marker in page_text, f"Entered draft data is absent from print preview: {page_text}")
    require("Нет записей для печати" not in page_text, f"Preview still reports no data: {page_text}")
    require(
        page.locator("#stage6-preview-page tbody tr").count() >= 1,
        "Print preview did not render any data rows.",
    )
    footer = page.locator("#stage6-preview-page .stage6-print-footer").inner_text()
    match = re.search(r"Записей:\s*(\d+)", footer)
    require(match is not None and int(match.group(1)) >= 1, f"Invalid preview counter: {footer}")
    page.locator("#stage6-preview-close").click()
    preview.wait_for(state="hidden", timeout=5_000)


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
            test_delete_renumbers_rows(page)
            test_composite_formatting(page)
            test_preview_includes_incomplete_draft(page)
            require(not browser_errors, "Browser errors: " + " | ".join(browser_errors))
        except Exception:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(screenshot), full_page=False, timeout=5_000)
            except Exception as screenshot_error:  # pragma: no cover
                print(f"Diagnostic screenshot failed: {screenshot_error}", file=sys.stderr)
            try:
                diagnostic = page.evaluate(
                    """() => {
                        const root = document.getElementById('event-journal');
                        const table = window.shiftHelperEventGrid;
                        return {
                            url: location.href,
                            dataset: root ? {...root.dataset} : null,
                            selected: [...(window.shiftHelperSelectedRowKeys || [])],
                            ranges: table?.getRanges?.().length || 0,
                            printRows: window.shiftHelperAcceptanceStage6?.meaningfulRows?.()
                                .map(row => row.getData()._rowKey) || [],
                        };
                    }"""
                )
                print(
                    "manual rejection diagnostic="
                    + json.dumps(diagnostic, ensure_ascii=False, sort_keys=True),
                    file=sys.stderr,
                )
            except Exception as diagnostic_error:  # pragma: no cover
                print(f"Browser diagnostic failed: {diagnostic_error}", file=sys.stderr)
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
