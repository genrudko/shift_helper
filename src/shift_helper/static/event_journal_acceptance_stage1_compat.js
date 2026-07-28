"use strict";

/* Keep the settings-dialog slider compatible while the status bar uses Excel mapping. */
(() => {
    const root = document.getElementById("event-journal");
    const journalZoom = document.getElementById("journal-zoom");
    if (!root || !journalZoom || !window.shiftHelperAcceptanceStage1) return;

    const preferenceKey = "shift-helper-ui-preferences-v1";
    const legacyZoomKey = "shift-helper-operator-zoom-v1";
    const nativeSetItem = Storage.prototype.setItem;
    Storage.prototype.setItem = function setItem(key, value) {
        if (this === localStorage && key === preferenceKey) {
            try {
                const parsed = JSON.parse(String(value));
                const zoom = Number(parsed.zoom);
                if (Number.isFinite(zoom)) window.shiftHelperPersistedZoom = zoom;
            } catch (_error) {
                // Preserve the underlying storage behavior for malformed writes.
            }
        } else if (this === localStorage && key === legacyZoomKey) {
            try {
                const zoom = Number(JSON.parse(String(value)));
                if (Number.isFinite(zoom)) window.shiftHelperPersistedZoom = zoom;
            } catch (_error) {
                // Preserve the underlying storage behavior for malformed writes.
            }
        }
        return nativeSetItem.call(this, key, value);
    };

    document.getElementById("acceptance-journal-zoom")?.remove();
    journalZoom.classList.remove("acceptance-zoom-native");
    journalZoom.min = "10";
    journalZoom.max = "400";
    journalZoom.step = "5";

    window.addEventListener("input", (event) => {
        if (!(event.target instanceof HTMLInputElement)) return;
        if (!new Set(["journal-zoom", "ribbon-zoom"]).has(event.target.id)) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        window.shiftHelperAcceptanceStage1.setZoom(event.target.value);
    }, true);

    root.dataset.acceptanceStage1 = "ready";
})();
