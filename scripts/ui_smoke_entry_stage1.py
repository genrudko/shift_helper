"""Run the full legacy smoke with Stage 1 geometry readiness."""

from __future__ import annotations  # noqa: I001

import runpy
from pathlib import Path

from playwright.sync_api import Page, TimeoutError

BASE_SCRIPT = Path(__file__).with_name("ui_smoke_entry_video.py")
BASE = runpy.run_path(str(BASE_SCRIPT), run_name="shift_helper_ui_smoke_stage1_base")
ENTRY = BASE["ENTRY"]
ORIGINAL_VIEWPORT_TEST = BASE["ORIGINAL_VIEWPORT_TEST"]
TEST_OPERATOR_REPAIRS = BASE["test_operator_repairs"]
ORIGINAL_SCREENSHOT = Page.screenshot


def bounded_diagnostic_screenshot(self: Page, *args, **kwargs):
    """Do not let an infinite-sheet screenshot hide the primary smoke failure."""

    if kwargs.get("full_page"):
        kwargs["full_page"] = False
    kwargs.setdefault("timeout", 5_000)
    try:
        return ORIGINAL_SCREENSHOT(self, *args, **kwargs)
    except TimeoutError:
        return b""


def wait_for_stage1_geometry(page: Page) -> None:
    try:
        page.wait_for_function(
            """() => {
                const root = document.getElementById('event-journal');
                return root?.dataset.operatorRepairReady === 'true'
                    && root.dataset.videoAcceptanceRepair === 'ready'
                    && root.dataset.acceptanceStage1 === 'ready'
                    && root.dataset.zoomApplying !== 'true'
                    && Boolean(window.shiftHelperAcceptanceStage1);
            }""",
            timeout=20_000,
        )
    except TimeoutError as exc:
        diagnostic = page.evaluate(
            """() => {
                const root = document.getElementById('event-journal');
                return JSON.stringify({
                    dataset: root ? {...root.dataset} : null,
                    hasStage1Api: Boolean(window.shiftHelperAcceptanceStage1),
                    hasZoomApi: Boolean(window.shiftHelperZoom),
                    preferences: localStorage.getItem('shift-helper-ui-preferences-v1'),
                    legacyZoom: localStorage.getItem('shift-helper-operator-zoom-v1'),
                    ribbonZoom: document.getElementById('ribbon-zoom')?.value ?? null,
                    customSlider: Boolean(document.getElementById('acceptance-ribbon-zoom')),
                });
            }"""
        )
        raise AssertionError(f"Stage 1 readiness timed out: {diagnostic}") from exc


Page.screenshot = bounded_diagnostic_screenshot
TEST_OPERATOR_REPAIRS.__globals__["wait_for_complete_view"] = wait_for_stage1_geometry
ORIGINAL_VIEWPORT_TEST.__globals__["wait_for_operator_repair"] = wait_for_stage1_geometry


if __name__ == "__main__":
    ENTRY["main"]()
