"use strict";

/* Keep DOM alignment metadata synchronized with the authoritative alignment store. */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table || root.dataset.stage4AlignmentContract === "ready") return;

    const alignmentKey = "shift-helper-event-cell-alignment-v3";
    const defaults = {
        start_date: {horizontal: "center", vertical: "middle"},
        start_time: {horizontal: "center", vertical: "middle"},
        asset_label: {horizontal: "center", vertical: "middle"},
        description: {horizontal: "left", vertical: "top"},
        reason: {horizontal: "left", vertical: "top"},
        actions: {horizontal: "left", vertical: "top"},
        performer: {horizontal: "left", vertical: "middle"},
        end_date: {horizontal: "center", vertical: "middle"},
        end_time: {horizontal: "center", vertical: "middle"},
        author: {horizontal: "left", vertical: "middle"},
    };
    let frame = 0;

    function loadAlignment() {
        try {
            return JSON.parse(localStorage.getItem(alignmentKey) || "{}");
        } catch (_error) {
            return {};
        }
    }

    function applyContract() {
        frame = 0;
        const store = loadAlignment();
        table.getRows("active").forEach((row) => {
            const rowKey = row.getData()._rowKey;
            row.getCells().forEach((cell) => {
                const field = cell.getField();
                if (!field) return;
                const value = cell.getElement?.()?.querySelector(".journal-cell-value");
                if (!value) return;
                const alignment = store[rowKey]?.[field]
                    || defaults[field]
                    || {horizontal: "left", vertical: "middle"};
                value.dataset.horizontal = alignment.horizontal || "left";
                value.dataset.vertical = alignment.vertical || "middle";
            });
        });
    }

    function schedule() {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(applyContract);
    }

    table.on("renderComplete", schedule);
    table.on("rowUpdated", schedule);
    new MutationObserver(schedule).observe(root, {
        attributes: true,
        attributeFilter: ["style"],
        childList: true,
        subtree: true,
    });

    window.shiftHelperAcceptanceStage4Alignment = {apply: schedule};
    root.dataset.stage4AlignmentContract = "ready";
    schedule();
})();
