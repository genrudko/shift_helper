"use strict";

/* Keep the settings-dialog slider compatible while the status bar uses Excel mapping. */
(() => {
    const root = document.getElementById("event-journal");
    const journalZoom = document.getElementById("journal-zoom");
    if (!root || !journalZoom || !window.shiftHelperAcceptanceStage1) return;

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
})();
