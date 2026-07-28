"use strict";

/* Keep all live view controls in one atomic local preference object. */
(() => {
    const root = document.getElementById("event-journal");
    const preferenceKey = "shift-helper-ui-preferences-v1";
    let bound = false;

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

    function writeLivePreferences() {
        const live = controls();
        const preferences = readPreferences();
        if (live.theme) preferences.theme = live.theme.value;
        if (live.fontSize) preferences.fontSize = Number(live.fontSize.value) || 13;
        if (live.fontFamily) preferences.fontFamily = live.fontFamily.value;
        if (live.frozenThrough) preferences.frozenThrough = live.frozenThrough.value;
        const zoom = Number(document.getElementById("ribbon-zoom")?.value);
        if (Number.isFinite(zoom)) preferences.zoom = zoom;
        try {
            localStorage.setItem(preferenceKey, JSON.stringify(preferences));
        } catch (_error) {
            // Workstation presentation settings must not block journal input.
        }
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
