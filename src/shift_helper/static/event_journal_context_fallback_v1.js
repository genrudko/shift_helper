"use strict";

/* Keep all live view controls in one atomic local preference object. */
(() => {
    const preferenceKey = "shift-helper-ui-preferences-v1";
    const controls = {
        theme: document.getElementById("journal-theme"),
        fontSize: document.getElementById("journal-font-size"),
        fontFamily: document.getElementById("journal-font-family"),
        frozenThrough: document.getElementById("journal-frozen-through"),
    };

    function readPreferences() {
        try {
            return JSON.parse(localStorage.getItem(preferenceKey) || "{}");
        } catch (_error) {
            return {};
        }
    }

    function writeLivePreferences() {
        const preferences = readPreferences();
        if (controls.theme) preferences.theme = controls.theme.value;
        if (controls.fontSize) preferences.fontSize = Number(controls.fontSize.value) || 13;
        if (controls.fontFamily) preferences.fontFamily = controls.fontFamily.value;
        if (controls.frozenThrough) preferences.frozenThrough = controls.frozenThrough.value;
        const zoom = Number(document.getElementById("ribbon-zoom")?.value);
        if (Number.isFinite(zoom)) preferences.zoom = zoom;
        try {
            localStorage.setItem(preferenceKey, JSON.stringify(preferences));
        } catch (_error) {
            // Workstation presentation settings must not block journal input.
        }
    }

    Object.values(controls).forEach((control) => {
        control?.addEventListener("input", writeLivePreferences, true);
        control?.addEventListener("change", writeLivePreferences, true);
    });
    writeLivePreferences();

    if (!document.getElementById("event-journal-context-fallback-legacy-v1")) {
        const legacy = document.createElement("script");
        legacy.id = "event-journal-context-fallback-legacy-v1";
        legacy.src = "/static/event_journal_context_fallback_legacy_v1.js";
        document.body.appendChild(legacy);
    }
})();
