"use strict";

(() => {
    const table = window.shiftHelperEventGrid;
    if (!table) {
        return;
    }

    function releaseSelection(row) {
        const element = row.getElement?.();
        const isSelected = element?.classList?.contains("journal-row--selected")
            || window.shiftHelperSelectedRowKey === row.getData()._rowKey;
        if (!isSelected) {
            return;
        }

        const replacement = table.getRows().find((candidate) => (
            candidate !== row
            && candidate.getElement?.()?.isConnected
        ));
        const replacementCell = replacement?.getCell("start_date")?.getElement?.();
        if (replacementCell) {
            replacementCell.dispatchEvent(new MouseEvent("click", {
                bubbles: true,
                cancelable: true,
                view: window,
            }));
        }
        window.shiftHelperSelectedRowKey = null;
    }

    function patchRow(row) {
        if (!row || row.__shiftHelperDeleteGuard) {
            return;
        }
        Object.defineProperty(row, "__shiftHelperDeleteGuard", {value: true});
        const originalDelete = row.delete.bind(row);
        row.delete = (...args) => {
            releaseSelection(row);
            return originalDelete(...args);
        };
    }

    function patchAllRows() {
        table.getRows().forEach(patchRow);
    }

    patchAllRows();
    table.on("tableBuilt", patchAllRows);
    table.on("renderComplete", patchAllRows);
    table.on("rowAdded", patchRow);
})();
