"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;

    if (!root || !table || typeof table.redraw !== "function") {
        return;
    }

    function rowNumberUnderPointer(event) {
        const pathMatch = event.composedPath?.().find(
            (item) => item instanceof Element && item.classList.contains("journal-row-number"),
        );
        if (pathMatch) {
            return pathMatch;
        }
        return document.elementsFromPoint(event.clientX, event.clientY)
            .find((item) => item instanceof Element && item.classList.contains("journal-row-number"))
            || null;
    }

    function preserveRowSelectionOnSecondaryPress(event) {
        if (event.button !== 2 || !rowNumberUnderPointer(event)) {
            return;
        }
        event.stopImmediatePropagation();
    }

    function normalizePointerLayers() {
        root.querySelectorAll(".tabulator-table").forEach((element) => {
            element.style.pointerEvents = "none";
        });
        root.querySelectorAll(".tabulator-row, .tabulator-cell").forEach((element) => {
            element.style.pointerEvents = "auto";
        });
    }

    document.addEventListener("pointerdown", preserveRowSelectionOnSecondaryPress, true);
    document.addEventListener("mousedown", preserveRowSelectionOnSecondaryPress, true);

    const originalRedraw = table.redraw.bind(table);
    const originalGetRows = table.getRows.bind(table);
    let ready = Boolean(root.querySelector(".tabulator-tableholder"));
    let bootstrapSettled = false;
    let bootstrapFrame = 0;
    let pending = false;
    let pendingForce = false;

    function internalElementReady() {
        return Boolean(
            root.isConnected
            && root.querySelector(".tabulator-tableholder")
            && root.querySelector(".tabulator-table"),
        );
    }

    function settleBootstrap() {
        window.cancelAnimationFrame(bootstrapFrame);
        bootstrapFrame = window.requestAnimationFrame(() => {
            bootstrapFrame = window.requestAnimationFrame(() => {
                bootstrapSettled = true;
                normalizePointerLayers();
                flushPending();
            });
        });
    }

    function flushPending() {
        if (!pending || !ready || !internalElementReady()) {
            return;
        }
        const force = bootstrapSettled && pendingForce;
        pending = false;
        pendingForce = false;
        window.requestAnimationFrame(() => {
            if (!internalElementReady()) {
                pending = true;
                pendingForce ||= force;
                return;
            }
            originalRedraw(force);
            normalizePointerLayers();
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
        const effectiveForce = bootstrapSettled && Boolean(force);
        const result = originalRedraw(effectiveForce);
        normalizePointerLayers();
        return result;
    };

    table.on("tableBuilt", () => {
        ready = true;
        pending = true;
        pendingForce = false;
        normalizePointerLayers();
        settleBootstrap();
        flushPending();
    });
    table.on("renderComplete", () => {
        ready = true;
        normalizePointerLayers();
        flushPending();
    });

    if (ready) {
        normalizePointerLayers();
        settleBootstrap();
        window.requestAnimationFrame(() => {
            pending = true;
            pendingForce = false;
            flushPending();
        });
    }
})();
