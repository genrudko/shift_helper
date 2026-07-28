"use strict";

/* Keep all live view controls in one atomic local preference object. */
(() => {
    const root = document.getElementById("event-journal");
    const preferenceKey = "shift-helper-ui-preferences-v1";
    const legacyZoomKey = "shift-helper-operator-zoom-v1";
    const zoomControlIds = new Set(["journal-zoom", "ribbon-zoom"]);
    let bound = false;
    let reapplyFrame = 0;
    let requestedZoom = 100;

    function clampZoom(value) {
        return Math.min(400, Math.max(10, Number(value) || 100));
    }

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

    function setRequestedZoom(value) {
        requestedZoom = clampZoom(value);
        window.shiftHelperPersistedZoom = requestedZoom;
    }

    function savePreferences(preferences) {
        try {
            localStorage.setItem(preferenceKey, JSON.stringify(preferences));
            localStorage.setItem(legacyZoomKey, JSON.stringify(requestedZoom));
        } catch (_error) {
            // Workstation presentation settings must not block journal input.
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
        savePreferences(preferences);
        reapplyCurrentZoom(requestedZoom);
    }

    function persistRequestedZoom() {
        const preferences = readPreferences();
        preferences.zoom = requestedZoom;
        savePreferences(preferences);
    }

    function rememberZoomRequest(event) {
        const target = event.target;
        if (!(target instanceof HTMLInputElement) || !zoomControlIds.has(target.id)) return;
        const value = Number(target.value);
        if (!Number.isFinite(value)) return;
        setRequestedZoom(value);
        persistRequestedZoom();
    }

    function rememberZoomWheel(event) {
        const target = event.target;
        if (!(target instanceof HTMLInputElement) || !zoomControlIds.has(target.id)) return;
        const value = Number(target.value) + (event.deltaY < 0 ? 5 : -5);
        setRequestedZoom(value);
        persistRequestedZoom();
    }

    function rememberZoomButton(event) {
        const button = event.target instanceof Element
            ? event.target.closest("#ribbon-zoom-out, #ribbon-zoom-in")
            : null;
        if (!button) return;
        const current = Number(document.getElementById("ribbon-zoom")?.value) || requestedZoom;
        setRequestedZoom(current + (button.id === "ribbon-zoom-in" ? 5 : -5));
        persistRequestedZoom();
    }

    function bindLivePreferences() {
        if (bound) return;
        if (root?.dataset.videoAcceptanceRepair !== "ready") {
            requestAnimationFrame(bindLivePreferences);
            return;
        }
        bound = true;
        const stored = readPreferences();
        setRequestedZoom(
            Number(window.shiftHelperPersistedZoom)
            || Number(stored.zoom)
            || Number(document.getElementById("ribbon-zoom")?.value)
            || 100,
        );
        window.addEventListener("input", rememberZoomRequest, true);
        window.addEventListener("change", rememberZoomRequest, true);
        window.addEventListener("wheel", rememberZoomWheel, {capture: true, passive: true});
        window.addEventListener("click", rememberZoomButton, true);
        Object.values(controls()).forEach((control) => {
            control?.addEventListener("input", writeLivePreferences, true);
            control?.addEventListener("change", writeLivePreferences, true);
        });
        writeLivePreferences();
        root.dataset.liveViewPreferences = "ready";
        root.dataset.contextController = "ribbon-with-preflight";
        root.dataset.contextFallback = "ready";
    }

    bindLivePreferences();
})();
