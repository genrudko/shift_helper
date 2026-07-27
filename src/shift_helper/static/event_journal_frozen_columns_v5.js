"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const select = document.getElementById("journal-frozen-through");

    if (!root || !table || !select || typeof table.updateColumnDefinition !== "function") {
        return;
    }

    const preferenceKey = "shift-helper-ui-preferences-v1";
    const defaultBoundary = "asset_label";
    let applying = false;
    let queuedBoundary = null;

    function readPreferences() {
        try {
            return JSON.parse(window.localStorage.getItem(preferenceKey) || "{}");
        } catch (_error) {
            return {};
        }
    }

    function saveBoundary(boundary) {
        const preferences = readPreferences();
        preferences.frozenThrough = boundary;
        window.localStorage.setItem(preferenceKey, JSON.stringify(preferences));
    }

    function orderedFields() {
        return table.getColumns()
            .map((column) => column.getField())
            .filter(Boolean);
    }

    function expectedFields(boundary) {
        const fields = orderedFields();
        if (boundary === "none") {
            return new Set();
        }
        const index = fields.indexOf(boundary);
        if (index < 0 || index === fields.length - 1) {
            return index === fields.length - 1 ? new Set() : new Set(
                fields.slice(0, fields.indexOf(defaultBoundary) + 1),
            );
        }
        return new Set(fields.slice(0, index + 1));
    }

    function clearTransientState() {
        window.shiftHelperClearTransientGridState?.();
        for (const range of table.getRanges?.() || []) {
            try {
                range.remove();
            } catch (_error) {
                // A stale selection must not block a view-setting change.
            }
        }
        document.querySelectorAll(".journal-fill-handle").forEach((handle) => {
            handle.hidden = true;
        });
    }

    async function applyBoundary(boundary) {
        if (applying) {
            queuedBoundary = boundary;
            return;
        }
        applying = true;
        clearTransientState();
        try {
            const expected = expectedFields(boundary);
            for (const field of orderedFields()) {
                const column = table.getColumn(field);
                if (!column) {
                    continue;
                }
                const frozen = expected.has(field);
                if (Boolean(column.getDefinition().frozen) !== frozen) {
                    await table.updateColumnDefinition(field, {frozen});
                }
            }
            saveBoundary(boundary);
            table.redraw(true);
        } finally {
            applying = false;
            if (queuedBoundary !== null) {
                const next = queuedBoundary;
                queuedBoundary = null;
                await applyBoundary(next);
            }
        }
    }

    select.addEventListener("change", (event) => {
        event.stopImmediatePropagation();
        void applyBoundary(event.target.value);
    }, true);

    document.getElementById("reset-view-settings")?.addEventListener("click", () => {
        window.setTimeout(() => {
            select.value = defaultBoundary;
            void applyBoundary(defaultBoundary);
        }, 0);
    }, true);

    function applyStoredBoundary() {
        const boundary = readPreferences().frozenThrough || defaultBoundary;
        select.value = boundary;
        void applyBoundary(boundary);
    }

    table.on("tableBuilt", applyStoredBoundary);
    if (root.querySelector(".tabulator-tableholder")) {
        window.requestAnimationFrame(applyStoredBoundary);
    }
})();
