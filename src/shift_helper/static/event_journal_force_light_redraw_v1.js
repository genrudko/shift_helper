"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;

    if (
        !root
        || !table
        || typeof table.redraw !== "function"
        || root.dataset.forceLightRedraw === "ready"
    ) {
        return;
    }

    const redraw = table.redraw.bind(table);
    table.redraw = () => redraw(false);
    root.dataset.forceLightRedraw = "ready";
})();
