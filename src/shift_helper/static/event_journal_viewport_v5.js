"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const settingsDialog = document.getElementById("journal-view-settings");
    const frozenSelect = document.getElementById("journal-frozen-through");

    if (!root || !table || !settingsDialog || !frozenSelect) {
        return;
    }

    const preferenceKey = "shift-helper-ui-preferences-v1";
    const widthKey = "shift-helper-column-base-widths-v1";
    const defaults = {
        theme: "dark",
        zoom: 100,
        fontSize: 13,
        fontFamily: "Segoe UI",
        frozenThrough: "asset_label",
    };
    let preferences = loadJson(preferenceKey, defaults);
    const baseWidths = new Map(Object.entries(loadJson(widthKey, {})));
    let scalingColumns = false;
    let frozenApplying = false;
    let currentScale = 1;
    let geometryFrame = 0;
    let rowDrag = null;
    let syntheticRowPointer = false;
    let geometryBound = false;

    function loadJson(key, fallback) {
        try {
            const raw = window.localStorage.getItem(key);
            return raw === null ? structuredClone(fallback) : {
                ...structuredClone(fallback),
                ...JSON.parse(raw),
            };
        } catch (_error) {
            return structuredClone(fallback);
        }
    }

    function saveJson(key, value) {
        try {
            window.localStorage.setItem(key, JSON.stringify(value));
        } catch (_error) {
            // View settings must never block journal input.
        }
    }

    function saveBaseWidths() {
        saveJson(widthKey, Object.fromEntries(baseWidths));
    }

    function effectiveTheme() {
        if (preferences.theme !== "system") {
            return preferences.theme;
        }
        return window.matchMedia("(prefers-color-scheme: light)").matches
            ? "light"
            : "dark";
    }

    function clampPreferences() {
        preferences.zoom = Math.min(140, Math.max(75, Number(preferences.zoom) || 100));
        preferences.fontSize = Math.min(18, Math.max(10, Number(preferences.fontSize) || 13));
        const fields = new Set(["none", ...table.getColumns()
            .map((column) => column.getField())
            .filter(Boolean)]);
        if (!fields.has(preferences.frozenThrough)) {
            preferences.frozenThrough = defaults.frozenThrough;
        }
    }

    function initializeBaseWidths() {
        table.getColumns().forEach((column) => {
            const field = column.getField();
            if (field && !baseWidths.has(field)) {
                baseWidths.set(field, column.getWidth());
            }
        });
        saveBaseWidths();
    }

    function scaleColumns() {
        initializeBaseWidths();
        const scale = preferences.zoom / 100;
        scalingColumns = true;
        try {
            table.getColumns().forEach((column) => {
                const field = column.getField();
                const base = field ? Number(baseWidths.get(field)) : 0;
                if (base > 0) {
                    column.setWidth(Math.max(54, Math.round(base * scale)));
                }
            });
        } finally {
            scalingColumns = false;
            currentScale = scale;
        }
    }

    function applyFrozenColumns() {
        if (frozenApplying || typeof table.getColumnLayout !== "function") {
            return;
        }
        const layout = table.getColumnLayout();
        const boundary = preferences.frozenThrough;
        const boundaryIndex = boundary === "none"
            ? -1
            : layout.findIndex((column) => column.field === boundary);
        let changed = false;
        layout.forEach((column, index) => {
            const frozen = boundaryIndex >= 0 && index <= boundaryIndex;
            if (Boolean(column.frozen) !== frozen) {
                column.frozen = frozen;
                changed = true;
            }
        });
        if (!changed) {
            return;
        }
        frozenApplying = true;
        hideFillHandle();
        try {
            (table.getRanges?.() || []).forEach((range) => range.remove());
            table.setColumnLayout(layout);
        } finally {
            frozenApplying = false;
        }
        window.requestAnimationFrame(() => {
            scaleColumns();
            table.redraw(true);
            scheduleGeometry();
        });
    }

    function applyView({freeze = true} = {}) {
        clampPreferences();
        const scale = preferences.zoom / 100;
        document.body.style.zoom = "";
        document.body.style.width = "";
        document.documentElement.dataset.theme = effectiveTheme();
        document.documentElement.style.setProperty("--ui-scale-factor", String(scale));
        document.documentElement.style.setProperty(
            "--ui-font-family",
            `"${preferences.fontFamily}", "Segoe UI", system-ui, sans-serif`,
        );
        document.documentElement.style.setProperty(
            "--journal-font-size",
            `${preferences.fontSize * scale}px`,
        );
        document.documentElement.style.setProperty(
            "--journal-row-height",
            `${Math.round(34 * scale)}px`,
        );
        document.documentElement.style.setProperty(
            "--journal-control-height",
            `${Math.round(30 * scale)}px`,
        );
        document.documentElement.style.setProperty(
            "--journal-toolbar-gap",
            `${Math.max(5, Math.round(8 * scale))}px`,
        );
        document.documentElement.style.setProperty("--ui-viewport-height", "100vh");
        scaleColumns();
        saveJson(preferenceKey, preferences);
        if (freeze) {
            applyFrozenColumns();
        }
        window.requestAnimationFrame(() => {
            table.redraw(true);
            scheduleGeometry();
        });
    }

    function selectedLastCell() {
        if ((window.shiftHelperSelectedRowKeys || []).length) {
            return null;
        }
        const range = table.getRanges?.().at(-1);
        const raw = range?.getCells?.() || [];
        const cells = (raw.length && Array.isArray(raw[0]) ? raw.flat() : raw)
            .filter((cell) => cell && typeof cell.getElement === "function");
        return cells.at(-1) || null;
    }

    function fillHandle() {
        return document.querySelector(".journal-fill-handle");
    }

    function hideFillHandle() {
        const handle = fillHandle();
        if (handle) {
            handle.hidden = true;
        }
    }

    function placeFillHandle() {
        const handle = fillHandle();
        const cell = selectedLastCell();
        if (!handle || !cell || !cell.getElement()?.isConnected) {
            hideFillHandle();
            return;
        }
        if (handle.parentElement !== root) {
            root.appendChild(handle);
        }
        const cellRect = cell.getElement().getBoundingClientRect();
        const rootRect = root.getBoundingClientRect();
        handle.style.left = `${cellRect.right - rootRect.left - (handle.offsetWidth / 2)}px`;
        handle.style.top = `${cellRect.bottom - rootRect.top - (handle.offsetHeight / 2)}px`;
        handle.hidden = false;
    }

    function scheduleGeometry() {
        window.cancelAnimationFrame(geometryFrame);
        geometryFrame = window.requestAnimationFrame(placeFillHandle);
    }

    function protectEditor(editor) {
        if (editor.dataset.caretClickProtected === "true") {
            return;
        }
        editor.dataset.caretClickProtected = "true";
        const keepEditing = (event) => {
            event.stopPropagation();
        };
        editor.addEventListener("pointerdown", keepEditing);
        editor.addEventListener("mousedown", keepEditing);
        editor.addEventListener("pointerup", keepEditing);
        editor.addEventListener("click", keepEditing);
        editor.addEventListener("dblclick", keepEditing);
    }

    const editorObserver = new MutationObserver(() => {
        root.querySelectorAll(".journal-stable-editor").forEach(protectEditor);
    });
    editorObserver.observe(root, {childList: true, subtree: true});

    function rowNumberAtPoint(x, y) {
        const element = document.elementFromPoint(x, y);
        return element instanceof Element
            ? element.closest(".journal-row-number")
            : null;
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
        if (syntheticRowPointer || !event.isTrusted || event.button !== 0) {
            return;
        }
        const target = event.target instanceof Element
            ? event.target.closest(".journal-row-number")
            : null;
        if (!target || !root.contains(target)) {
            return;
        }
        rowDrag = {
            last: target,
            ctrlKey: event.ctrlKey || event.metaKey,
        };
        root.classList.add("journal-row-dragging");
    }, true);

    window.addEventListener("pointermove", (event) => {
        if (!rowDrag || !(event.buttons & 1)) {
            return;
        }
        const target = rowNumberAtPoint(event.clientX, event.clientY);
        if (target && target !== rowDrag.last) {
            rowDrag.last = target;
            dispatchShiftSelection(target, rowDrag.ctrlKey);
        }
        const holder = root.querySelector(".tabulator-tableholder");
        if (holder) {
            const rect = holder.getBoundingClientRect();
            const edge = Math.max(24, 34 * currentScale);
            if (event.clientY < rect.top + edge) {
                holder.scrollTop -= Math.max(12, edge / 2);
            } else if (event.clientY > rect.bottom - edge) {
                holder.scrollTop += Math.max(12, edge / 2);
            }
        }
        event.preventDefault();
    }, true);

    function finishRowDrag() {
        rowDrag = null;
        root.classList.remove("journal-row-dragging");
    }

    window.addEventListener("pointerup", finishRowDrag, true);
    window.addEventListener("pointercancel", finishRowDrag, true);

    function syncSettings() {
        frozenSelect.value = preferences.frozenThrough;
    }

    document.getElementById("open-view-settings")?.addEventListener("click", () => {
        preferences = loadJson(preferenceKey, defaults);
        syncSettings();
    });

    document.getElementById("journal-theme")?.addEventListener("change", (event) => {
        preferences.theme = event.target.value;
        applyView({freeze: false});
    });
    document.getElementById("journal-zoom")?.addEventListener("input", (event) => {
        preferences.zoom = Number(event.target.value);
        applyView({freeze: false});
    });
    document.getElementById("journal-font-size")?.addEventListener("input", (event) => {
        preferences.fontSize = Number(event.target.value);
        applyView({freeze: false});
    });
    document.getElementById("journal-font-family")?.addEventListener("change", (event) => {
        preferences.fontFamily = event.target.value;
        applyView({freeze: false});
    });
    frozenSelect.addEventListener("change", (event) => {
        preferences.frozenThrough = event.target.value;
        applyView({freeze: true});
    });
    document.getElementById("reset-view-settings")?.addEventListener("click", () => {
        preferences = {...defaults};
        baseWidths.clear();
        saveBaseWidths();
        applyView({freeze: true});
    });
    document.getElementById("reset-grid-layout")?.addEventListener("click", () => {
        window.requestAnimationFrame(() => {
            baseWidths.clear();
            initializeBaseWidths();
            scaleColumns();
            scheduleGeometry();
        });
    });

    table.on("columnResized", (column) => {
        if (scalingColumns || frozenApplying) {
            return;
        }
        const field = column?.getField?.();
        if (field) {
            baseWidths.set(field, column.getWidth() / Math.max(0.75, currentScale));
            saveBaseWidths();
        }
        scheduleGeometry();
    });
    table.on("rangeChanged", scheduleGeometry);
    table.on("cellClick", scheduleGeometry);
    table.on("renderComplete", scheduleGeometry);
    table.on("columnMoved", scheduleGeometry);
    table.on("columnVisibilityChanged", scheduleGeometry);

    function bindGeometry() {
        if (geometryBound) {
            return;
        }
        const holder = root.querySelector(".tabulator-tableholder");
        if (!holder) {
            return;
        }
        geometryBound = true;
        holder.addEventListener("scroll", scheduleGeometry, {passive: true});
        new ResizeObserver(() => {
            table.redraw(true);
            scheduleGeometry();
        }).observe(root);
        const handle = fillHandle();
        handle?.addEventListener("pointerup", () => {
            window.requestAnimationFrame(scheduleGeometry);
        });
    }

    table.on("tableBuilt", bindGeometry);
    table.on("renderComplete", bindGeometry);
    bindGeometry();

    window.addEventListener("resize", () => {
        preferences = loadJson(preferenceKey, defaults);
        applyView({freeze: false});
    });
    window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
        if (preferences.theme === "system") {
            applyView({freeze: false});
        }
    });

    applyView({freeze: true});
    syncSettings();
    scheduleGeometry();
})();
