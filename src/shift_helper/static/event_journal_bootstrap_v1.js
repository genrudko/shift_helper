"use strict";

/*
 * Shift-Helper event journal bootstrap.
 *
 * Ownership contract:
 * - this file owns draft-aware sorting, sheet zoom, row-drag selection and
 *   column selection;
 * - event_journal_viewport_v5.js owns geometry only;
 * - event_journal_operator_repair_v1.js owns Ribbon formatting.
 */

(() => {
    const migrationKey = "shift-helper-grid-persistence-migration-v5";
    if (localStorage.getItem(migrationKey) !== "done") {
        const fragments = [
            "shift-helper-event-grid-v3",
            "tabulator-shift-helper-event-grid-v3",
            "shift-helper-column-base-widths-v1",
            "shift-helper-column-base-widths-v2",
        ];
        const obsolete = [];
        for (let index = 0; index < localStorage.length; index += 1) {
            const key = localStorage.key(index);
            if (key && fragments.some((fragment) => key.includes(fragment))) {
                obsolete.push(key);
            }
        }
        obsolete.forEach((key) => localStorage.removeItem(key));
        localStorage.setItem(migrationKey, "done");
    }
})();

(() => {
    const dateFields = new Set(["start_date", "end_date"]);
    const timeFields = new Set(["start_time", "end_time"]);
    const collator = new Intl.Collator("ru", {numeric: true, sensitivity: "base"});

    const parseDate = (value) => {
        const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(String(value || "").trim());
        return match ? new Date(+match[3], +match[2] - 1, +match[1]).getTime() : null;
    };
    const parseTime = (value) => {
        const match = /^(\d{1,2}):(\d{2})$/.exec(String(value || "").trim());
        return match ? (+match[1] * 60) + +match[2] : null;
    };
    const compareValues = (field, leftValue, rightValue, direction) => {
        const leftBlank = String(leftValue ?? "").trim() === "";
        const rightBlank = String(rightValue ?? "").trim() === "";
        if (leftBlank !== rightBlank) {
            const result = leftBlank ? 1 : -1;
            return direction === "desc" ? -result : result;
        }
        if (dateFields.has(field)) {
            const left = parseDate(leftValue);
            const right = parseDate(rightValue);
            if (left !== null && right !== null) return left - right;
        }
        if (timeFields.has(field)) {
            const left = parseTime(leftValue);
            const right = parseTime(rightValue);
            if (left !== null && right !== null) return left - right;
        }
        const left = Number(String(leftValue ?? "").replace(/\s/g, "").replace(",", "."));
        const right = Number(String(rightValue ?? "").replace(/\s/g, "").replace(",", "."));
        if (Number.isFinite(left) && Number.isFinite(right)) return left - right;
        return collator.compare(String(leftValue ?? ""), String(rightValue ?? ""));
    };

    function install(TabulatorClass) {
        if (!TabulatorClass || window.shiftHelperDraftSortBootstrap === "ready") {
            return TabulatorClass;
        }
        TabulatorClass.extendModule("sort", "sorters", {
            shiftHelperDraft(left, right, leftRow, rightRow, _column, direction, params) {
                const leftData = leftRow.getData();
                const rightData = rightRow.getData();
                const leftDraft = Boolean(leftData._draft);
                const rightDraft = Boolean(rightData._draft);
                if (leftDraft !== rightDraft) {
                    const result = leftDraft ? 1 : -1;
                    return direction === "desc" ? -result : result;
                }
                if (leftDraft) return 0;
                return compareValues(params.field, left, right, direction)
                    || (Number(leftData.id || 0) - Number(rightData.id || 0));
            },
        });

        function ShiftHelperTabulator(element, options = {}) {
            const target = typeof element === "string" ? document.querySelector(element) : element;
            if (target?.id === "event-journal") {
                options.headerSortClickElement = "icon";
                options.renderHorizontal = "basic";
                options.columns = (options.columns || []).map((column) => column.field ? {
                    ...column,
                    sorter: "shiftHelperDraft",
                    sorterParams: {field: column.field},
                } : column);
            }
            return new TabulatorClass(element, options);
        }
        Object.setPrototypeOf(ShiftHelperTabulator, TabulatorClass);
        ShiftHelperTabulator.prototype = TabulatorClass.prototype;
        window.shiftHelperDraftSortBootstrap = "ready";
        return ShiftHelperTabulator;
    }

    if (window.Tabulator) {
        window.Tabulator = install(window.Tabulator);
        return;
    }
    let pending;
    Object.defineProperty(window, "Tabulator", {
        configurable: true,
        get: () => pending,
        set(value) {
            pending = install(value);
            Object.defineProperty(window, "Tabulator", {
                configurable: true,
                writable: true,
                value: pending,
            });
        },
    });
})();

