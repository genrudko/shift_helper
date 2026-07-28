"use strict";

/* Keep row, column and cell selection visuals mutually exclusive. */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table || root.dataset.selectionModeContract === "ready") return;

    let frame = 0;

    function clearCellVisuals() {
        root.querySelectorAll(".journal-active-cell").forEach((element) => {
            element.classList.remove("journal-active-cell");
        });
        document.querySelectorAll(".journal-fill-handle").forEach((handle) => {
            handle.hidden = true;
        });
    }

    function settleNonCellMode(mode) {
        root.dataset.selectionMode = mode;
        clearCellVisuals();
        queueMicrotask(clearCellVisuals);
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(clearCellVisuals);
    }

    window.addEventListener("pointerdown", (event) => {
        if (!(event.target instanceof Element) || event.button !== 0) return;
        if (event.target.closest(
            ".tabulator-col-sorter, .tabulator-header-filter, "
            + ".tabulator-col-resize-handle, input, select, textarea",
        )) return;
        const header = event.target.closest(
            ".tabulator-col[tabulator-field], .tabulator-col[data-field]",
        );
        if (header && root.contains(header)) {
            settleNonCellMode("columns");
            return;
        }
        const rowNumber = event.target.closest(".journal-row-number");
        if (rowNumber && root.contains(rowNumber)) settleNonCellMode("rows");
    }, true);

    table.on("rangeChanged", () => {
        if (["rows", "columns"].includes(root.dataset.selectionMode)) {
            settleNonCellMode(root.dataset.selectionMode);
        }
    });
    table.on("cellClick", () => {
        cancelAnimationFrame(frame);
        root.dataset.selectionMode = "cells";
    });

    window.shiftHelperSelectionModeContract = {
        clearCellVisuals,
        settleNonCellMode,
    };
    root.dataset.selectionModeContract = "ready";
})();
