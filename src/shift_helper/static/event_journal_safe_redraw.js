"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;

    if (!root || !table || typeof table.redraw !== "function") {
        return;
    }

    const preferenceKey = "shift-helper-ui-preferences-v1";
    const defaultBoundary = "asset_label";
    const detachedCellElement = document.createElement("span");
    const originalRedraw = table.redraw.bind(table);
    const originalGetRows = table.getRows.bind(table);
    const originalGetColumnLayout = table.getColumnLayout?.bind(table);
    const originalSetColumnLayout = table.setColumnLayout?.bind(table);

    let ready = Boolean(root.querySelector(".tabulator-tableholder"));
    let pending = false;
    let pendingForce = false;
    let suppressNextForcedRedraw = false;
    let stickyFrame = 0;
    let virtualFrozenFields = new Set();

    function readPreferences() {
        try {
            return JSON.parse(localStorage.getItem(preferenceKey) || "{}");
        } catch (_error) {
            return {};
        }
    }

    function writePreferences(value) {
        try {
            localStorage.setItem(preferenceKey, JSON.stringify(value));
        } catch (_error) {
            // View preferences must never block journal input.
        }
    }

    function orderedDataFields() {
        return table.getColumns()
            .map((column) => column.getField())
            .filter(Boolean);
    }

    function fieldsThrough(boundary) {
        const fields = orderedDataFields();
        if (boundary === "none") {
            return new Set();
        }
        const index = fields.indexOf(boundary);
        const fallbackIndex = fields.indexOf(defaultBoundary);
        const end = index >= 0 ? index : fallbackIndex;
        return new Set(end >= 0 ? fields.slice(0, end + 1) : []);
    }

    function boundaryFromFields(fields = virtualFrozenFields) {
        const ordered = orderedDataFields();
        let boundary = "none";
        for (const field of ordered) {
            if (!fields.has(field)) {
                break;
            }
            boundary = field;
        }
        return boundary;
    }

    function initializeVirtualFrozenFields() {
        const preferences = readPreferences();
        virtualFrozenFields = fieldsThrough(preferences.frozenThrough || defaultBoundary);
    }

    function persistFrozenBoundary() {
        const boundary = boundaryFromFields();
        const preferences = readPreferences();
        preferences.frozenThrough = boundary;
        writePreferences(preferences);
        const settingsSelect = document.getElementById("journal-frozen-through");
        const ribbonSelect = document.getElementById("ribbon-frozen-through");
        if (settingsSelect) settingsSelect.value = boundary;
        if (ribbonSelect) ribbonSelect.value = boundary;
        root.dataset.stableFrozenThrough = boundary;
    }

    function connectedElement(component) {
        try {
            const element = component?.getElement?.();
            return element instanceof Element && element.isConnected ? element : null;
        } catch (_error) {
            return null;
        }
    }

    function clearStickyStyle(element) {
        if (!element) return;
        element.classList.remove("operator-stable-frozen");
        element.style.position = "relative";
        element.style.left = "auto";
        element.style.right = "auto";
        element.style.zIndex = "";
        element.style.boxShadow = "";
    }

    function setStickyStyle(element, left, zIndex) {
        if (!element) return;
        element.classList.add("operator-stable-frozen");
        element.style.position = "sticky";
        element.style.left = `${Math.round(left)}px`;
        element.style.right = "auto";
        element.style.zIndex = String(zIndex);
    }

    function applyStableFrozenColumns() {
        window.cancelAnimationFrame(stickyFrame);
        stickyFrame = 0;

        const columns = table.getColumns().filter((column) => column.getField());
        const visibleRows = table.getRows("visible");
        const rowHeader = root.querySelector(".journal-row-number");
        let left = rowHeader instanceof Element
            ? rowHeader.getBoundingClientRect().width
            : 46;
        let lastFrozenHeader = null;
        const lastFrozenCells = [];

        for (const column of columns) {
            const field = column.getField();
            const frozen = virtualFrozenFields.has(field);
            const header = connectedElement(column);
            const cells = visibleRows
                .map((row) => connectedElement(row.getCell(field)))
                .filter(Boolean);

            if (frozen) {
                setStickyStyle(header, left, 42);
                cells.forEach((cell) => setStickyStyle(cell, left, 22));
                lastFrozenHeader = header;
                lastFrozenCells.splice(0, lastFrozenCells.length, ...cells);
                left += Number(column.getWidth()) || 0;
            } else {
                clearStickyStyle(header);
                cells.forEach(clearStickyStyle);
            }
        }

        if (lastFrozenHeader) {
            lastFrozenHeader.style.boxShadow = "5px 0 10px rgba(0, 0, 0, 0.18)";
            lastFrozenCells.forEach((cell) => {
                cell.style.boxShadow = "5px 0 10px rgba(0, 0, 0, 0.14)";
            });
        }
        root.dataset.stableFreezeReady = "true";
    }

    function scheduleStableFrozenColumns() {
        window.cancelAnimationFrame(stickyFrame);
        stickyFrame = window.requestAnimationFrame(applyStableFrozenColumns);
    }

    function applyVirtualColumnLayout(layout) {
        if (!Array.isArray(layout)) {
            return;
        }
        virtualFrozenFields = new Set(
            layout
                .filter((column) => column?.field && column.frozen)
                .map((column) => column.field),
        );

        for (const definition of layout) {
            if (!definition?.field) continue;
            const column = table.getColumn(definition.field);
            if (!column) continue;
            const width = Number(definition.width);
            if (Number.isFinite(width) && width > 0 && column.getWidth() !== width) {
                column.setWidth(width);
            }
            if (definition.visible === false) {
                column.hide();
            } else if (definition.visible === true) {
                column.show();
            }
        }

        suppressNextForcedRedraw = true;
        persistFrozenBoundary();
        scheduleStableFrozenColumns();
    }

    function protectDestroyedCellComponents() {
        const sample = table.getRows()?.[0]?.getCells?.()?.[0];
        const prototype = sample ? Object.getPrototypeOf(sample) : null;
        if (!prototype || prototype.__shiftHelperSafeElement === true) {
            return;
        }
        const originalGetElement = prototype.getElement;
        if (typeof originalGetElement !== "function") {
            return;
        }
        Object.defineProperty(prototype, "__shiftHelperSafeElement", {
            configurable: false,
            enumerable: false,
            value: true,
            writable: false,
        });
        prototype.getElement = function getElement() {
            const element = originalGetElement.call(this);
            return element && typeof element.getBoundingClientRect === "function"
                ? element
                : detachedCellElement;
        };
    }

    function loadContextFallback() {
        if (document.getElementById("event-journal-context-fallback-v1")) {
            return;
        }
        const script = document.createElement("script");
        script.id = "event-journal-context-fallback-v1";
        script.src = "/static/event_journal_context_fallback_v1.js";
        document.body.appendChild(script);
    }

    function rowNumberUnderPointer(event) {
        const pathMatch = event.composedPath?.().find(
            (item) => item instanceof Element && item.classList.contains("journal-row-number"),
        );
        if (pathMatch) {
            return pathMatch;
        }
        return document.elementsFromPoint(event.clientX, event.clientY)
            .find((item) => item instanceof Element && item.classList.contains("journal-row-number"))
            || null;
    }

    function preserveRowSelectionOnSecondaryPress(event) {
        if (event.button !== 2 || !rowNumberUnderPointer(event)) {
            return;
        }
        event.stopImmediatePropagation();
    }

    function internalElementReady() {
        return Boolean(
            root.isConnected
            && root.querySelector(".tabulator-tableholder")
            && root.querySelector(".tabulator-table"),
        );
    }

    function flushPending() {
        if (!pending || !ready || !internalElementReady()) {
            return;
        }
        let force = pendingForce;
        pending = false;
        pendingForce = false;
        if (force && suppressNextForcedRedraw) {
            force = false;
            suppressNextForcedRedraw = false;
        }
        window.requestAnimationFrame(() => {
            if (!internalElementReady()) {
                pending = true;
                pendingForce ||= force;
                return;
            }
            originalRedraw(force);
            protectDestroyedCellComponents();
            scheduleStableFrozenColumns();
        });
    }

    initializeVirtualFrozenFields();

    if (originalGetColumnLayout) {
        table.getColumnLayout = () => originalGetColumnLayout().map((column) => (
            column?.field
                ? {...column, frozen: virtualFrozenFields.has(column.field)}
                : {...column}
        ));
    }

    if (originalSetColumnLayout) {
        table.setColumnLayout = (layout) => {
            applyVirtualColumnLayout(layout);
            return Promise.resolve(table.getColumnLayout?.() || layout);
        };
    }

    table.getRows = (range) => {
        if (range === "visible" && (!ready || !internalElementReady())) {
            return [];
        }
        try {
            return originalGetRows(range);
        } catch (error) {
            if (range === "visible" && /visibleRows/.test(String(error))) {
                return [];
            }
            throw error;
        }
    };

    table.redraw = (force = false) => {
        if (!ready || !internalElementReady()) {
            pending = true;
            pendingForce ||= Boolean(force);
            return undefined;
        }
        let effectiveForce = Boolean(force);
        if (effectiveForce && suppressNextForcedRedraw) {
            effectiveForce = false;
            suppressNextForcedRedraw = false;
        }
        const result = originalRedraw(effectiveForce);
        protectDestroyedCellComponents();
        scheduleStableFrozenColumns();
        return result;
    };

    document.addEventListener("pointerdown", preserveRowSelectionOnSecondaryPress, true);
    document.addEventListener("mousedown", preserveRowSelectionOnSecondaryPress, true);

    table.on("tableBuilt", () => {
        ready = true;
        protectDestroyedCellComponents();
        pending = true;
        scheduleStableFrozenColumns();
        flushPending();
    });
    table.on("renderComplete", () => {
        ready = true;
        protectDestroyedCellComponents();
        scheduleStableFrozenColumns();
        flushPending();
    });
    table.on("columnResized", scheduleStableFrozenColumns);
    table.on("columnMoved", scheduleStableFrozenColumns);
    table.on("columnVisibilityChanged", scheduleStableFrozenColumns);

    protectDestroyedCellComponents();
    scheduleStableFrozenColumns();
    window.addEventListener("resize", scheduleStableFrozenColumns);

    if (ready) {
        window.requestAnimationFrame(() => {
            pending = true;
            flushPending();
        });
    }

    if (document.readyState === "complete") {
        window.setTimeout(loadContextFallback, 0);
    } else {
        window.addEventListener("load", () => window.setTimeout(loadContextFallback, 0), {once: true});
    }
})();
