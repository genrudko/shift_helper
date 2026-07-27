"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const ribbon = document.getElementById("journal-ribbon");
    if (!root || !table || !ribbon || root.dataset.operatorRepair === "ready") return;
    root.dataset.operatorRepair = "ready";

    const ICONS = "/static/shift_helper_icons_v1.svg";
    const KEYS = {
        preferences: "shift-helper-ui-preferences-v1",
        widths: "shift-helper-column-base-widths-v1",
        fills: "shift-helper-event-cell-fill-v3",
        rules: "shift-helper-event-format-rules-v3",
        text: "shift-helper-event-cell-text-style-v1",
        ribbon: "shift-helper-ribbon-state-v1",
        zoom: "shift-helper-operator-zoom-v1",
    };
    const editable = [
        "start_date", "start_time", "asset_label", "description", "reason",
        "actions", "performer", "end_date", "end_time", "author",
    ];
    const dates = new Set(["start_date", "end_date"]);
    const times = new Set(["start_time", "end_time"]);
    const fonts = [
        "Segoe UI", "Aptos", "Calibri", "Arial", "Tahoma", "Verdana", "Georgia",
        "Times New Roman", "Courier New", "Trebuchet MS", "Carlito", "Caladea",
        "Liberation Sans", "Liberation Serif", "Liberation Mono", "DejaVu Sans",
        "DejaVu Serif", "DejaVu Sans Mono", "Noto Sans", "Noto Serif",
        "Noto Sans Mono", "Roboto", "Ubuntu", "Cantarell", "Source Sans 3",
        "Source Serif 4", "Fira Sans", "Fira Code", "PT Sans", "PT Serif",
    ];
    const sizes = [8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72, 96];
    const colors = [
        "#ffffff", "#f2f2f2", "#d9e1f2", "#dae9f8", "#e2f0d9", "#fff2cc", "#fce4d6", "#f4cccc",
        "#d9d9d9", "#b4c6e7", "#9dc3e6", "#a9d18e", "#ffd966", "#f4b183", "#ea9999", "#d5a6bd",
        "#a6a6a6", "#4472c4", "#5b9bd5", "#70ad47", "#ffc000", "#ed7d31", "#c00000", "#7030a0",
        "#7f7f7f", "#2f5597", "#2e75b6", "#548235", "#bf9000", "#c65911", "#9c0006", "#5f497a",
        "#000000", "#203864", "#1f4e78", "#375623", "#806000", "#843c0c", "#660000", "#3f3151",
    ];
    const collator = new Intl.Collator("ru", {numeric: true, sensitivity: "base"});
    let zoomFrame = 0;
    let activeCell = null;
    let columnAnchor = null;
    let pan = null;
    let palette = null;

    const load = (key, fallback) => {
        try {
            const raw = localStorage.getItem(key);
            return raw === null ? structuredClone(fallback) : JSON.parse(raw);
        } catch (_error) {
            return structuredClone(fallback);
        }
    };
    const save = (key, value) => {
        try { localStorage.setItem(key, JSON.stringify(value)); } catch (_error) { /* non-blocking */ }
    };
    const clamp = (value, low, high, fallback) => {
        const number = Number(value);
        return Number.isFinite(number) ? Math.min(high, Math.max(low, number)) : fallback;
    };
    const svg = (name) => `<svg class="ribbon-icon" aria-hidden="true"><use href="${ICONS}#${name}"></use></svg>`;

    function selectedRows() {
        const keys = new Set(window.shiftHelperSelectedRowKeys || []);
        return keys.size ? table.getRows().filter((row) => keys.has(row.getData()._rowKey)) : [];
    }
    function rangeCells() {
        return [...new Set((table.getRanges?.() || []).flatMap((range) => {
            const cells = range.getCells?.() || [];
            return cells.length && Array.isArray(cells[0]) ? cells.flat() : cells;
        }).filter((cell) => cell?.getField))];
    }
    function selectedCells() {
        const rows = selectedRows();
        return rows.length
            ? rows.flatMap((row) => editable.map((field) => row.getCell(field)).filter(Boolean))
            : rangeCells().filter((cell) => editable.includes(cell.getField()));
    }

    function baseWidths() {
        const stored = load(KEYS.widths, {});
        table.getColumns().forEach((column) => {
            const width = Number(stored[column.getField()]);
            if (width > 0) column.setWidth(width);
        });
    }
    function applyZoom(raw, persist = true) {
        const value = clamp(raw, 10, 400, 100);
        const scale = value / 100;
        const preferences = load(KEYS.preferences, {});
        preferences.zoom = value;
        if (persist) {
            save(KEYS.preferences, preferences);
            save(KEYS.zoom, value);
        }
        document.documentElement.style.setProperty("--ui-scale-factor", "1");
        document.documentElement.style.setProperty("--journal-font-size", `${Number(preferences.fontSize) || 13}px`);
        document.documentElement.style.setProperty("--journal-row-height", "34px");
        document.documentElement.style.setProperty("--journal-control-height", "30px");
        document.documentElement.style.setProperty("--journal-toolbar-gap", "8px");
        root.style.zoom = String(scale);
        root.style.width = `${100 / scale}%`;
        root.style.height = `${100 / scale}%`;
        ["journal-zoom", "ribbon-zoom"].forEach((id) => {
            const input = document.getElementById(id);
            if (!input) return;
            input.min = "10";
            input.max = "400";
            input.step = "5";
            input.value = String(value);
        });
        document.getElementById("ribbon-zoom-value")?.replaceChildren(`${value}%`);
        document.getElementById("journal-zoom-value")?.replaceChildren(`${value}%`);
        cancelAnimationFrame(zoomFrame);
        zoomFrame = requestAnimationFrame(() => table.redraw?.(false));
    }
    function bindZoom() {
        baseWidths();
        const initial = load(KEYS.zoom, null) ?? load(KEYS.preferences, {}).zoom ?? 100;
        const input = (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            applyZoom(event.currentTarget.value);
        };
        ["journal-zoom", "ribbon-zoom"].forEach((id) => {
            const control = document.getElementById(id);
            if (!control) return;
            control.min = "10";
            control.max = "400";
            control.step = "5";
            control.addEventListener("input", input, true);
            control.addEventListener("wheel", (event) => {
                event.preventDefault();
                applyZoom(Number(control.value) + (event.deltaY < 0 ? 5 : -5));
            }, {capture: true, passive: false});
        });
        const adjust = (step) => (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            applyZoom(Number(document.getElementById("ribbon-zoom")?.value || 100) + step);
        };
        document.getElementById("ribbon-zoom-out")?.addEventListener("click", adjust(-5), true);
        document.getElementById("ribbon-zoom-in")?.addEventListener("click", adjust(5), true);
        const reassert = () => setTimeout(() => {
            baseWidths();
            applyZoom(document.getElementById("ribbon-zoom")?.value || initial, false);
        }, 0);
        ["journal-theme", "journal-font-size", "journal-font-family", "journal-frozen-through"].forEach((id) => {
            const control = document.getElementById(id);
            control?.addEventListener("change", reassert);
            control?.addEventListener("input", reassert);
        });
        addEventListener("resize", reassert);
        applyZoom(initial, false);
    }

    const parseDate = (value) => {
        const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(String(value || "").trim());
        return match ? new Date(+match[3], +match[2] - 1, +match[1]).getTime() : null;
    };
    const parseTime = (value) => {
        const match = /^(\d{1,2}):(\d{2})$/.exec(String(value || "").trim());
        return match ? (+match[1] * 60) + +match[2] : null;
    };
    function compare(field, a, b, direction) {
        const aBlank = String(a ?? "").trim() === "";
        const bBlank = String(b ?? "").trim() === "";
        if (aBlank !== bBlank) {
            const result = aBlank ? 1 : -1;
            return direction === "desc" ? -result : result;
        }
        if (dates.has(field)) {
            const left = parseDate(a); const right = parseDate(b);
            if (left !== null && right !== null) return left - right;
        }
        if (times.has(field)) {
            const left = parseTime(a); const right = parseTime(b);
            if (left !== null && right !== null) return left - right;
        }
        const left = Number(String(a ?? "").replace(/\s/g, "").replace(",", "."));
        const right = Number(String(b ?? "").replace(/\s/g, "").replace(",", "."));
        if (Number.isFinite(left) && Number.isFinite(right)) return left - right;
        return collator.compare(String(a ?? ""), String(b ?? ""));
    }
    function sorter(field) {
        return (a, b, aRow, bRow, _column, direction) => {
            const aDraft = Boolean(aRow?.getData?.()._draft);
            const bDraft = Boolean(bRow?.getData?.()._draft);
            if (aDraft !== bDraft) {
                const result = aDraft ? 1 : -1;
                return direction === "desc" ? -result : result;
            }
            if (aDraft) return 0;
            const result = compare(field, a, b, direction);
            return result || (Number(aRow?.getData?.().id || 0) - Number(bRow?.getData?.().id || 0));
        };
    }
    async function bindSort() {
        if (!table.updateColumnDefinition) return;
        for (const column of table.getColumns()) {
            const field = column.getField();
            if (field) await table.updateColumnDefinition(field, {sorter: sorter(field)});
        }
        root.dataset.draftAwareSort = "ready";
        table.on("dataSorted", () => {
            const holder = root.querySelector(".tabulator-tableholder");
            if (holder) holder.scrollTop = 0;
        });
    }

    function ruleMatches(rule, field, raw) {
        if (rule.field !== "*" && rule.field !== field) return false;
        const value = String(raw ?? "");
        const normalized = value.toLocaleLowerCase("ru");
        const expected = String(rule.value ?? "").toLocaleLowerCase("ru");
        if (rule.operator === "contains") return normalized.includes(expected);
        if (rule.operator === "equals") return normalized === expected;
        if (rule.operator === "starts") return normalized.startsWith(expected);
        if (rule.operator === "empty") return value.trim() === "";
        if (rule.operator === "nonempty") return value.trim() !== "";
        if (rule.operator === "regex") {
            try { return new RegExp(rule.value, "iu").test(value); } catch (_error) { return false; }
        }
        return false;
    }
    function contrast(color) {
        const hex = String(color || "").replace("#", "");
        if (!/^[0-9a-f]{6}$/i.test(hex)) return "";
        const r = parseInt(hex.slice(0, 2), 16);
        const g = parseInt(hex.slice(2, 4), 16);
        const b = parseInt(hex.slice(4, 6), 16);
        return (r * .299 + g * .587 + b * .114) > 155 ? "#18212a" : "#f7fafc";
    }
    const stores = () => ({fills: load(KEYS.fills, {}), rules: load(KEYS.rules, []), text: load(KEYS.text, {})});
    function applyCell(cell, state = stores()) {
        const element = cell?.getElement?.();
        if (!element) return;
        const data = cell.getRow().getData();
        const fill = state.fills[data._rowKey]?.[cell.getField()]
            || state.rules.find((rule) => ruleMatches(rule, cell.getField(), cell.getValue()))?.color || "";
        if (fill) element.style.setProperty("background-color", fill, "important");
        else element.style.removeProperty("background-color");
        const value = element.querySelector(".journal-cell-value");
        if (!value) return;
        value.style.color = fill ? contrast(fill) : "";
        const rotation = Number(state.text[data._rowKey]?.[cell.getField()]?.rotation || 0);
        value.style.transform = rotation ? `rotate(${rotation}deg)` : "";
        value.style.transformOrigin = "center";
    }
    function applyAll() {
        const state = stores();
        table.getRows().forEach((row) => row.getCells().forEach((cell) => applyCell(cell, state)));
        const hidden = document.getElementById("ribbon-font-size");
        const visible = document.getElementById("operator-font-size");
        if (hidden && visible && document.activeElement !== visible) visible.value = hidden.value || "13";
    }
    const closePalette = () => { palette?.remove(); palette = null; };
    function bindFill() {
        const input = document.getElementById("cell-fill-color");
        const apply = document.getElementById("apply-cell-fill");
        const clear = document.getElementById("clear-cell-fill");
        if (!input || !apply || !clear || document.getElementById("operator-fill-control")) return;
        input.closest(".ribbon-color-button")?.classList.add("operator-hidden-control");
        apply.classList.add("operator-hidden-control");
        clear.classList.add("operator-hidden-control");
        const control = document.createElement("div");
        control.id = "operator-fill-control";
        control.className = "operator-split-control";
        const main = document.createElement("button");
        main.type = "button";
        main.className = "operator-fill-main";
        main.innerHTML = `${svg("fill")}<span class="operator-color-line"></span>`;
        main.title = "Применить последний цвет заливки";
        const arrow = document.createElement("button");
        arrow.type = "button";
        arrow.className = "operator-fill-arrow";
        arrow.textContent = "▾";
        arrow.title = "Выбрать цвет заливки";
        control.append(main, arrow);
        input.closest(".ribbon-button-row")?.insertBefore(control, input.closest(".ribbon-color-button"));
        const line = () => control.style.setProperty("--operator-fill-color", input.value || "#fff2cc");
        line();
        main.addEventListener("click", () => { apply.click(); requestAnimationFrame(applyAll); });
        arrow.addEventListener("click", (event) => {
            event.stopPropagation();
            closePalette();
            palette = document.createElement("div");
            palette.className = "operator-color-palette";
            colors.forEach((color) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "operator-color-swatch";
                button.style.backgroundColor = color;
                button.title = color;
                button.addEventListener("click", () => {
                    input.value = color;
                    line();
                    apply.click();
                    closePalette();
                    requestAnimationFrame(applyAll);
                });
                palette.appendChild(button);
            });
            const none = document.createElement("button");
            none.type = "button";
            none.className = "operator-color-none";
            none.textContent = "Нет заливки";
            none.addEventListener("click", () => { clear.click(); closePalette(); requestAnimationFrame(applyAll); });
            palette.appendChild(none);
            document.body.appendChild(palette);
            const anchor = arrow.getBoundingClientRect();
            const box = palette.getBoundingClientRect();
            palette.style.left = `${Math.max(8, Math.min(anchor.left, innerWidth - box.width - 8))}px`;
            palette.style.top = `${Math.max(8, Math.min(anchor.bottom + 4, innerHeight - box.height - 8))}px`;
        });
        document.addEventListener("pointerdown", (event) => {
            if (palette && event.target instanceof Element && !palette.contains(event.target) && !control.contains(event.target)) closePalette();
        }, true);
    }

    function fillSelect(select, values, fallback) {
        if (!select) return;
        const normalized = values.map(String);
        const current = select.value || String(fallback);
        const existing = [...select.options].map((option) => option.value);
        if (existing.length !== normalized.length || existing.some((value, index) => value !== normalized[index])) {
            select.replaceChildren(...normalized.map((value) => new Option(value, value)));
        }
        select.value = normalized.includes(current) ? current : String(fallback);
    }
    function setFontSize(value) {
        const select = document.getElementById("ribbon-font-size");
        const size = clamp(value, 1, 200, 13);
        if (!select) return;
        if (![...select.options].some((option) => Number(option.value) === size)) select.add(new Option(String(size), String(size)));
        select.value = String(size);
        select.dispatchEvent(new Event("change", {bubbles: true}));
    }
    function bindFonts() {
        fillSelect(document.getElementById("ribbon-font-family"), fonts, "Segoe UI");
        fillSelect(document.getElementById("journal-font-family"), fonts, "Segoe UI");
        const select = document.getElementById("ribbon-font-size");
        if (!select || document.getElementById("operator-font-size")) return;
        fillSelect(select, sizes, 13);
        select.classList.add("operator-hidden-control");
        const input = document.createElement("input");
        input.id = "operator-font-size";
        input.type = "number";
        input.min = "1";
        input.max = "200";
        input.value = select.value || "13";
        input.title = "Размер шрифта — можно ввести вручную";
        const small = document.createElement("button");
        small.type = "button";
        small.className = "ribbon-icon-button";
        small.innerHTML = svg("font-decrease");
        small.title = "Уменьшить размер шрифта";
        const large = document.createElement("button");
        large.type = "button";
        large.className = "ribbon-icon-button";
        large.innerHTML = svg("font-increase");
        large.title = "Увеличить размер шрифта";
        select.parentElement?.append(input, small, large);
        const commit = () => setFontSize(input.value);
        input.addEventListener("change", commit);
        input.addEventListener("keydown", (event) => {
            if (event.key === "Enter") { event.preventDefault(); commit(); input.select(); }
        });
        small.addEventListener("click", () => { input.value = String(clamp(+input.value - 1, 1, 200, 13)); commit(); });
        large.addEventListener("click", () => { input.value = String(clamp(+input.value + 1, 1, 200, 13)); commit(); });
        new MutationObserver(() => document.querySelectorAll(".journal-mini-toolbar").forEach((bar) => {
            const lists = bar.querySelectorAll("select");
            fillSelect(lists[0], fonts, "Segoe UI");
            fillSelect(lists[1], sizes, 13);
        })).observe(document.body, {childList: true, subtree: true});
    }
    function rotate(value) {
        const state = load(KEYS.text, {});
        const cells = selectedCells();
        cells.forEach((cell) => {
            const key = cell.getRow().getData()._rowKey;
            state[key] ||= {};
            state[key][cell.getField()] ||= {};
            if (value) state[key][cell.getField()].rotation = value;
            else delete state[key][cell.getField()].rotation;
        });
        save(KEYS.text, state);
        const current = stores(); current.text = state;
        cells.forEach((cell) => applyCell(cell, current));
    }
    function bindDirection() {
        const group = document.querySelector(".ribbon-group--alignment .ribbon-button-row:last-of-type");
        if (!group || document.getElementById("operator-text-direction")) return;
        const button = document.createElement("button");
        button.id = "operator-text-direction";
        button.type = "button";
        button.className = "ribbon-icon-button";
        button.innerHTML = svg("text-direction");
        button.title = "Направление текста: 0° / −90° / 90°";
        const values = [0, -90, 90];
        let index = 0;
        button.addEventListener("click", () => { index = (index + 1) % values.length; rotate(values[index]); });
        group.appendChild(button);
    }

    function mark(cell) {
        activeCell?.classList.remove("journal-active-cell");
        activeCell = cell?.getElement?.() || null;
        activeCell?.classList.add("journal-active-cell");
    }
    function selectColumns(field, event) {
        const fields = table.getColumns().map((column) => column.getField()).filter(Boolean);
        const target = fields.indexOf(field);
        if (target < 0) return;
        let start = target; let end = target;
        if (event.shiftKey && columnAnchor && fields.includes(columnAnchor)) {
            start = Math.min(fields.indexOf(columnAnchor), target);
            end = Math.max(fields.indexOf(columnAnchor), target);
        } else columnAnchor = field;
        const rows = table.getRows("active");
        if (!rows.length) return;
        (table.getRanges?.() || []).forEach((range) => range.remove());
        table.addRange(rows[0].getCell(fields[start]), rows.at(-1).getCell(fields[end]));
        root.querySelectorAll(".operator-column-selected").forEach((node) => node.classList.remove("operator-column-selected"));
        fields.slice(start, end + 1).forEach((name) => table.getColumn(name)?.getElement?.()?.classList.add("operator-column-selected"));
        root.dataset.selectionMode = "columns";
    }
    function bindColumns() {
        const handler = (event) => {
            if (!(event.target instanceof Element)) return;
            const header = event.target.closest(".tabulator-col[data-field]");
            if (!header || !root.contains(header)) return;
            if (event.target.closest(".tabulator-col-sorter, .tabulator-header-filter, .tabulator-col-resize-handle, input, select, textarea")) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            selectColumns(header.dataset.field, event);
        };
        root.addEventListener("pointerdown", handler, true);
        root.addEventListener("click", handler, true);
    }
    function bindPan() {
        const holder = root.querySelector(".tabulator-tableholder");
        if (!holder || holder.dataset.middlePan === "ready") return;
        holder.dataset.middlePan = "ready";
        holder.addEventListener("pointerdown", (event) => {
            if (event.button !== 1) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            pan = {id: event.pointerId, x: event.clientX, y: event.clientY, left: holder.scrollLeft, top: holder.scrollTop};
            holder.setPointerCapture?.(event.pointerId);
            root.classList.add("operator-middle-panning");
        }, true);
        holder.addEventListener("pointermove", (event) => {
            if (!pan || event.pointerId !== pan.id) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            holder.scrollLeft = pan.left - (event.clientX - pan.x);
            holder.scrollTop = pan.top - (event.clientY - pan.y);
        }, true);
        const finish = (event) => {
            if (!pan || event.pointerId !== pan.id) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            holder.releasePointerCapture?.(event.pointerId);
            pan = null;
            root.classList.remove("operator-middle-panning");
        };
        holder.addEventListener("pointerup", finish, true);
        holder.addEventListener("pointercancel", finish, true);
        holder.addEventListener("auxclick", (event) => {
            if (event.button === 1) { event.preventDefault(); event.stopImmediatePropagation(); }
        }, true);
    }
    function collapse(value) {
        const state = load(KEYS.ribbon, {collapsed: false, activeTab: "home"});
        state.collapsed = value;
        save(KEYS.ribbon, state);
        ribbon.dataset.ribbonState = value ? "collapsed" : "expanded";
        const button = document.getElementById("ribbon-collapse");
        if (button) {
            button.setAttribute("aria-expanded", String(!value));
            button.title = value ? "Развернуть ленту" : "Свернуть ленту";
            button.innerHTML = `${svg(value ? "expand" : "collapse")}<span class="visually-hidden">${value ? "Развернуть ленту" : "Свернуть ленту"}</span>`;
        }
        requestAnimationFrame(() => table.redraw?.(false));
    }
    function bindCollapse() {
        document.getElementById("ribbon-collapse")?.addEventListener("click", (event) => {
            event.preventDefault(); event.stopImmediatePropagation(); collapse(ribbon.dataset.ribbonState !== "collapsed");
        }, true);
        document.querySelector('[data-ribbon-command="collapse"]')?.addEventListener("click", (event) => {
            event.preventDefault(); event.stopImmediatePropagation(); collapse(true);
        }, true);
        document.querySelectorAll("[data-ribbon-tab]").forEach((tab) => tab.addEventListener("dblclick", (event) => {
            event.preventDefault(); event.stopImmediatePropagation(); collapse(ribbon.dataset.ribbonState !== "collapsed");
        }, true));
    }

    async function init() {
        bindZoom();
        bindFonts();
        bindFill();
        bindDirection();
        bindColumns();
        bindCollapse();
        bindPan();
        table.on("cellClick", (_event, cell) => mark(cell));
        table.on("rangeChanged", (range) => {
            const raw = range?.getCells?.() || [];
            mark((raw.length && Array.isArray(raw[0]) ? raw.flat() : raw).at(-1));
        });
        table.on("renderComplete", () => { applyAll(); bindPan(); });
        table.on("rowUpdated", applyAll);
        table.on("cellEdited", applyCell);
        await bindSort();
        applyAll();
        root.dataset.operatorRepairReady = "true";
    }
    void init();
})();
