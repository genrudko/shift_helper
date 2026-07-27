"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const settingsDialog = document.getElementById("journal-view-settings");
    const frozenSelect = document.getElementById("journal-frozen-through");

    if (!root || !table || !settingsDialog || !frozenSelect) return;

    const preferenceKey = "shift-helper-ui-preferences-v1";
    const widthKey = "shift-helper-column-base-widths-v1";
    const defaults = {
        theme: "dark",
        zoom: 100,
        fontSize: 13,
        fontFamily: "Segoe UI",
        frozenThrough: "asset_label",
    };

    let preferences = loadPreferences();
    let frozenApplying = false;
    let geometryFrame = 0;
    let rowDrag = null;
    let syntheticRowPointer = false;
    let geometryBound = false;

    function loadPreferences() {
        try {
            return {
                ...structuredClone(defaults),
                ...JSON.parse(localStorage.getItem(preferenceKey) || "{}"),
            };
        } catch (_error) {
            return structuredClone(defaults);
        }
    }

    function savePreferences() {
        try {
            localStorage.setItem(preferenceKey, JSON.stringify(preferences));
        } catch (_error) {
            // Visual preferences must never block journal input.
        }
    }

    function effectiveTheme() {
        if (preferences.theme !== "system") return preferences.theme;
        return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }

    function availableFields() {
        return new Set([
            "none",
            ...table.getColumns().map((column) => column.getField()).filter(Boolean),
        ]);
    }

    function normalizePreferences() {
        preferences.zoom = Math.min(400, Math.max(10, Number(preferences.zoom) || 100));
        preferences.fontSize = Math.min(200, Math.max(1, Number(preferences.fontSize) || 13));
        if (!availableFields().has(preferences.frozenThrough)) {
            preferences.frozenThrough = defaults.frozenThrough;
        }
    }

    function applyAppearance() {
        normalizePreferences();
        document.body.style.removeProperty("zoom");
        document.body.style.removeProperty("width");
        document.documentElement.dataset.theme = effectiveTheme();
        document.documentElement.style.setProperty(
            "--ui-font-family",
            `"${preferences.fontFamily}", "Segoe UI", system-ui, sans-serif`,
        );
        document.documentElement.style.setProperty("--ui-viewport-height", "100vh");
        savePreferences();
    }

    function hideFillHandle() {
        const handle = document.querySelector(".journal-fill-handle");
        if (handle) handle.hidden = true;
    }

    function selectedLastCellElement() {
        if ((window.shiftHelperSelectedRowKeys || []).length) return null;
        const range = table.getRanges?.().at(-1);
        const raw = range?.getCells?.() || [];
        const cells = (raw.length && Array.isArray(raw[0]) ? raw.flat() : raw)
            .filter((cell) => cell && typeof cell.getElement === "function");
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
        const cellElement = selectedLastCellElement();
        if (!handle || !cellElement) {
            hideFillHandle();
            return;
        }
        if (handle.parentElement !== root) root.appendChild(handle);
        const cellRect = cellElement.getBoundingClientRect();
        const rootRect = root.getBoundingClientRect();
        handle.style.left = `${cellRect.right - rootRect.left - (handle.offsetWidth / 2)}px`;
        handle.style.top = `${cellRect.bottom - rootRect.top - (handle.offsetHeight / 2)}px`;
        handle.hidden = false;
    }

    function scheduleGeometry() {
        cancelAnimationFrame(geometryFrame);
        geometryFrame = requestAnimationFrame(placeFillHandle);
    }

    function applyFrozenColumns() {
        if (frozenApplying || typeof table.getColumnLayout !== "function") return;
        const layout = table.getColumnLayout();
        const boundaryIndex = preferences.frozenThrough === "none"
            ? -1
            : layout.findIndex((column) => column.field === preferences.frozenThrough);
        let changed = false;
        layout.forEach((column, index) => {
            const frozen = boundaryIndex >= 0 && index <= boundaryIndex;
            if (Boolean(column.frozen) !== frozen) {
                column.frozen = frozen;
                changed = true;
            }
        });
        if (!changed) return;

        frozenApplying = true;
        hideFillHandle();
        try {
            (table.getRanges?.() || []).forEach((range) => range.remove());
            table.setColumnLayout(layout);
        } finally {
            frozenApplying = false;
        }
        requestAnimationFrame(() => {
            table.redraw(true);
            scheduleGeometry();
        });
    }

    function syncSettings() {
        const theme = document.getElementById("journal-theme");
        const zoom = document.getElementById("journal-zoom");
        const fontSize = document.getElementById("journal-font-size");
        const fontFamily = document.getElementById("journal-font-family");
        if (theme) theme.value = preferences.theme;
        if (zoom) zoom.value = String(preferences.zoom);
        if (fontSize) fontSize.value = String(preferences.fontSize);
        if (fontFamily) fontFamily.value = preferences.fontFamily;
        frozenSelect.value = preferences.frozenThrough;
    }

    function protectEditor(editor) {
        if (editor.dataset.caretClickProtected === "true") return;
        editor.dataset.caretClickProtected = "true";
        const keepEditing = (event) => event.stopPropagation();
        ["pointerdown", "mousedown", "pointerup", "click", "dblclick"].forEach((type) => {
            editor.addEventListener(type, keepEditing);
        });
    }

    new MutationObserver(() => {
        root.querySelectorAll(".journal-stable-editor").forEach(protectEditor);
    }).observe(root, {childList: true, subtree: true});

    function rowNumberAtPoint(x, y) {
        const element = document.elementFromPoint(x, y);
        return element instanceof Element ? element.closest(".journal-row-number") : null;
    }

    function dispatchShiftSelection(rowNumber, ctrlKey) {
        syntheticRowPointer = true;
        try {
            rowNumber.dispatchEvent(new PointerEvent("pointerdown", {
                bubbles: true,
                cancelable: true,
                composed: true,
                button: 0,
                buttons: 1,
                shiftKey: true,
                ctrlKey,
            }));
        } finally {
            syntheticRowPointer = false;
        }
    }

    window.addEventListener("pointerdown", (event) => {
        if (syntheticRowPointer || !event.isTrusted || event.button !== 0) return;
        const target = event.target instanceof Element
            ? event.target.closest(".journal-row-number")
            : null;
        if (!target || !root.contains(target)) return;
        rowDrag = {last: target, ctrlKey: event.ctrlKey || event.metaKey};
        root.classList.add("journal-row-dragging");
    }, true);

    window.addEventListener("pointermove", (event) => {
        if (!rowDrag || !(event.buttons & 1)) return;
        const target = rowNumberAtPoint(event.clientX, event.clientY);
        if (target && target !== rowDrag.last) {
            rowDrag.last = target;
            dispatchShiftSelection(target, rowDrag.ctrlKey);
        }
        const holder = root.querySelector(".tabulator-tableholder");
        if (holder) {
            const rect = holder.getBoundingClientRect();
            const rowHeight = Number.parseFloat(
                getComputedStyle(document.documentElement)
                    .getPropertyValue("--journal-row-height"),
            ) || 34;
            const edge = Math.max(24, rowHeight);
            if (event.clientY < rect.top + edge) holder.scrollTop -= Math.max(12, edge / 2);
            else if (event.clientY > rect.bottom - edge) {
                holder.scrollTop += Math.max(12, edge / 2);
            }
        }
        event.preventDefault();
    }, true);

    const finishRowDrag = () => {
        rowDrag = null;
        root.classList.remove("journal-row-dragging");
    };
    window.addEventListener("pointerup", finishRowDrag, true);
    window.addEventListener("pointercancel", finishRowDrag, true);

    document.getElementById("open-view-settings")?.addEventListener("click", () => {
        preferences = loadPreferences();
        normalizePreferences();
        syncSettings();
    });
    document.getElementById("journal-theme")?.addEventListener("change", (event) => {
        preferences.theme = event.target.value;
        applyAppearance();
    });
    document.getElementById("journal-font-size")?.addEventListener("input", (event) => {
        preferences.fontSize = Number(event.target.value);
        applyAppearance();
        scheduleGeometry();
    });
    document.getElementById("journal-font-family")?.addEventListener("change", (event) => {
        preferences.fontFamily = event.target.value;
        applyAppearance();
        scheduleGeometry();
    });
    frozenSelect.addEventListener("change", (event) => {
        preferences.frozenThrough = event.target.value;
        applyAppearance();
        applyFrozenColumns();
    });
    document.getElementById("reset-view-settings")?.addEventListener("click", () => {
        preferences = structuredClone(defaults);
        try {
            localStorage.removeItem(widthKey);
        } catch (_error) {
            // Ignore unavailable local storage.
        }
        applyAppearance();
        syncSettings();
        document.getElementById("journal-zoom")?.dispatchEvent(new Event("input", {bubbles: true}));
        applyFrozenColumns();
    });
    document.getElementById("reset-grid-layout")?.addEventListener("click", () => {
        try {
            localStorage.removeItem(widthKey);
        } catch (_error) {
            // Ignore unavailable local storage.
        }
        requestAnimationFrame(() => {
            table.redraw(false);
            scheduleGeometry();
        });
    });

    ["rangeChanged", "cellClick", "renderComplete", "columnMoved", "columnVisibilityChanged"]
        .forEach((eventName) => table.on(eventName, scheduleGeometry));

    function bindGeometry() {
        if (geometryBound) return;
        const holder = root.querySelector(".tabulator-tableholder");
        if (!holder) return;
        geometryBound = true;
        holder.addEventListener("scroll", scheduleGeometry, {passive: true});
        new ResizeObserver(scheduleGeometry).observe(root);
        document.querySelector(".journal-fill-handle")?.addEventListener("pointerup", () => {
            requestAnimationFrame(scheduleGeometry);
        });
    }

    table.on("tableBuilt", bindGeometry);
    table.on("renderComplete", bindGeometry);
    bindGeometry();
    window.addEventListener("resize", scheduleGeometry);
    matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
        if (preferences.theme === "system") applyAppearance();
    });

    applyAppearance();
    syncSettings();
    applyFrozenColumns();
    scheduleGeometry();
})();
