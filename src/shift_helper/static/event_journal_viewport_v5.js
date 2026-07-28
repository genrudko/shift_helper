"use strict";

/*
 * Geometry-only viewport controller.
 * Zoom and row selection deliberately live in event_journal_bootstrap_v1.js.
 */

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const frozenSelect = document.getElementById("journal-frozen-through");
    if (!root || !table || !frozenSelect) return;

    const preferenceKey = "shift-helper-ui-preferences-v1";
    let geometryFrame = 0;
    let frozenApplying = false;

    const loadPreferences = () => {
        try {
            return JSON.parse(localStorage.getItem(preferenceKey) || "{}");
        } catch (_error) {
            return {};
        }
    };
    const savePreferences = (preferences) => {
        try {
            localStorage.setItem(preferenceKey, JSON.stringify(preferences));
        } catch (_error) {
            // Geometry preferences are optional.
        }
    };

    function hideFillHandle() {
        document.querySelectorAll(".journal-fill-handle").forEach((handle) => {
            handle.hidden = true;
        });
    }
    function selectedLastCellElement() {
        if ((window.shiftHelperSelectedRowKeys || []).length) return null;
        const range = table.getRanges?.().at(-1);
        const raw = range?.getCells?.() || [];
        const cells = (raw.length && Array.isArray(raw[0]) ? raw.flat() : raw)
            .filter((cell) => cell?.getElement);
        const cell = cells.at(-1);
        if (!cell) return null;
        try {
            const element = cell.getElement();
            return element?.isConnected ? element : null;
        } catch (_error) {
            return null;
        }
    }
    function placeFillHandle() {
        const handle = document.querySelector(".journal-fill-handle");
        const cell = selectedLastCellElement();
        if (!handle || !cell || root.dataset.selectionMode !== "cells") {
            hideFillHandle();
            return;
        }
        if (handle.parentElement !== document.body) document.body.appendChild(handle);
        const rect = cell.getBoundingClientRect();
        const scale = Number(
            getComputedStyle(document.documentElement).getPropertyValue("--operator-zoom-scale"),
        ) || 1;
        const size = Math.max(6, Math.min(18, 9 * scale));
        handle.style.position = "fixed";
        handle.style.width = `${size}px`;
        handle.style.height = `${size}px`;
        handle.style.left = `${rect.right - (size / 2)}px`;
        handle.style.top = `${rect.bottom - (size / 2)}px`;
        handle.hidden = false;
    }
    function scheduleGeometry() {
        cancelAnimationFrame(geometryFrame);
        geometryFrame = requestAnimationFrame(placeFillHandle);
    }

    function applyFrozenColumns() {
        const controller = window.shiftHelperFrozenColumns;
        if (!controller || frozenApplying) return;
        frozenApplying = true;
        hideFillHandle();
        try {
            const preferences = loadPreferences();
            const desired = frozenSelect.value || preferences.frozenThrough || "asset_label";
            const applied = controller.applyBoundary(desired);
            preferences.frozenThrough = applied;
            frozenSelect.value = applied;
            const ribbonSelect = document.getElementById("ribbon-frozen-through");
            if (ribbonSelect) ribbonSelect.value = applied;
            savePreferences(preferences);
        } finally {
            frozenApplying = false;
        }
        scheduleGeometry();
    }

    function protectEditor(editor) {
        if (editor.dataset.caretClickProtected === "true") return;
        editor.dataset.caretClickProtected = "true";
        const keepEditing = (event) => event.stopPropagation();
        ["pointerdown", "mousedown", "pointerup", "click", "dblclick"].forEach((type) => {
            editor.addEventListener(type, keepEditing);
        });
        const openContextMenu = (event) => {
            if (event.button !== 2 && event.type !== "contextmenu") return;
            event.preventDefault();
            event.stopImmediatePropagation();
            window.shiftHelperContextPreflightOpen?.(
                "cells",
                event.clientX,
                event.clientY,
            );
        };
        editor.addEventListener("pointerdown", openContextMenu, true);
        editor.addEventListener("contextmenu", openContextMenu, true);
    }
    const editorObserver = new MutationObserver(() => {
        root.querySelectorAll(".journal-stable-editor").forEach(protectEditor);
    });
    editorObserver.observe(root, {childList: true, subtree: true});

    frozenSelect.addEventListener("change", applyFrozenColumns);
    document.getElementById("ribbon-frozen-through")?.addEventListener(
        "change",
        () => window.setTimeout(applyFrozenColumns, 0),
    );
    document.getElementById("reset-view-settings")?.addEventListener(
        "click",
        () => window.setTimeout(applyFrozenColumns, 0),
    );

    ["rangeChanged", "cellClick", "renderComplete", "columnMoved", "columnVisibilityChanged"]
        .forEach((eventName) => table.on(eventName, scheduleGeometry));
    table.on("tableBuilt", applyFrozenColumns);
    table.on("renderComplete", applyFrozenColumns);

    const bindHolder = () => {
        const holder = root.querySelector(".tabulator-tableholder");
        if (!holder || holder.dataset.geometryBound === "true") return;
        holder.dataset.geometryBound = "true";
        holder.addEventListener("scroll", scheduleGeometry, {passive: true});
    };
    table.on("tableBuilt", bindHolder);
    table.on("renderComplete", bindHolder);
    bindHolder();

    window.addEventListener("resize", scheduleGeometry);
    window.addEventListener("shifthelper:zoom", scheduleGeometry);
    applyFrozenColumns();
    scheduleGeometry();
    root.dataset.viewportController = "geometry-only";
})();
