"use strict";

/*
 * One visual contract for mutually exclusive cell, row and column selection.
 * The history controller remains the data owner for selected row keys; this
 * contract clears stale Tabulator cell ranges before row mode and restores the
 * authoritative row classes after legacy render listeners have completed.
 */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table || root.dataset.selectionModeContract === "ready") return;

    let frame = 0;
    let snapshotFrame = 0;
    let clearingRanges = false;
    const authoritativeRowKeys = new Set(window.shiftHelperSelectedRowKeys || []);

    function rowKey(row) {
        return row?.getData?.()._rowKey || null;
    }

    function clearCellVisuals() {
        root.querySelectorAll(".journal-active-cell").forEach((element) => {
            element.classList.remove("journal-active-cell");
        });
        document.querySelectorAll(".journal-fill-handle").forEach((handle) => {
            handle.hidden = true;
        });
    }

    function clearCellRanges() {
        if (clearingRanges) return;
        clearingRanges = true;
        try {
            const selectRange = table.modules?.selectRange;
            if (typeof selectRange?.clearRanges === "function") {
                // The vendored Tabulator range component recreates a default
                // range when the last public RangeComponent is removed. The
                // module-level clear is the only operation that leaves row
                // mode with no active range and therefore no transparent row.
                selectRange.clearRanges();
                return;
            }
            for (const range of table.getRanges?.() || []) {
                try {
                    range.remove();
                } catch (_error) {
                    // A stale virtual range must not block a row-selection gesture.
                }
            }
        } finally {
            clearingRanges = false;
        }
    }

    function reconcileRows() {
        cancelAnimationFrame(frame);
        frame = 0;
        const available = new Set(table.getRows().map(rowKey).filter(Boolean));
        [...authoritativeRowKeys].forEach((key) => {
            if (!available.has(key)) authoritativeRowKeys.delete(key);
        });
        window.shiftHelperSelectedRowKeys = [...authoritativeRowKeys];
        table.getRows().forEach((row) => {
            const element = row.getElement?.();
            if (!(element instanceof Element)) return;
            const selected = authoritativeRowKeys.has(rowKey(row));
            element.classList.toggle("journal-row--multi-selected", selected);
            if (selected) element.style.setProperty("opacity", "1", "important");
            else element.style.removeProperty("opacity");
        });
        root.dataset.rowSelectionVisualCount = String(authoritativeRowKeys.size);
    }

    function scheduleRowReconcile() {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(reconcileRows);
    }

    function captureControllerSelection() {
        cancelAnimationFrame(snapshotFrame);
        snapshotFrame = requestAnimationFrame(() => {
            snapshotFrame = 0;
            authoritativeRowKeys.clear();
            (window.shiftHelperSelectedRowKeys || []).forEach((key) => {
                if (key) authoritativeRowKeys.add(key);
            });
            reconcileRows();
        });
    }

    function queueControllerSnapshot() {
        queueMicrotask(() => {
            authoritativeRowKeys.clear();
            (window.shiftHelperSelectedRowKeys || []).forEach((key) => {
                if (key) authoritativeRowKeys.add(key);
            });
            reconcileRows();
            captureControllerSelection();
        });
    }

    function settleNonCellMode(mode) {
        root.dataset.selectionMode = mode;
        clearCellVisuals();
        queueMicrotask(() => {
            clearCellVisuals();
            if (mode === "rows") clearCellRanges();
        });
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
            clearCellVisuals();
            if (mode === "rows") {
                clearCellRanges();
                reconcileRows();
            }
        });
    }

    function beginRowMode() {
        clearCellRanges();
        settleNonCellMode("rows");
        queueControllerSnapshot();
    }

    window.addEventListener("pointerdown", (event) => {
        if (!(event.target instanceof Element)) return;
        if (event.target.closest(
            ".tabulator-col-sorter, .tabulator-header-filter, "
            + ".tabulator-col-resize-handle, input, select, textarea",
        )) return;

        const rowNumber = event.target.closest(".journal-row-number");
        if (rowNumber && root.contains(rowNumber) && event.button === 0) {
            beginRowMode();
            return;
        }

        const header = event.target.closest(
            ".tabulator-col[tabulator-field], .tabulator-col[data-field]",
        );
        if (header && root.contains(header) && event.button === 0) {
            authoritativeRowKeys.clear();
            settleNonCellMode("columns");
            return;
        }

        if (event.target.closest(".tabulator-cell") && root.contains(event.target)) {
            root.dataset.selectionMode = "cells";
            table.getRows().forEach((row) => row.getElement?.()?.style.removeProperty("opacity"));
            authoritativeRowKeys.clear();
            window.shiftHelperSelectedRowKeys = [];
            root.querySelectorAll(".journal-row--multi-selected").forEach((element) => {
                element.classList.remove("journal-row--multi-selected");
            });
        }
    }, true);

    window.addEventListener("contextmenu", (event) => {
        if (!(event.target instanceof Element)) return;
        const rowNumber = event.target.closest(".journal-row-number");
        if (rowNumber && root.contains(rowNumber)) beginRowMode();
    }, true);

    table.on("rangeChanged", () => {
        if (root.dataset.selectionMode === "rows" && authoritativeRowKeys.size) {
            clearCellRanges();
            settleNonCellMode("rows");
            scheduleRowReconcile();
        } else if (root.dataset.selectionMode === "columns") {
            settleNonCellMode("columns");
        }
    });

    table.on("renderComplete", scheduleRowReconcile);
    table.on("rowAdded", scheduleRowReconcile);
    table.on("rowDeleted", scheduleRowReconcile);
    table.on("cellClick", () => {
        cancelAnimationFrame(frame);
        authoritativeRowKeys.clear();
        root.dataset.selectionMode = "cells";
    });

    window.shiftHelperSelectionModeContract = {
        clearCellVisuals,
        clearCellRanges,
        reconcileRows,
        settleNonCellMode,
        rowKeys: () => [...authoritativeRowKeys],
    };
    reconcileRows();
    root.dataset.selectionModeContract = "ready";
})();
