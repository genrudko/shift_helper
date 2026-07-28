"use strict";

/* Synchronize public Stage 1 controls and persistence with applied sheet zoom. */
(() => {
    const root = document.getElementById("event-journal");
    const controller = window.shiftHelperAcceptanceStage1;
    if (!root || !controller) return;

    const preferenceKey = "shift-helper-ui-preferences-v1";
    const legacyZoomKey = "shift-helper-operator-zoom-v1";

    function persistAppliedZoom(value) {
        if (root.dataset.zoomApplying === "true") return;
        window.shiftHelperPersistedZoom = value;
        try {
            const preferences = JSON.parse(localStorage.getItem(preferenceKey) || "{}");
            preferences.zoom = value;
            localStorage.setItem(preferenceKey, JSON.stringify(preferences));
            localStorage.setItem(legacyZoomKey, JSON.stringify(value));
        } catch (_error) {
            // Workstation presentation settings must not block journal input.
        }
    }

    function sync() {
        const value = Math.min(400, Math.max(10, Number(root.dataset.sheetZoom) || 100));
        const position = controller.zoomToPosition(value);
        ["journal-zoom", "ribbon-zoom"].forEach((id) => {
            const native = document.getElementById(id);
            if (native) native.value = String(value);
            const slider = document.getElementById(`acceptance-${id}`);
            if (!slider) return;
            slider.dataset.zoom = String(value);
            slider.dataset.position = String(position);
            slider.style.setProperty("--acceptance-zoom-position", `${position}%`);
            slider.setAttribute("aria-valuenow", String(value));
            slider.setAttribute("aria-valuetext", `${value}%`);
        });
        persistAppliedZoom(value);
        root.dataset.acceptanceStage1 = "ready";
    }

    new MutationObserver(sync).observe(root, {
        attributes: true,
        attributeFilter: ["data-sheet-zoom", "data-zoom-applying"],
    });
    requestAnimationFrame(sync);
})();
