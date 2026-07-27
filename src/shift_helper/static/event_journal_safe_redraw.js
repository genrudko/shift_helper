"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;

    if (!root || !table || typeof table.redraw !== "function") {
        return;
    }

    const detachedCellElement = document.createElement("span");

    function protectDestroyedCellComponents() {
        const sample = table.getRows()?.[0]?.getCells?.()?.[0];
        const prototype = sample ? Object.getPrototypeOf(sample) : null;
        if (!prototype || prototype.__shiftHelperSafeElement === true) {
            return;
        }
        const originalGetElement = prototype.getElement;
        if (typeof originalGetElement !== "function") {
            return;
        }
        Object.defineProperty(prototype, "__shiftHelperSafeElement", {
            configurable: false,
            enumerable: false,
            value: true,
            writable: false,
        });
        prototype.getElement = function getElement() {
            const element = originalGetElement.call(this);
            return element && typeof element.getBoundingClientRect === "function"
                ? element
                : detachedCellElement;
        };
    }

    function loadContextFallback() {
        if (document.getElementById("event-journal-context-fallback-v1")) {
            return;
        }
        const script = document.createElement("script");
        script.id = "event-journal-context-fallback-v1";
        script.src = "/static/event_journal_context_fallback_v1.js";
        document.body.appendChild(script);
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

    document.addEventListener("pointerdown", preserveRowSelectionOnSecondaryPress, true);
    document.addEventListener("mousedown", preserveRowSelectionOnSecondaryPress, true);

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
            protectDestroyedCellComponents();
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
        const result = originalRedraw(force);
        protectDestroyedCellComponents();
        return result;
    };

    table.on("tableBuilt", () => {
        ready = true;
        protectDestroyedCellComponents();
        pending = true;
        flushPending();
    });
    table.on("renderComplete", () => {
        ready = true;
        protectDestroyedCellComponents();
        flushPending();
    });

    protectDestroyedCellComponents();
    if (ready) {
        window.requestAnimationFrame(() => {
            pending = true;
            flushPending();
        });
    }

    if (document.readyState === "complete") {
        window.setTimeout(loadContextFallback, 0);
    } else {
        window.addEventListener("load", () => window.setTimeout(loadContextFallback, 0), {once: true});
    }
})();