(() => {
    const preferenceKey = "shift-helper-ui-preferences-v1";
    const zoomKey = "shift-helper-operator-zoom-v2";

    const loadJson = (key, fallback) => {
        try {
            const raw = localStorage.getItem(key);
            return raw === null ? structuredClone(fallback) : JSON.parse(raw);
        } catch (_error) {
            return structuredClone(fallback);
        }
    };
    const saveJson = (key, value) => {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (_error) {
            // Presentation preferences must never block journal work.
        }
    };
    const clampZoom = (value) => Math.min(400, Math.max(10, Number(value) || 100));

    function appendStylesheet(id, href) {
        if (document.getElementById(id)) return;
        const stylesheet = document.createElement("link");
        stylesheet.id = id;
        stylesheet.rel = "stylesheet";
        stylesheet.href = href;
        document.head.appendChild(stylesheet);
    }

    function ensureStylesheet() {
        appendStylesheet(
            "event-journal-operator-repair-v1-css",
            "/static/event_journal_operator_repair_v1.css",
        );
        appendStylesheet(
            "event-journal-sheet-zoom-v1-css",
            "/static/event_journal_sheet_zoom_v1.css",
        );
    }

    function ensureSheetLayer(root) {
        let viewport = document.getElementById("journal-sheet-viewport");
        let layer = document.getElementById("journal-sheet-layer");
        if (viewport && layer && layer.contains(root)) return {viewport, layer};

        viewport = document.createElement("div");
        viewport.id = "journal-sheet-viewport";
        viewport.className = "journal-sheet-viewport";
        viewport.setAttribute("aria-label", "Область масштабирования листа");

        layer = document.createElement("div");
        layer.id = "journal-sheet-layer";
        layer.className = "journal-sheet-layer";

        const parent = root.parentElement;
        if (!parent) return {viewport: root, layer: root};
        parent.insertBefore(viewport, root);
        viewport.appendChild(layer);
        layer.appendChild(root);
        root.dataset.sheetViewport = "ready";
        return {viewport, layer};
    }

    function installStableZoom(root, table) {
        if (root.dataset.stableZoom === "ready") return;
        root.dataset.stableZoom = "ready";
        const workspace = root.closest(".journal-workspace") || root;
        const {viewport, layer} = ensureSheetLayer(root);
        let frame = 0;
        let current = 100;

        const clearLegacyZoom = () => {
            document.body.style.removeProperty("zoom");
            document.body.style.removeProperty("width");
            workspace.style.removeProperty("zoom");
            workspace.style.removeProperty("width");
            workspace.style.removeProperty("height");
            workspace.style.removeProperty("transform-origin");
            root.style.removeProperty("zoom");
            root.style.removeProperty("width");
            root.style.removeProperty("height");
            root.style.removeProperty("transform-origin");
        };
        const syncControls = (value) => {
            ["journal-zoom", "ribbon-zoom"].forEach((id) => {
                const control = document.getElementById(id);
                if (!control) return;
                control.min = "10";
                control.max = "400";
                control.step = "5";
                control.value = String(value);
            });
            document.getElementById("journal-zoom-value")?.replaceChildren(`${value}%`);
            document.getElementById("ribbon-zoom-value")?.replaceChildren(`${value}%`);
        };
        const persist = (value) => {
            const preferences = loadJson(preferenceKey, {});
            preferences.zoom = value;
            saveJson(preferenceKey, preferences);
            saveJson(zoomKey, value);
        };
        const apply = (rawValue, shouldPersist = true) => {
            const value = clampZoom(rawValue);
            const scale = value / 100;
            current = value;
            if (shouldPersist) persist(value);
            clearLegacyZoom();
            layer.style.transformOrigin = "top left";
            layer.style.zoom = String(scale);
            layer.style.width = `${100 / scale}%`;
            layer.style.height = `${100 / scale}%`;
            document.documentElement.style.setProperty("--ui-viewport-height", "100vh");
            document.documentElement.style.setProperty("--operator-zoom-scale", String(scale));
            root.dataset.sheetZoom = String(value);
            viewport.dataset.sheetZoom = String(value);
            layer.dataset.sheetZoom = String(value);
            syncControls(value);
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(() => {
                table.redraw?.(false);
                window.dispatchEvent(new CustomEvent("shifthelper:zoom", {
                    detail: {value, scale},
                }));
            });
        };
        const request = (rawValue, shouldPersist = true) => apply(rawValue, shouldPersist);

        const interceptInput = (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            request(event.currentTarget.value);
        };
        ["journal-zoom", "ribbon-zoom"].forEach((id) => {
            const control = document.getElementById(id);
            if (!control) return;
            control.addEventListener("input", interceptInput, true);
            control.addEventListener("wheel", (event) => {
                event.preventDefault();
                event.stopImmediatePropagation();
                request(Number(control.value) + (event.deltaY < 0 ? 5 : -5));
            }, {capture: true, passive: false});
        });

        const adjust = (delta) => (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            request(current + delta);
        };
        document.getElementById("ribbon-zoom-out")?.addEventListener("click", adjust(-5), true);
        document.getElementById("ribbon-zoom-in")?.addEventListener("click", adjust(5), true);

        viewport.addEventListener("wheel", (event) => {
            if (!event.ctrlKey) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            request(current + (event.deltaY < 0 ? 5 : -5));
        }, {capture: true, passive: false});

        const reassert = () => window.setTimeout(() => apply(current, false), 0);
        ["journal-theme", "journal-font-size", "journal-font-family", "journal-frozen-through"]
            .forEach((id) => {
                const control = document.getElementById(id);
                control?.addEventListener("change", reassert);
                control?.addEventListener("input", reassert);
            });
        window.addEventListener("resize", reassert);

        const initial = loadJson(zoomKey, null) ?? loadJson(preferenceKey, {}).zoom ?? 100;
        apply(initial, false);
        window.shiftHelperZoom = {
            apply: request,
            current: () => current,
            layer: () => layer,
            viewport: () => viewport,
        };
    }

    function installRowDrag(root, table) {
        if (root.dataset.rowDragController === "ready") return;
        root.dataset.rowDragController = "ready";
        let drag = null;
        let synthetic = false;

        const rowNumberAtPoint = (x, y) => {
            const target = document.elementFromPoint(x, y);
            return target instanceof Element ? target.closest(".journal-row-number") : null;
        };
        const selectThrough = (rowNumber) => {
            synthetic = true;
            try {
                rowNumber.dispatchEvent(new PointerEvent("pointerdown", {
                    bubbles: true,
                    cancelable: true,
                    composed: true,
                    button: 0,
                    buttons: 1,
                    shiftKey: true,
                }));
            } finally {
                synthetic = false;
            }
        };

        window.addEventListener("pointerdown", (event) => {
            if (synthetic || event.button !== 0 || !(event.target instanceof Element)) return;
            const rowNumber = event.target.closest(".journal-row-number");
            if (!rowNumber || !root.contains(rowNumber)) return;
            drag = {last: rowNumber};
            root.classList.add("operator-row-dragging");
        }, true);

        window.addEventListener("pointermove", (event) => {
            if (!drag || !(event.buttons & 1)) return;
            const rowNumber = rowNumberAtPoint(event.clientX, event.clientY);
            if (rowNumber && rowNumber !== drag.last && root.contains(rowNumber)) {
                drag.last = rowNumber;
                selectThrough(rowNumber);
            }
            const holder = root.querySelector(".tabulator-tableholder");
            if (holder) {
                const rect = holder.getBoundingClientRect();
                const edge = 34;
                if (event.clientY < rect.top + edge) holder.scrollTop -= 20;
                else if (event.clientY > rect.bottom - edge) holder.scrollTop += 20;
            }
            event.preventDefault();
        }, true);

        const finish = () => {
            drag = null;
            root.classList.remove("operator-row-dragging");
        };
        window.addEventListener("pointerup", finish, true);
        window.addEventListener("pointercancel", finish, true);
        table.on("renderComplete", () => {
            if (!drag) return;
            const selected = new Set(window.shiftHelperSelectedRowKeys || []);
            table.getRows().forEach((row) => {
                row.getElement()?.classList.toggle(
                    "journal-row--multi-selected",
                    selected.has(row.getData()._rowKey),
                );
            });
        });
    }

    function installColumnSelection(root, table) {
        if (root.dataset.columnSelectionController === "ready") return;
        root.dataset.columnSelectionController = "ready";
        let anchorField = null;

        root.addEventListener("pointerdown", (event) => {
            if (!(event.target instanceof Element) || event.button !== 0) return;
            const header = event.target.closest(
                ".tabulator-col[tabulator-field], .tabulator-col[data-field]",
            );
            if (!header || !root.contains(header)) return;
            if (event.target.closest(
                ".tabulator-col-sorter, .tabulator-header-filter, "
                + ".tabulator-col-resize-handle, input, select, textarea",
            )) return;

            const field = header.getAttribute("tabulator-field") || header.dataset.field;
            const fields = table.getColumns().map((column) => column.getField()).filter(Boolean);
            const rows = table.getRows("active");
            const targetIndex = fields.indexOf(field);
            if (targetIndex < 0 || !rows.length) return;

            event.preventDefault();
            event.stopImmediatePropagation();
            (table.getRanges?.() || []).forEach((range) => range.remove());
            root.querySelectorAll(".operator-column-selected").forEach((node) => {
                node.classList.remove("operator-column-selected");
            });

            let startIndex = targetIndex;
            let endIndex = targetIndex;
            if (event.shiftKey && anchorField && fields.includes(anchorField)) {
                startIndex = Math.min(fields.indexOf(anchorField), targetIndex);
                endIndex = Math.max(fields.indexOf(anchorField), targetIndex);
            } else {
                anchorField = field;
            }
            const selectedFields = fields.slice(startIndex, endIndex + 1);
            table.addRange(
                rows[0].getCell(selectedFields[0]),
                rows.at(-1).getCell(selectedFields.at(-1)),
            );
            selectedFields.forEach((selectedField) => {
                table.getColumn(selectedField)?.getElement?.()?.classList.add(
                    "operator-column-selected",
                );
            });
            root.dataset.selectionMode = "columns";
            document.querySelectorAll(".journal-fill-handle").forEach((handle) => {
                handle.hidden = true;
            });
        }, true);

        table.on("cellClick", () => {
            root.querySelectorAll(".operator-column-selected").forEach((node) => {
                node.classList.remove("operator-column-selected");
            });
            root.dataset.selectionMode = "cells";
        });
    }

    function loadRepair() {
        ensureStylesheet();
        const root = document.getElementById("event-journal");
        const table = window.shiftHelperEventGrid;
        if (!root || !table) return;

        const finalize = () => {
            if (root.dataset.operatorRepairReady !== "true") {
                requestAnimationFrame(finalize);
                return;
            }
            document.body.style.removeProperty("zoom");
            document.body.style.removeProperty("width");
            const workspace = root.closest(".journal-workspace");
            workspace?.style.removeProperty("zoom");
            workspace?.style.removeProperty("width");
            workspace?.style.removeProperty("height");
            workspace?.style.removeProperty("transform-origin");
            root.style.removeProperty("zoom");
            root.style.removeProperty("width");
            root.style.removeProperty("height");
            installStableZoom(root, table);
            installRowDrag(root, table);
            installColumnSelection(root, table);
            root.dataset.videoAcceptanceRepair = "ready";
        };

        if (document.getElementById("event-journal-operator-repair-v1-js")) {
            finalize();
            return;
        }
        const script = document.createElement("script");
        script.id = "event-journal-operator-repair-v1-js";
        script.src = "/static/event_journal_operator_repair_v1.js";
        script.addEventListener("load", finalize, {once: true});
        document.body.appendChild(script);
    }

    if (document.readyState === "complete") setTimeout(loadRepair, 0);
    else window.addEventListener("load", loadRepair, {once: true});
})();
