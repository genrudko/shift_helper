"use strict";

(() => {
    const migrationKey = "shift-helper-grid-persistence-migration-v4";
    if (localStorage.getItem(migrationKey) === "done") return;
    const fragments = ["shift-helper-event-grid-v3", "tabulator-shift-helper-event-grid-v3"];
    const obsolete = [];
    for (let index = 0; index < localStorage.length; index += 1) {
        const key = localStorage.key(index);
        if (key && fragments.some((fragment) => key.includes(fragment))) obsolete.push(key);
    }
    obsolete.forEach((key) => localStorage.removeItem(key));
    localStorage.setItem(migrationKey, "done");
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
    const widthKey = "shift-helper-column-base-widths-v1";
    const zoomKey = "shift-helper-operator-zoom-v1";
    const loadJson = (key, fallback) => {
        try {
            const raw = localStorage.getItem(key);
            return raw === null ? structuredClone(fallback) : JSON.parse(raw);
        } catch (_error) {
            return structuredClone(fallback);
        }
    };
    const saveJson = (key, value) => {
        try { localStorage.setItem(key, JSON.stringify(value)); } catch (_error) { /* non-blocking */ }
    };
    const clampZoom = (value) => Math.min(400, Math.max(10, Number(value) || 100));

    if (!document.getElementById("event-journal-operator-repair-v1-css")) {
        const stylesheet = document.createElement("link");
        stylesheet.id = "event-journal-operator-repair-v1-css";
        stylesheet.rel = "stylesheet";
        stylesheet.href = "/static/event_journal_operator_repair_v1.css";
        document.head.appendChild(stylesheet);
    }

    function bindColumnHeaders(table) {
        const root = document.getElementById("event-journal");
        if (!root || !table || root.dataset.columnHeaderSelection === "ready") return;
        root.dataset.columnHeaderSelection = "ready";
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
            const targetIndex = fields.indexOf(field);
            const rows = table.getRows("active");
            if (targetIndex < 0 || !rows.length) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            let startIndex = targetIndex;
            let endIndex = targetIndex;
            if (event.shiftKey && anchorField && fields.includes(anchorField)) {
                startIndex = Math.min(fields.indexOf(anchorField), targetIndex);
                endIndex = Math.max(fields.indexOf(anchorField), targetIndex);
            } else {
                anchorField = field;
            }
            if (!event.ctrlKey && !event.metaKey) {
                (table.getRanges?.() || []).forEach((range) => range.remove());
                root.querySelectorAll(".operator-column-selected").forEach((node) => {
                    node.classList.remove("operator-column-selected");
                });
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
        }, true);
    }

    function suppressLegacyZoomBindings() {
        const restorers = [];
        const suppressed = new Map([
            ["journal-zoom", new Set(["input", "wheel"])],
            ["ribbon-zoom", new Set(["input", "wheel"])],
            ["ribbon-zoom-out", new Set(["click"])],
            ["ribbon-zoom-in", new Set(["click"])],
            ["journal-theme", new Set(["input", "change"])],
            ["journal-font-size", new Set(["input", "change"])],
            ["journal-font-family", new Set(["input", "change"])],
            ["journal-frozen-through", new Set(["input", "change"])],
        ]);
        suppressed.forEach((types, id) => {
            const control = document.getElementById(id);
            if (!control) return;
            const original = control.addEventListener;
            control.addEventListener = function addEventListener(type, listener, options) {
                if (types.has(type)) return;
                return original.call(this, type, listener, options);
            };
            restorers.push(() => { delete control.addEventListener; });
        });
        const originalWindowAdd = window.addEventListener;
        window.addEventListener = function addEventListener(type, listener, options) {
            if (type === "resize") return;
            return originalWindowAdd.call(this, type, listener, options);
        };
        restorers.push(() => { delete window.addEventListener; });
        return () => restorers.reverse().forEach((restore) => restore());
    }

    function bindStableZoom(table) {
        const root = document.getElementById("event-journal");
        if (!root || !table || root.dataset.stableZoom === "ready") return;
        root.dataset.stableZoom = "ready";
        const baseWidths = new Map(Object.entries(loadJson(widthKey, {})));
        let currentScale = 1;
        let scalingColumns = false;
        let zoomFrame = 0;
        let pendingZoom = 100;

        const initializeBaseWidths = () => {
            table.getColumns().forEach((column) => {
                const field = column.getField();
                if (field && !baseWidths.has(field)) {
                    baseWidths.set(field, column.getWidth() / Math.max(0.1, currentScale));
                }
            });
            saveJson(widthKey, Object.fromEntries(baseWidths));
        };
        const persistZoom = (value) => {
            const preferences = loadJson(preferenceKey, {});
            preferences.zoom = value;
            saveJson(preferenceKey, preferences);
            saveJson(zoomKey, value);
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
        const applyZoom = (rawValue) => {
            const value = clampZoom(rawValue);
            const previousScale = currentScale;
            currentScale = value / 100;
            root.style.removeProperty("zoom");
            root.style.removeProperty("width");
            root.style.removeProperty("height");
            document.documentElement.style.setProperty("--ui-scale-factor", "1");
            const preferences = loadJson(preferenceKey, {});
            const fontSize = Number(preferences.fontSize) || 13;
            document.documentElement.style.setProperty(
                "--journal-font-size",
                `${Math.max(6, fontSize * currentScale)}px`,
            );
            document.documentElement.style.setProperty(
                "--journal-row-height",
                `${Math.max(12, Math.round(34 * currentScale))}px`,
            );
            document.documentElement.style.setProperty(
                "--journal-control-height",
                `${Math.max(12, Math.round(30 * currentScale))}px`,
            );
            document.documentElement.style.setProperty(
                "--journal-toolbar-gap",
                `${Math.max(2, Math.round(8 * currentScale))}px`,
            );
            if (!baseWidths.size) {
                currentScale = previousScale || 1;
                initializeBaseWidths();
                currentScale = value / 100;
            } else {
                initializeBaseWidths();
            }
            scalingColumns = true;
            try {
                table.getColumns().forEach((column) => {
                    const field = column.getField();
                    const base = field ? Number(baseWidths.get(field)) : 0;
                    if (base > 0) column.setWidth(Math.max(12, Math.round(base * currentScale)));
                });
            } finally {
                scalingColumns = false;
            }
            saveJson(widthKey, Object.fromEntries(baseWidths));
            root.dataset.sheetZoom = String(value);
            syncControls(value);
            requestAnimationFrame(() => table.redraw(false));
        };
        const requestZoom = (rawValue, persist = true) => {
            pendingZoom = clampZoom(rawValue);
            if (persist) persistZoom(pendingZoom);
            cancelAnimationFrame(zoomFrame);
            zoomFrame = requestAnimationFrame(() => applyZoom(pendingZoom));
        };
        const inputZoom = (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            requestZoom(event.currentTarget.value);
        };
        ["journal-zoom", "ribbon-zoom"].forEach((id) => {
            const control = document.getElementById(id);
            if (!control) return;
            control.addEventListener("input", inputZoom, true);
            control.addEventListener("wheel", (event) => {
                event.preventDefault();
                event.stopImmediatePropagation();
                requestZoom(Number(control.value) + (event.deltaY < 0 ? 5 : -5));
            }, {capture: true, passive: false});
        });
        const adjust = (step) => (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            const value = Number(document.getElementById("ribbon-zoom")?.value || 100);
            requestZoom(value + step);
        };
        document.getElementById("ribbon-zoom-out")?.addEventListener("click", adjust(-5), true);
        document.getElementById("ribbon-zoom-in")?.addEventListener("click", adjust(5), true);
        const viewPreferenceFields = {
            "journal-theme": ["theme", (value) => value],
            "journal-font-size": ["fontSize", (value) => Number(value)],
            "journal-font-family": ["fontFamily", (value) => value],
            "journal-frozen-through": ["frozenThrough", (value) => value],
        };
        Object.entries(viewPreferenceFields).forEach(([id, [field, normalize]]) => {
            const control = document.getElementById(id);
            const persistAndReapply = () => {
                const preferences = loadJson(preferenceKey, {});
                preferences[field] = normalize(control.value);
                preferences.zoom = pendingZoom;
                saveJson(preferenceKey, preferences);
                setTimeout(() => requestZoom(pendingZoom, false), 0);
            };
            control?.addEventListener("change", persistAndReapply);
            control?.addEventListener("input", persistAndReapply);
        });
        document.getElementById("reset-view-settings")?.addEventListener("click", () => {
            setTimeout(() => {
                baseWidths.clear();
                currentScale = 1;
                requestZoom(100);
            }, 0);
        });
        document.getElementById("reset-grid-layout")?.addEventListener("click", () => {
            setTimeout(() => {
                baseWidths.clear();
                initializeBaseWidths();
                requestZoom(pendingZoom, false);
            }, 40);
        });
        table.on("columnResized", (column) => {
            if (scalingColumns) return;
            const field = column?.getField?.();
            if (!field) return;
            baseWidths.set(field, column.getWidth() / Math.max(0.1, currentScale));
            saveJson(widthKey, Object.fromEntries(baseWidths));
        });
        window.addEventListener("resize", () => {
            setTimeout(() => requestZoom(pendingZoom, false), 0);
        });
        const initial = loadJson(zoomKey, null) ?? loadJson(preferenceKey, {}).zoom ?? 100;
        pendingZoom = clampZoom(initial);
        applyZoom(pendingZoom);
    }

    function loadRepair() {
        if (document.getElementById("event-journal-operator-repair-v1-js")) return;
        const table = window.shiftHelperEventGrid;
        bindColumnHeaders(table);
        const restoreLegacyBindings = suppressLegacyZoomBindings();
        const originalUpdate = table?.updateColumnDefinition?.bind(table);
        if (table && originalUpdate) {
            table.updateColumnDefinition = (field, definition) => {
                if (
                    window.shiftHelperDraftSortBootstrap === "ready"
                    && typeof definition?.sorter === "function"
                ) return Promise.resolve(table.getColumn(field));
                return originalUpdate(field, definition);
            };
        }
        const finalize = () => {
            const root = document.getElementById("event-journal");
            if (root?.dataset.operatorRepairReady !== "true") {
                requestAnimationFrame(finalize);
                return;
            }
            restoreLegacyBindings();
            if (table && originalUpdate) table.updateColumnDefinition = originalUpdate;
            bindStableZoom(table);
        };
        const script = document.createElement("script");
        script.id = "event-journal-operator-repair-v1-js";
        script.src = "/static/event_journal_operator_repair_v1.js";
        script.addEventListener("load", finalize, {once: true});
        document.body.appendChild(script);
    }

    if (document.readyState === "complete") setTimeout(loadRepair, 0);
    else window.addEventListener("load", loadRepair, {once: true});
})();
