"use strict";

/* Keep all live view controls in one atomic local preference object. */
(() => {
    const root = document.getElementById("event-journal");
    const preferenceKey = "shift-helper-ui-preferences-v1";
    let bound = false;
    let reapplyFrame = 0;
    let requestedZoom = 100;

    function controls() {
        return {
            theme: document.getElementById("journal-theme"),
            fontSize: document.getElementById("journal-font-size"),
            fontFamily: document.getElementById("journal-font-family"),
            frozenThrough: document.getElementById("journal-frozen-through"),
        };
    }

    function readPreferences() {
        try {
            return JSON.parse(localStorage.getItem(preferenceKey) || "{}");
        } catch (_error) {
            return {};
        }
    }

    function reapplyCurrentZoom(value) {
        cancelAnimationFrame(reapplyFrame);
        reapplyFrame = requestAnimationFrame(() => {
            window.shiftHelperZoom?.apply?.(value, false);
        });
    }

    function writeLivePreferences() {
        const live = controls();
        const preferences = readPreferences();
        if (live.theme) preferences.theme = live.theme.value;
        if (live.fontSize) preferences.fontSize = Number(live.fontSize.value) || 13;
        if (live.fontFamily) preferences.fontFamily = live.fontFamily.value;
        if (live.frozenThrough) preferences.frozenThrough = live.frozenThrough.value;
        preferences.zoom = requestedZoom;
        try {
            localStorage.setItem(preferenceKey, JSON.stringify(preferences));
        } catch (_error) {
            // Workstation presentation settings must not block journal input.
        }
        reapplyCurrentZoom(requestedZoom);
    }

    function rememberZoomRequest(event) {
        const target = event.target;
        if (!(target instanceof HTMLInputElement)) return;
        if (!new Set(["journal-zoom", "ribbon-zoom"]).has(target.id)) return;
        const value = Number(target.value);
        if (Number.isFinite(value)) requestedZoom = value;
    }

    function rememberZoomWheel(event) {
        const target = event.target;
        if (!(target instanceof HTMLInputElement)) return;
        if (!new Set(["journal-zoom", "ribbon-zoom"]).has(target.id)) return;
        const value = Number(target.value) + (event.deltaY < 0 ? 5 : -5);
        requestedZoom = Math.min(400, Math.max(10, value));
    }

    function loadLegacyContextController() {
        if (document.getElementById("event-journal-context-fallback-legacy-v1")) return;
        const legacy = document.createElement("script");
        legacy.id = "event-journal-context-fallback-legacy-v1";
        legacy.src = "/static/event_journal_context_fallback_legacy_v1.js";
        document.body.appendChild(legacy);
    }

    function bindLivePreferences() {
        if (bound) return;
        if (root?.dataset.videoAcceptanceRepair !== "ready") {
            requestAnimationFrame(bindLivePreferences);
            return;
        }
        bound = true;
        const stored = readPreferences();
        requestedZoom = Number(stored.zoom)
            || Number(document.getElementById("ribbon-zoom")?.value)
            || 100;
        window.addEventListener("input", rememberZoomRequest, true);
        window.addEventListener("change", rememberZoomRequest, true);
        window.addEventListener("wheel", rememberZoomWheel, {capture: true, passive: true});
        Object.values(controls()).forEach((control) => {
            control?.addEventListener("input", writeLivePreferences, true);
            control?.addEventListener("change", writeLivePreferences, true);
        });
        writeLivePreferences();
        root.dataset.liveViewPreferences = "ready";
        loadLegacyContextController();
    }

    bindLivePreferences();
})();
