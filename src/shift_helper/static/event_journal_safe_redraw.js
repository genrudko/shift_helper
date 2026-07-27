"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;

    if (!root || !table || typeof table.redraw !== "function") {
        return;
    }

    const originalRedraw = table.redraw.bind(table);
    const originalGetRows = table.getRows.bind(table);
    let ready = Boolean(root.querySelector(".tabulator-tableholder"));
    let pending = false;
    let pendingForce = false;

    function internalElementReady() {
        return Boolean(
            root.isConnected
            && root.querySelector(".tabulator-tableholder")
            && root.querySelector(".tabulator-table"),
        );
    }

    function flushPending() {
        if (!pending || !ready || !internalElementReady()) {
            return;
        }
        const force = pendingForce;
        pending = false;
        pendingForce = false;
        window.requestAnimationFrame(() => {
            if (!internalElementReady()) {
                pending = true;
                pendingForce ||= force;
                return;
            }
            originalRedraw(force);
        });
    }

    table.getRows = (range) => {
        if (range === "visible" && (!ready || !internalElementReady())) {
            return [];
        }
        try {
            return originalGetRows(range);
        } catch (error) {
            if (range === "visible" && /visibleRows/.test(String(error))) {
                return [];
            }
            throw error;
        }
    };

    table.redraw = (force = false) => {
        if (!ready || !internalElementReady()) {
            pending = true;
            pendingForce ||= Boolean(force);
            return undefined;
        }
        return originalRedraw(force);
    };

    table.on("tableBuilt", () => {
        ready = true;
        pending = true;
        flushPending();
    });
    table.on("renderComplete", () => {
        ready = true;
        flushPending();
    });

    if (ready) {
        window.requestAnimationFrame(() => {
            pending = true;
            flushPending();
        });
    }

    if (!document.querySelector('script[data-shift-helper-frozen-columns="v5"]')) {
        const script = document.createElement("script");
        script.src = "/static/event_journal_frozen_columns_v5.js";
        script.defer = true;
        script.dataset.shiftHelperFrozenColumns = "v5";
        document.head.appendChild(script);
    }

    if (!document.querySelector('script[data-shift-helper-editor-caret="v5"]')) {
        const script = document.createElement("script");
        script.src = "/static/event_journal_editor_caret_v5.js";
        script.defer = true;
        script.dataset.shiftHelperEditorCaret = "v5";
        document.head.appendChild(script);
    }
})();
