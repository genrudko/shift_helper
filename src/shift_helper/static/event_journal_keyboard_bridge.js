"use strict";

(() => {
    const table = window.shiftHelperEventGrid;
    const root = document.getElementById("event-journal");
    if (!table || !root) {
        return;
    }

    const editableFields = new Set([
        "start_date",
        "start_time",
        "asset_label",
        "description",
        "reason",
        "actions",
        "performer",
        "end_date",
        "end_time",
        "author",
    ]);
    let activeCell = null;
    root.dataset.keyboardBridge = "ready";

    table.on("cellClick", (_event, cell) => {
        activeCell = cell;
    });
    table.on("rangeChanged", (range) => {
        const bounds = range.getBounds?.();
        activeCell = bounds?.end || bounds?.bottomRight || activeCell;
    });

    function cellFromSelectedElement() {
        const element = root.querySelector(
            ".tabulator-cell.tabulator-range-active, "
            + ".tabulator-cell.tabulator-range-selected, "
            + ".tabulator-cell[aria-selected='true']"
        );
        if (!element) {
            return null;
        }
        for (const row of table.getRows("active")) {
            for (const cell of row.getCells()) {
                if (cell.getElement() === element) {
                    return cell;
                }
            }
        }
        return null;
    }

    function currentCell() {
        return cellFromSelectedElement() || activeCell;
    }

    function seedEditor(cell, value) {
        const apply = () => {
            const editor = cell.getElement().querySelector(".journal-excel-editor");
            if (!(editor instanceof HTMLInputElement || editor instanceof HTMLTextAreaElement)) {
                return false;
            }
            editor.value = value;
            editor.dispatchEvent(new Event("input", {bubbles: true}));
            editor.setSelectionRange(value.length, value.length);
            return true;
        };

        if (!apply()) {
            window.requestAnimationFrame(apply);
        }
    }

    document.addEventListener("keydown", (event) => {
        const target = event.target;
        if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
            return;
        }
        const cell = currentCell();
        if (!cell || !editableFields.has(cell.getField())) {
            return;
        }
        const modifier = event.ctrlKey || event.metaKey || event.altKey;
        if (event.key === "Enter" || event.key === "F2") {
            event.preventDefault();
            event.stopImmediatePropagation();
            cell.edit();
            return;
        }
        if (event.key.length === 1 && !modifier) {
            event.preventDefault();
            event.stopImmediatePropagation();
            cell.edit();
            seedEditor(cell, event.key);
        }
    }, true);
})();
