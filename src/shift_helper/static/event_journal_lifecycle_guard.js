"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;

    if (!root || !table) {
        return;
    }

    let clearing = false;
    let redrawScheduled = false;

    function safeRemoveRange(range) {
        try {
            range.remove();
        } catch (_error) {
            // The range may already reference a row removed by Tabulator.
        }
    }

    function scheduleRedraw() {
        if (redrawScheduled) {
            return;
        }
        redrawScheduled = true;
        window.requestAnimationFrame(() => {
            redrawScheduled = false;
            try {
                table.redraw(true);
            } catch (_error) {
                // A second render cycle will follow after the row mutation completes.
            }
        });
    }

    function clearTransientGridState() {
        if (clearing) {
            return;
        }
        clearing = true;
        try {
            const active = document.activeElement;
            if (
                active instanceof HTMLInputElement
                || active instanceof HTMLTextAreaElement
                || active instanceof HTMLSelectElement
            ) {
                active.blur();
            }

            for (const range of table.getRanges?.() || []) {
                safeRemoveRange(range);
            }

            root.querySelectorAll(".tabulator-editing").forEach((element) => {
                element.classList.remove("tabulator-editing");
            });
            document.querySelectorAll(".journal-fill-handle").forEach((handle) => {
                handle.hidden = true;
            });
        } finally {
            clearing = false;
        }
        scheduleRedraw();
    }

    function patchRow(row) {
        if (!row || row.__shiftHelperLifecycleGuard) {
            return;
        }
        Object.defineProperty(row, "__shiftHelperLifecycleGuard", {value: true});
        const originalDelete = row.delete.bind(row);
        row.delete = async (...args) => {
            clearTransientGridState();
            await new Promise((resolve) => window.requestAnimationFrame(resolve));
            const result = await originalDelete(...args);
            scheduleRedraw();
            return result;
        };
    }

    table.getRows().forEach(patchRow);
    table.on("rowAdded", (row) => {
        patchRow(row);
        scheduleRedraw();
    });
    table.on("renderComplete", () => {
        table.getRows().forEach(patchRow);
    });

    window.shiftHelperClearTransientGridState = clearTransientGridState;
})();
