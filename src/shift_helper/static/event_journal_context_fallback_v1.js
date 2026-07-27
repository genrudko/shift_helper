"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;

    if (!root || !table || root.dataset.contextFallback === "ready") {
        return;
    }
    root.dataset.contextFallback = "ready";

    let redispatching = false;

    function containsPoint(element, x, y) {
        const rect = element.getBoundingClientRect();
        return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
    }

    function liveRowHeaderAtPoint(x, y) {
        for (const row of table.getRows("visible")) {
            let rowElement = null;
            try {
                rowElement = row.getElement();
            } catch (_error) {
                continue;
            }
            const header = rowElement?.querySelector?.(".journal-row-number");
            if (header instanceof Element && header.isConnected && containsPoint(header, x, y)) {
                return header;
            }
        }
        return null;
    }

    function liveCellAtPoint(x, y) {
        for (const row of table.getRows("visible")) {
            for (const cell of row.getCells()) {
                let element = null;
                try {
                    element = cell.getElement();
                } catch (_error) {
                    continue;
                }
                if (
                    element instanceof Element
                    && element.isConnected
                    && containsPoint(element, x, y)
                ) {
                    return element;
                }
            }
        }
        return null;
    }

    function pointerInit(event) {
        return {
            bubbles: true,
            cancelable: true,
            composed: true,
            pointerId: event.pointerId,
            pointerType: event.pointerType || "mouse",
            isPrimary: event.isPrimary,
            button: event.button,
            buttons: event.buttons,
            clientX: event.clientX,
            clientY: event.clientY,
            screenX: event.screenX,
            screenY: event.screenY,
            ctrlKey: event.ctrlKey,
            shiftKey: event.shiftKey,
            altKey: event.altKey,
            metaKey: event.metaKey,
        };
    }

    window.addEventListener("pointerdown", (event) => {
        if (
            redispatching
            || !(event.target instanceof Element)
            || !root.contains(event.target)
            || event.target.closest(".journal-row-number")
        ) {
            return;
        }
        const header = liveRowHeaderAtPoint(event.clientX, event.clientY);
        if (!header) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        redispatching = true;
        try {
            header.dispatchEvent(new PointerEvent("pointerdown", pointerInit(event)));
        } finally {
            redispatching = false;
        }
    }, true);

    window.addEventListener("contextmenu", (event) => {
        if (
            redispatching
            || !(event.target instanceof Element)
            || !root.contains(event.target)
        ) {
            return;
        }
        if (event.target.closest(".journal-row-number")) {
            return;
        }

        const target = liveRowHeaderAtPoint(event.clientX, event.clientY)
            || liveCellAtPoint(event.clientX, event.clientY);
        if (!target) {
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
                target.dispatchEvent(new MouseEvent("contextmenu", {
                    bubbles: true,
                    cancelable: true,
                    composed: true,
                    button: 2,
                    buttons: 2,
                    ctrlKey: event.ctrlKey,
                    shiftKey: event.shiftKey,
                    altKey: event.altKey,
                    metaKey: event.metaKey,
                    ...coordinates,
                }));
            } finally {
                redispatching = false;
            }
        }, 0);
    }, true);
})();
