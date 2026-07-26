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

    table.on("cellClick", (_event, cell) => {
        activeCell = cell;
    });
    table.on("rangeChanged", (range) => {
        activeCell = range.getBounds?.().end || activeCell;
    });

    function currentCell() {
        const ranges = table.getRanges?.() || [];
        return ranges.at(-1)?.getBounds?.().end || activeCell;
    }

    function replaceEditorValue(cell, value) {
        window.setTimeout(() => {
            const editor = cell.getElement().querySelector(".journal-excel-editor");
            if (!(editor instanceof HTMLInputElement || editor instanceof HTMLTextAreaElement)) {
                return;
            }
            editor.value = value;
            editor.dispatchEvent(new Event("input", {bubbles: true}));
            editor.setSelectionRange(value.length, value.length);
        }, 0);
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
            replaceEditorValue(cell, event.key);
        }
    }, true);
})();
