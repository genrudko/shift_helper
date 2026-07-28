"use strict";

/* Keep the settings-dialog slider compatible while the status bar uses Excel mapping. */
(() => {
    const root = document.getElementById("event-journal");
    const journalZoom = document.getElementById("journal-zoom");
    const controller = window.shiftHelperAcceptanceStage1;
    if (!root || !journalZoom || !controller) return;

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
        controller.setZoom(event.target.value);
    }, true);

    root.dataset.acceptanceStage1 = "ready";
})();
