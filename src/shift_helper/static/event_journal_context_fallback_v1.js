"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;

    if (!root || !table || root.dataset.contextFallback === "ready") {
        return;
    }
    root.dataset.contextFallback = "ready";

    let redispatching = false;

    function liveCellAtPoint(x, y) {
        for (const row of table.getRows("visible")) {
            for (const cell of row.getCells()) {
                let element = null;
                try {
                    element = cell.getElement();
                } catch (_error) {
                    continue;
                }
                if (!(element instanceof Element) || !element.isConnected) {
                    continue;
                }
                const rect = element.getBoundingClientRect();
                if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
                    return {cell, element};
                }
            }
        }
        return null;
    }

    window.addEventListener("contextmenu", (event) => {
        if (
            redispatching
            || !(event.target instanceof Element)
            || !root.contains(event.target)
            || event.target.closest(".journal-row-number")
        ) {
            return;
        }

        const live = liveCellAtPoint(event.clientX, event.clientY);
        if (!live) {
            return;
        }

        const before = document.querySelectorAll(".journal-context-shell").length;
        const coordinates = {
            clientX: event.clientX,
            clientY: event.clientY,
            screenX: event.screenX,
            screenY: event.screenY,
        };

        window.setTimeout(() => {
            if (document.querySelectorAll(".journal-context-shell").length > before) {
                return;
            }
            redispatching = true;
            try {
                live.element.dispatchEvent(new MouseEvent("contextmenu", {
                    bubbles: true,
                    cancelable: true,
                    composed: true,
                    button: 2,
                    buttons: 2,
                    ...coordinates,
                }));
            } finally {
                redispatching = false;
            }
        }, 0);
    }, true);
})();
