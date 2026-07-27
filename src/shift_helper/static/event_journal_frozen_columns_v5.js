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
    root.dataset.frozenColumnsController = "ready";

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

    function expectedFields(boundary, fields) {
        if (boundary === "none") {
            return new Set();
        }
        const index = fields.indexOf(boundary);
        if (index < 0) {
            const fallbackIndex = fields.indexOf(defaultBoundary);
            return new Set(fields.slice(0, fallbackIndex + 1));
        }
        if (index === fields.length - 1) {
            return new Set(fields.slice(0, -1));
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

    async function setFrozen(field, frozen) {
        const column = table.getColumn(field);
        if (!column || Boolean(column.getDefinition().frozen) === frozen) {
            return;
        }
        await table.updateColumnDefinition(field, {frozen});
    }

    async function applyBoundary(boundary) {
        if (applying) {
            queuedBoundary = boundary;
            return;
        }
        applying = true;
        root.dataset.frozenColumnsApplying = boundary;
        delete root.dataset.frozenColumnsApplied;
        clearTransientState();
        try {
            const fields = orderedFields();
            const expected = expectedFields(boundary, fields);

            for (const field of [...fields].reverse()) {
                if (!expected.has(field)) {
                    await setFrozen(field, false);
                }
            }
            for (const field of fields) {
                if (expected.has(field)) {
                    await setFrozen(field, true);
                }
            }

            saveBoundary(boundary);
            table.redraw(true);
            root.dataset.frozenColumnsApplied = boundary;
        } finally {
            delete root.dataset.frozenColumnsApplying;
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
