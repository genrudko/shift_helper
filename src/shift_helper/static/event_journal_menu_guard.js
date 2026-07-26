"use strict";

(() => {
    const table = window.shiftHelperEventGrid;
    if (!table?.options) {
        return;
    }

    // Row-number context menus are handled by event_journal_row_context.js.
    // Disable the obsolete Tabulator row callback whose callback signature
    // differs between the row and menu modules and otherwise raises a late
    // `row.getData is not a function` page error after the menu has worked.
    table.options.rowContextMenu = false;
})();
