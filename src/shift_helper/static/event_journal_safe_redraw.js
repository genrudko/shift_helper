"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;

    if (!root || !table || typeof table.redraw !== "function") {
        return;
    }

    const originalRedraw = table.redraw.bind(table);
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
})();
