"use strict";

/*
 * Early, authoritative bootstrap for the event journal.
 * It owns draft-aware sorting, sheet zoom and mutually exclusive selection modes.
 */

(() => {
    const migrationKey = "shift-helper-grid-persistence-migration-v4";
    if (localStorage.getItem(migrationKey) !== "done") {
        const fragments = ["shift-helper-event-grid-v3", "tabulator-shift-helper-event-grid-v3"];
        const obsolete = [];
        for (let index = 0; index < localStorage.length; index += 1) {
            const key = localStorage.key(index);
            if (key && fragments.some((fragment) => key.includes(fragment))) obsolete.push(key);
        }
        obsolete.forEach((key) => localStorage.removeItem(key));
        localStorage.setItem(migrationKey, "done");
    }

    const zoomMigrationKey = "shift-helper-tabulator-zoom-v2";
    if (localStorage.getItem(zoomMigrationKey) !== "done") {
        localStorage.removeItem("shift-helper-column-base-widths-v1");
        localStorage.setItem(zoomMigrationKey, "done");
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
        if (!TabulatorClass || window.shiftHelperDraftSortBootstrap === "ready") return TabulatorClass;
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
    const widthKey = "shift-helper-column-base-widths-v2";
    const zoomKey = "shift-helper-operator-zoom-v1";
    const colors = [
        "#ffffff", "#f2f2f2", "#d9e1f2", "#dae9f8", "#e2f0d9", "#fff2cc", "#fce4d6", "#f4cccc",
        "#d9d9d9", "#b4c6e7", "#9dc3e6", "#a9d18e", "#ffd966", "#f4b183", "#ea9999", "#d5a6bd",
        "#a6a6a6", "#4472c4", "#5b9bd5", "#70ad47", "#ffc000", "#ed7d31", "#c00000", "#7030a0",
        "#7f7f7f", "#2f5597", "#2e75b6", "#548235", "#bf9000", "#c65911", "#9c0006", "#5f497a",
        "#000000", "#203864", "#1f4e78", "#375623", "#806000", "#843c0c", "#660000", "#3f3151",
    ];

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

    function suppressLegacyBindings(root) {
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
        const originalRootAdd = root.addEventListener;
        root.addEventListener = function addEventListener(type, listener, options) {
            if (type === "pointerdown" || type === "click") return;
            return originalRootAdd.call(this, type, listener, options);
        };
        restorers.push(() => { delete root.addEventListener; });
        const originalWindowAdd = window.addEventListener;
        window.addEventListener = function addEventListener(type, listener, options) {
            if (type === "resize") return;
            return originalWindowAdd.call(this, type, listener, options);
        };
        restorers.push(() => { delete window.addEventListener; });
        return () => restorers.reverse().forEach((restore) => restore());
    }

    function installSelectionController(root, table) {
        if (root.dataset.exclusiveSelection === "ready") return;
        root.dataset.exclusiveSelection = "ready";
        let anchorField = null;

        const hideFillHandle = () => {
            document.querySelectorAll(".journal-fill-handle").forEach((handle) => { handle.hidden = true; });
        };
        const clearActiveMarker = () => {
            root.querySelectorAll(".journal-active-cell").forEach((cell) => cell.classList.remove("journal-active-cell"));
        };
        const clearColumnVisuals = () => {
            root.querySelectorAll(".operator-column-selected").forEach((node) => {
                node.classList.remove("operator-column-selected");
            });
        };
        const clearRanges = () => {
            (table.getRanges?.() || []).forEach((range) => {
                try { range.remove(); } catch (_error) { /* stale range */ }
            });
        };
        const clearRowsThroughWorkspace = (rows, field) => {
            const element = rows[0]?.getCell(field)?.getElement?.();
            if (!(element instanceof Element)) return;
            element.dispatchEvent(new PointerEvent("pointerdown", {
                bubbles: true,
                cancelable: true,
                composed: true,
                button: 0,
                buttons: 1,
            }));
        };
        const leaveColumnMode = () => {
            if (!root.querySelector(".operator-column-selected") && root.dataset.selectionMode !== "columns") return;
            clearColumnVisuals();
            anchorField = null;
            root.dataset.selectionMode = "cells";
        };

        window.addEventListener("pointerdown", (event) => {
            if (!(event.target instanceof Element) || !root.contains(event.target)) return;
            if (event.target.closest(".journal-row-number")) {
                leaveColumnMode();
                clearActiveMarker();
                hideFillHandle();
                root.dataset.selectionMode = "rows";
                return;
            }
            if (event.target.closest(".tabulator-cell")) {
                leaveColumnMode();
                root.dataset.selectionMode = "cells";
            }
        }, true);

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
            clearRowsThroughWorkspace(rows, field);
            clearRanges();
            clearColumnVisuals();
            clearActiveMarker();
            hideFillHandle();

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
                table.getColumn(selectedField)?.getElement?.()?.classList.add("operator-column-selected");
            });
            const settle = () => {
                clearActiveMarker();
                hideFillHandle();
                root.dataset.selectionMode = "columns";
            };
            settle();
            setTimeout(settle, 0);
        }, true);

        table.on("cellClick", () => {
            clearColumnVisuals();
            root.dataset.selectionMode = "cells";
        });
        window.shiftHelperSelection = {leaveColumnMode};
    }

    function installStableZoom(root, table) {
        if (root.dataset.stableZoom === "ready") return;
        root.dataset.stableZoom = "ready";
        root.style.removeProperty("zoom");
        root.style.removeProperty("width");
        root.style.removeProperty("height");
        document.body.style.removeProperty("zoom");
        document.body.style.removeProperty("width");

        const baseMetrics = new Map();
        let currentScale = 1;
        let applying = false;
        let pending = null;
        let frame = 0;

        const initializeMetrics = () => {
            const stored = loadJson(widthKey, {});
            table.getColumns().forEach((column) => {
                const field = column.getField();
                if (!field || baseMetrics.has(field)) return;
                const definition = column.getDefinition?.() || {};
                const storedWidth = Number(stored[field]);
                const width = storedWidth > 0 ? storedWidth : Number(column.getWidth()) || Number(definition.width) || 100;
                const minWidth = Number(definition.minWidth) || Math.min(width, 40);
                baseMetrics.set(field, {width, minWidth});
            });
            saveJson(widthKey, Object.fromEntries(
                [...baseMetrics].map(([field, metric]) => [field, metric.width]),
            ));
        };

        const snapshotRanges = () => (table.getRanges?.() || []).map((range) => {
            const raw = range.getCells?.() || [];
            const cells = (raw.length && Array.isArray(raw[0]) ? raw.flat() : raw).filter(
                (cell) => cell?.getRow && cell?.getField,
            );
            const first = cells[0];
            const last = cells.at(-1);
            return first && last ? {
                firstRow: first.getRow().getData()._rowKey,
                firstField: first.getField(),
                lastRow: last.getRow().getData()._rowKey,
                lastField: last.getField(),
            } : null;
        }).filter(Boolean);
        const clearRanges = () => {
            (table.getRanges?.() || []).forEach((range) => {
                try { range.remove(); } catch (_error) { /* stale range */ }
            });
        };
        const restoreRanges = (snapshots, mode) => {
            if (!snapshots.length) return;
            const rows = new Map(table.getRows("active").map((row) => [row.getData()._rowKey, row]));
            snapshots.forEach((snapshot) => {
                const first = rows.get(snapshot.firstRow)?.getCell(snapshot.firstField);
                const last = rows.get(snapshot.lastRow)?.getCell(snapshot.lastField);
                if (first && last) {
                    try { table.addRange(first, last); } catch (_error) { /* filtered endpoint */ }
                }
            });
            root.dataset.selectionMode = mode;
            if (mode === "columns") {
                snapshots.forEach((snapshot) => {
                    const fields = table.getColumns().map((column) => column.getField()).filter(Boolean);
                    const start = fields.indexOf(snapshot.firstField);
                    const end = fields.indexOf(snapshot.lastField);
                    fields.slice(Math.max(0, start), end + 1).forEach((field) => {
                        table.getColumn(field)?.getElement?.()?.classList.add("operator-column-selected");
                    });
                });
                document.querySelectorAll(".journal-fill-handle").forEach((handle) => { handle.hidden = true; });
            }
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
        const saveView = (value) => {
            const preferences = loadJson(preferenceKey, {});
            preferences.zoom = value;
            saveJson(preferenceKey, preferences);
            saveJson(zoomKey, value);
        };

        const applyZoom = (value) => {
            if (applying) {
                pending = value;
                return;
            }
            applying = true;
            root.dataset.zoomApplying = "true";
            initializeMetrics();
            const scale = value / 100;
            const holder = root.querySelector(".tabulator-tableholder");
            const scrollTop = holder?.scrollTop || 0;
            const scrollLeft = holder?.scrollLeft || 0;
            const selectionMode = root.dataset.selectionMode || "cells";
            const ranges = snapshotRanges();
            clearRanges();
            root.querySelectorAll(".operator-column-selected").forEach((node) => {
                node.classList.remove("operator-column-selected");
            });

            document.documentElement.style.setProperty("--ui-scale-factor", "1");
            const preferences = loadJson(preferenceKey, {});
            const fontSize = Number(preferences.fontSize) || 13;
            document.documentElement.style.setProperty("--journal-font-size", `${Math.max(6, fontSize * scale)}px`);
            document.documentElement.style.setProperty("--journal-row-height", `${Math.max(12, Math.round(34 * scale))}px`);
            document.documentElement.style.setProperty("--journal-control-height", `${Math.max(12, Math.round(30 * scale))}px`);
            document.documentElement.style.setProperty("--journal-toolbar-gap", `${Math.max(2, Math.round(8 * scale))}px`);

            table.blockRedraw?.();
            try {
                table.getColumns().forEach((column) => {
                    const field = column.getField();
                    const metric = baseMetrics.get(field);
                    if (!field || !metric) return;
                    const width = Math.max(12, Math.round(metric.width * scale));
                    const minWidth = Math.max(8, Math.round(metric.minWidth * scale));
                    const definition = column.getDefinition?.();
                    if (definition) definition.minWidth = minWidth;
                    if (column._column) column._column.minWidth = minWidth;
                    column.setWidth(width);
                });
            } finally {
                table.restoreRedraw?.();
            }
            currentScale = scale;
            root.dataset.sheetZoom = String(value);
            syncControls(value);
            table.redraw?.(false);

            requestAnimationFrame(() => {
                if (holder) {
                    holder.scrollTop = scrollTop;
                    holder.scrollLeft = scrollLeft;
                }
                restoreRanges(ranges, selectionMode);
                delete root.dataset.zoomApplying;
                applying = false;
                if (pending !== null && pending !== value) {
                    const next = pending;
                    pending = null;
                    applyZoom(next);
                } else {
                    pending = null;
                }
            });
        };
        const requestZoom = (rawValue, persist = true) => {
            const value = clampZoom(rawValue);
            if (persist) saveView(value);
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(() => applyZoom(value));
        };

        const onInput = (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            requestZoom(event.currentTarget.value);
        };
        ["journal-zoom", "ribbon-zoom"].forEach((id) => {
            const control = document.getElementById(id);
            if (!control) return;
            control.addEventListener("input", onInput, true);
            control.addEventListener("wheel", (event) => {
                event.preventDefault();
                event.stopImmediatePropagation();
                requestZoom(Number(control.value) + (event.deltaY < 0 ? 5 : -5));
            }, {capture: true, passive: false});
        });
        const adjust = (step) => (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            requestZoom(Number(document.getElementById("ribbon-zoom")?.value || 100) + step);
        };
        document.getElementById("ribbon-zoom-out")?.addEventListener("click", adjust(-5), true);
        document.getElementById("ribbon-zoom-in")?.addEventListener("click", adjust(5), true);
        table.on("columnResized", (column) => {
            if (applying) return;
            const field = column?.getField?.();
            const width = Number(column?.getWidth?.());
            if (!field || !(width > 0)) return;
            const metric = baseMetrics.get(field) || {minWidth: 20};
            metric.width = width / Math.max(0.1, currentScale);
            baseMetrics.set(field, metric);
            saveJson(widthKey, Object.fromEntries(
                [...baseMetrics].map(([name, value]) => [name, value.width]),
            ));
        });

        const initial = loadJson(zoomKey, null) ?? loadJson(preferenceKey, {}).zoom ?? 100;
        const value = clampZoom(initial);
        syncControls(value);
        applyZoom(value);
        window.shiftHelperZoom = {apply: requestZoom};
    }

    function installTextColorPalette() {
        if (document.getElementById("operator-text-color-control")) return;
        const input = document.getElementById("ribbon-text-color");
        const label = input?.closest(".ribbon-color-button");
        const row = label?.parentElement;
        if (!input || !label || !row) return;
        label.classList.add("operator-hidden-control");

        const control = document.createElement("div");
        control.id = "operator-text-color-control";
        control.className = "operator-split-control operator-text-color-control";
        const main = document.createElement("button");
        main.type = "button";
        main.className = "operator-fill-main";
        main.innerHTML = '<svg class="ribbon-icon" aria-hidden="true"><use href="/static/shift_helper_icons_v1.svg#font-color"></use></svg><span class="operator-color-line"></span>';
        main.title = "Применить последний цвет текста";
        const arrow = document.createElement("button");
        arrow.type = "button";
        arrow.className = "operator-fill-arrow operator-text-color-arrow";
        arrow.textContent = "▾";
        arrow.title = "Выбрать цвет текста";
        control.append(main, arrow);
        row.insertBefore(control, label);

        const syncLine = () => control.style.setProperty("--operator-fill-color", input.value || "#000000");
        const apply = (color) => {
            input.value = color;
            syncLine();
            input.dispatchEvent(new Event("input", {bubbles: true}));
        };
        syncLine();
        main.addEventListener("click", () => apply(input.value || "#000000"));
        arrow.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            document.querySelectorAll(".operator-color-palette[data-owner='text']").forEach((item) => item.remove());
            const palette = document.createElement("div");
            palette.className = "operator-color-palette";
            palette.dataset.owner = "text";
            colors.forEach((color) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "operator-color-swatch";
                button.style.backgroundColor = color;
                button.title = color;
                button.addEventListener("click", () => {
                    apply(color);
                    palette.remove();
                });
                palette.appendChild(button);
            });
            document.body.appendChild(palette);
            const anchor = arrow.getBoundingClientRect();
            const box = palette.getBoundingClientRect();
            palette.style.left = `${Math.max(8, Math.min(anchor.left, innerWidth - box.width - 8))}px`;
            palette.style.top = `${Math.max(8, Math.min(anchor.bottom + 4, innerHeight - box.height - 8))}px`;
        });
    }

    function loadRepair() {
        if (document.getElementById("event-journal-operator-repair-v1-js")) return;
        const root = document.getElementById("event-journal");
        const table = window.shiftHelperEventGrid;
        if (!root || !table) return;
        const restoreBindings = suppressLegacyBindings(root);
        const originalUpdate = table.updateColumnDefinition?.bind(table);
        if (originalUpdate) {
            table.updateColumnDefinition = (field, definition) => {
                if (
                    window.shiftHelperDraftSortBootstrap === "ready"
                    && typeof definition?.sorter === "function"
                ) return Promise.resolve(table.getColumn(field));
                return originalUpdate(field, definition);
            };
        }
        const finalize = () => {
            if (root.dataset.operatorRepairReady !== "true") {
                requestAnimationFrame(finalize);
                return;
            }
            restoreBindings();
            if (originalUpdate) table.updateColumnDefinition = originalUpdate;
            root.style.removeProperty("zoom");
            root.style.removeProperty("width");
            root.style.removeProperty("height");
            document.body.style.removeProperty("zoom");
            document.body.style.removeProperty("width");
            installSelectionController(root, table);
            installStableZoom(root, table);
            installTextColorPalette();
            root.dataset.videoAcceptanceRepair = "ready";
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
