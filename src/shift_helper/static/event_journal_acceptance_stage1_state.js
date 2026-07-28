"use strict";

/* Synchronize public Stage 1 slider state with the applied sheet zoom. */
(() => {
    const root = document.getElementById("event-journal");
    const controller = window.shiftHelperAcceptanceStage1;
    if (!root || !controller) return;

    function sync() {
        const value = Math.min(400, Math.max(10, Number(root.dataset.sheetZoom) || 100));
        const position = controller.zoomToPosition(value);
        ["journal-zoom", "ribbon-zoom"].forEach((id) => {
            const slider = document.getElementById(`acceptance-${id}`);
            if (!slider) return;
            slider.dataset.zoom = String(value);
            slider.dataset.position = String(position);
            slider.style.setProperty("--acceptance-zoom-position", `${position}%`);
            slider.setAttribute("aria-valuenow", String(value));
            slider.setAttribute("aria-valuetext", `${value}%`);
        });
        root.dataset.acceptanceStage1 = "ready";
    }

    new MutationObserver(sync).observe(root, {
        attributes: true,
        attributeFilter: ["data-sheet-zoom", "data-zoom-applying"],
    });
    requestAnimationFrame(sync);
})();
