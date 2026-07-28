"""Run the full legacy smoke with Stage 1 geometry readiness."""

from __future__ import annotations  # noqa: I001

import runpy
from pathlib import Path

from playwright.sync_api import Page

BASE_SCRIPT = Path(__file__).with_name("ui_smoke_entry_video.py")
BASE = runpy.run_path(str(BASE_SCRIPT), run_name="shift_helper_ui_smoke_stage1_base")
ENTRY = BASE["ENTRY"]
ORIGINAL_VIEWPORT_TEST = BASE["ORIGINAL_VIEWPORT_TEST"]
TEST_OPERATOR_REPAIRS = BASE["test_operator_repairs"]


def wait_for_stage1_geometry(page: Page) -> None:
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


TEST_OPERATOR_REPAIRS.__globals__["wait_for_complete_view"] = wait_for_stage1_geometry
ORIGINAL_VIEWPORT_TEST.__globals__["wait_for_operator_repair"] = wait_for_stage1_geometry


if __name__ == "__main__":
    ENTRY["main"]()
