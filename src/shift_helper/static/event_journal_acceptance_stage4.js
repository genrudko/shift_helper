"use strict";

/*
 * Operator acceptance stage 4.
 * Adds authoritative formatting reset, an Excel-like Clear menu, and Find/Replace.
 */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table || root.dataset.acceptanceStage4 === "ready") return;

    const iconUrl = "/static/shift_helper_icons_v1.svg";
    const keys = {
        text: "shift-helper-event-cell-text-style-v1",
        alignment: "shift-helper-event-cell-alignment-v3",
        fills: "shift-helper-event-cell-fill-v3",
        borders: "shift-helper-event-cell-border-v1",
        rules: "shift-helper-event-format-rules-v3",
        resets: "shift-helper-event-format-reset-v1",
    };
    const editableFields = [
        "start_date", "start_time", "asset_label", "description", "reason",
        "actions", "performer", "end_date", "end_time", "author",
    ];
    const defaultAlignment = {
        start_date: {horizontal: "center", vertical: "middle"},
        start_time: {horizontal: "center", vertical: "middle"},
        asset_label: {horizontal: "center", vertical: "middle"},
        description: {horizontal: "left", vertical: "top"},
        reason: {horizontal: "left", vertical: "top"},
        actions: {horizontal: "left", vertical: "top"},
        performer: {horizontal: "left", vertical: "middle"},
        end_date: {horizontal: "center", vertical: "middle"},
        end_time: {horizontal: "center", vertical: "middle"},
        author: {horizontal: "left", vertical: "middle"},
    };
    const verticalMap = {top: "flex-start", middle: "center", bottom: "flex-end"};
    const rowLastKey = new WeakMap();
    let clearMenu = null;
    let lastClearMode = "contents";
    let formatFrame = 0;
    let markFrame = 0;
    let matches = [];
    let matchIds = new Set();
    let currentMatch = -1;
    let currentSignature = "";

    function load(key, fallback) {
        try {
            const raw = localStorage.getItem(key);
            return raw === null ? structuredClone(fallback) : JSON.parse(raw);
        } catch (_error) {
            return structuredClone(fallback);
        }
    }

    function save(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (_error) {
            // Presentation helpers must never block journal input.
        }
    }

    function svg(name) {
        return `<svg class="ribbon-icon" aria-hidden="true"><use href="${iconUrl}#${name}"></use></svg>`;
    }

    function isCell(candidate) {
        return Boolean(
            candidate
            && typeof candidate.getField === "function"
            && typeof candidate.getRow === "function"
            && typeof candidate.getElement === "function",
        );
    }

    function cellId(cell) {
        return `${cell.getRow().getData()._rowKey}\u0000${cell.getField()}`;
    }

    function selectedRows() {
        const keysSet = new Set(window.shiftHelperSelectedRowKeys || []);
        return keysSet.size
            ? table.getRows("active").filter((row) => keysSet.has(row.getData()._rowKey))
            : [];
    }

    function rangeCells() {
        return [...new Set((table.getRanges?.() || []).flatMap((range) => {
            const raw = range.getCells?.() || [];
            return raw.length && Array.isArray(raw[0]) ? raw.flat() : raw;
        }).filter(isCell))];
    }

    function activeCellFromDom() {
        const element = root.querySelector(".journal-active-cell");
        if (!element) return null;
        for (const row of table.getRows("active")) {
            const found = row.getCells().find((cell) => cell.getElement?.() === element);
            if (found) return found;
        }
        return null;
    }

    function selectedCells() {
        const rows = selectedRows();
        if (rows.length) {
            return rows.flatMap((row) => editableFields
                .map((field) => row.getCell(field))
                .filter(isCell));
        }
        const ranged = rangeCells().filter((cell) => editableFields.includes(cell.getField()));
        if (ranged.length) return ranged;
        const active = activeCellFromDom();
        return active && editableFields.includes(active.getField()) ? [active] : [];
    }

    function deleteEntry(store, rowKey, field) {
        if (!store[rowKey]?.[field]) return false;
        delete store[rowKey][field];
        if (!Object.keys(store[rowKey]).length) delete store[rowKey];
        return true;
    }

    function resetEntry(cell, create = false) {
        const resets = load(keys.resets, {});
        const rowKey = cell.getRow().getData()._rowKey;
        const field = cell.getField();
        if (create) {
            resets[rowKey] ||= {};
            resets[rowKey][field] ||= {};
        }
        return {resets, rowKey, field, entry: resets[rowKey]?.[field] || null};
    }

    function setResetCategories(cells, categories, enabled) {
        const resets = load(keys.resets, {});
        cells.forEach((cell) => {
            const rowKey = cell.getRow().getData()._rowKey;
            const field = cell.getField();
            resets[rowKey] ||= {};
            resets[rowKey][field] ||= {};
            categories.forEach((category) => {
                if (enabled) resets[rowKey][field][category] = true;
                else delete resets[rowKey][field][category];
            });
            if (!Object.keys(resets[rowKey][field]).length) delete resets[rowKey][field];
            if (!Object.keys(resets[rowKey]).length) delete resets[rowKey];
        });
        save(keys.resets, resets);
    }

    function purgeResetStores() {
        const resets = load(keys.resets, {});
        const stores = {
            text: load(keys.text, {}),
            alignment: load(keys.alignment, {}),
            fill: load(keys.fills, {}),
            border: load(keys.borders, {}),
        };
        const changed = {text: false, alignment: false, fill: false, border: false};
        Object.entries(resets).forEach(([rowKey, fields]) => {
            Object.entries(fields).forEach(([field, categories]) => {
                Object.keys(categories).forEach((category) => {
                    if (deleteEntry(stores[category], rowKey, field)) changed[category] = true;
                });
            });
        });
        if (changed.text) save(keys.text, stores.text);
        if (changed.alignment) save(keys.alignment, stores.alignment);
        if (changed.fill) save(keys.fills, stores.fill);
        if (changed.border) save(keys.borders, stores.border);
        return stores;
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
        const red = parseInt(hex.slice(0, 2), 16);
        const green = parseInt(hex.slice(2, 4), 16);
        const blue = parseInt(hex.slice(4, 6), 16);
        return (red * 0.299 + green * 0.587 + blue * 0.114) > 155
            ? "#18212a"
            : "#f7fafc";
    }

    function applyBorderLayer(cell, entry) {
        const element = cell.getElement?.();
        if (!element) return;
        let layer = element.querySelector(":scope > .stage3-cell-border-layer");
        if (!entry || !Object.values(entry).some(Boolean)) {
            layer?.remove();
            return;
        }
        if (!layer) {
            layer = document.createElement("span");
            layer.className = "stage3-cell-border-layer";
            element.appendChild(layer);
        }
        const line = "2px solid var(--ribbon-text)";
        layer.style.borderTop = entry.top ? line : "0";
        layer.style.borderRight = entry.right ? line : "0";
        layer.style.borderBottom = entry.bottom ? line : "0";
        layer.style.borderLeft = entry.left ? line : "0";
    }

    function applyFormatting() {
        formatFrame = 0;
        const stores = purgeResetStores();
        const rules = load(keys.rules, []);
        table.getRows("active").forEach((row) => {
            const rowKey = row.getData()._rowKey;
            row.getCells().forEach((cell) => {
                const field = cell.getField();
                if (!field) return;
                const element = cell.getElement?.();
                const value = element?.querySelector(".journal-cell-value");
                if (!element || !value) return;

                const text = stores.text[rowKey]?.[field] || {};
                const alignment = stores.alignment[rowKey]?.[field]
                    || defaultAlignment[field]
                    || {horizontal: "left", vertical: "middle"};
                const manualFill = stores.fill[rowKey]?.[field] || "";
                const ruleFill = rules.find((rule) => ruleMatches(rule, field, cell.getValue()))?.color || "";
                const fill = manualFill || ruleFill;

                if (fill) element.style.setProperty("background-color", fill, "important");
                else element.style.removeProperty("background-color");
                element.style.textAlign = alignment.horizontal || "left";
                element.style.alignItems = verticalMap[alignment.vertical] || "center";
                value.style.textAlign = alignment.horizontal || "left";
                value.style.fontFamily = text.fontFamily || "";
                value.style.fontSize = text.fontSize ? `${text.fontSize}px` : "";
                value.style.fontWeight = text.bold ? "700" : "";
                value.style.fontStyle = text.italic ? "italic" : "";
                value.style.textDecoration = text.underline ? "underline" : "";
                value.style.whiteSpace = text.wrap ? "pre-wrap" : "";
                value.style.overflowWrap = text.wrap ? "anywhere" : "";
                const rotation = Number(text.rotation || 0);
                value.style.transform = rotation ? `rotate(${rotation}deg)` : "";
                value.style.transformOrigin = "center";
                if (text.color) value.style.color = text.color;
                else if (fill) value.style.color = contrast(fill);
                else value.style.removeProperty("color");
                applyBorderLayer(cell, stores.border[rowKey]?.[field] || null);
            });
        });
        window.shiftHelperFrozenColumns?.reapply?.();
    }

    function scheduleFormatting() {
        cancelAnimationFrame(formatFrame);
        formatFrame = requestAnimationFrame(() => requestAnimationFrame(applyFormatting));
    }

    function updateTextProperty(property, rawValue, {toggle = false} = {}) {
        const cells = selectedCells();
        if (!cells.length) return;
        const store = load(keys.text, {});
        setResetCategories(cells, ["text"], false);
        let value = rawValue;
        if (toggle) {
            value = !cells.every((cell) => Boolean(
                store[cell.getRow().getData()._rowKey]?.[cell.getField()]?.[property],
            ));
        }
        cells.forEach((cell) => {
            const rowKey = cell.getRow().getData()._rowKey;
            const field = cell.getField();
            store[rowKey] ||= {};
            store[rowKey][field] ||= {};
            if (value === "" || value === false || value === null || Number.isNaN(value)) {
                delete store[rowKey][field][property];
            } else {
                store[rowKey][field][property] = value;
            }
            if (!Object.keys(store[rowKey][field]).length) delete store[rowKey][field];
            if (!Object.keys(store[rowKey]).length) delete store[rowKey];
        });
        save(keys.text, store);
        scheduleFormatting();
    }

    function updateAlignment(axis, value) {
        const cells = selectedCells();
        if (!cells.length) return;
        const store = load(keys.alignment, {});
        setResetCategories(cells, ["alignment"], false);
        cells.forEach((cell) => {
            const rowKey = cell.getRow().getData()._rowKey;
            const field = cell.getField();
            const fallback = defaultAlignment[field] || {horizontal: "left", vertical: "middle"};
            store[rowKey] ||= {};
            store[rowKey][field] = {
                ...fallback,
                ...(store[rowKey][field] || {}),
                [axis]: value,
            };
        });
        save(keys.alignment, store);
        scheduleFormatting();
    }

    function updateFill(color) {
        const cells = selectedCells();
        if (!cells.length) return;
        const store = load(keys.fills, {});
        setResetCategories(cells, ["fill"], false);
        cells.forEach((cell) => {
            const rowKey = cell.getRow().getData()._rowKey;
            const field = cell.getField();
            if (color) {
                store[rowKey] ||= {};
                store[rowKey][field] = color;
            } else {
                deleteEntry(store, rowKey, field);
            }
        });
        save(keys.fills, store);
        scheduleFormatting();
    }

    function bindAuthoritativeFormatting() {
        window.addEventListener("click", (event) => {
            if (!(event.target instanceof Element)) return;
            const textButton = event.target.closest("[data-text-style]");
            if (textButton) {
                event.preventDefault();
                event.stopImmediatePropagation();
                updateTextProperty(textButton.dataset.textStyle, true, {toggle: true});
                return;
            }
            const wrap = event.target.closest('[data-ribbon-command="wrap"]');
            if (wrap) {
                event.preventDefault();
                event.stopImmediatePropagation();
                updateTextProperty("wrap", true, {toggle: true});
                return;
            }
            const direction = event.target.closest("#operator-text-direction");
            if (direction) {
                event.preventDefault();
                event.stopImmediatePropagation();
                const store = load(keys.text, {});
                const cells = selectedCells();
                const values = [0, -90, 90];
                const current = Number(
                    store[cells[0]?.getRow().getData()._rowKey]?.[cells[0]?.getField()]?.rotation || 0,
                );
                updateTextProperty("rotation", values[(values.indexOf(current) + 1) % values.length]);
                return;
            }
            const horizontal = event.target.closest("[data-align-horizontal]");
            if (horizontal) {
                event.preventDefault();
                event.stopImmediatePropagation();
                updateAlignment("horizontal", horizontal.dataset.alignHorizontal);
                return;
            }
            const vertical = event.target.closest("[data-align-vertical]");
            if (vertical) {
                event.preventDefault();
                event.stopImmediatePropagation();
                updateAlignment("vertical", vertical.dataset.alignVertical);
                return;
            }
            const applyFill = event.target.closest("#apply-cell-fill");
            if (applyFill) {
                event.preventDefault();
                event.stopImmediatePropagation();
                updateFill(document.getElementById("cell-fill-color")?.value || "#fff2cc");
                return;
            }
            const clearFill = event.target.closest("#clear-cell-fill");
            if (clearFill) {
                event.preventDefault();
                event.stopImmediatePropagation();
                updateFill("");
            }
        }, true);

        window.addEventListener("change", (event) => {
            if (!(event.target instanceof Element)) return;
            if (event.target.matches("#ribbon-font-family")) {
                event.preventDefault();
                event.stopImmediatePropagation();
                updateTextProperty("fontFamily", event.target.value);
                return;
            }
            if (event.target.matches("#operator-font-size, #ribbon-font-size")) {
                event.preventDefault();
                event.stopImmediatePropagation();
                updateTextProperty("fontSize", Math.min(200, Math.max(1, Number(event.target.value) || 13)));
                return;
            }
            if (event.target.closest(".journal-mini-toolbar") && event.target instanceof HTMLSelectElement) {
                const title = event.target.title;
                event.preventDefault();
                event.stopImmediatePropagation();
                if (title === "Шрифт") updateTextProperty("fontFamily", event.target.value);
                if (title === "Размер шрифта") updateTextProperty("fontSize", Number(event.target.value));
            }
        }, true);

        window.addEventListener("input", (event) => {
            if (!(event.target instanceof Element)) return;
            if (event.target.matches("#ribbon-text-color")) {
                event.preventDefault();
                event.stopImmediatePropagation();
                updateTextProperty("color", event.target.value);
            }
        }, true);
    }

    function clearCategories(categories) {
        const cells = selectedCells();
        if (!cells.length) return;
        setResetCategories(cells, categories, true);
        purgeResetStores();
        scheduleFormatting();
    }

    function clearContents() {
        document.querySelector('[data-ribbon-command="clear"]')?.dispatchEvent(new MouseEvent("click", {
            bubbles: true,
            cancelable: true,
        }));
    }

    function clearMode(mode) {
        lastClearMode = mode;
        if (mode === "contents") clearContents();
        else if (mode === "formats") clearCategories(["text", "alignment", "fill", "border"]);
        else if (mode === "fill") clearCategories(["fill"]);
        else if (mode === "borders") clearCategories(["border"]);
        else if (mode === "all") {
            clearCategories(["text", "alignment", "fill", "border"]);
            clearContents();
        }
        closeClearMenu();
    }

    function closeClearMenu() {
        clearMenu?.remove();
        clearMenu = null;
        document.getElementById("stage4-clear-arrow")?.setAttribute("aria-expanded", "false");
    }

    function placeFloating(element, anchor) {
        document.body.appendChild(element);
        const anchorRect = anchor.getBoundingClientRect();
        const box = element.getBoundingClientRect();
        element.style.left = `${Math.max(8, Math.min(anchorRect.left, innerWidth - box.width - 8))}px`;
        element.style.top = `${Math.max(8, Math.min(anchorRect.bottom + 4, innerHeight - box.height - 8))}px`;
    }

    function openClearMenu(anchor) {
        closeClearMenu();
        clearMenu = document.createElement("div");
        clearMenu.id = "stage4-clear-menu";
        clearMenu.className = "stage4-clear-menu";
        clearMenu.setAttribute("role", "menu");
        [
            ["all", "Очистить всё"],
            ["formats", "Очистить форматирование"],
            ["contents", "Очистить содержимое"],
            ["fill", "Очистить заливку"],
            ["borders", "Очистить границы"],
        ].forEach(([mode, label]) => {
            const button = document.createElement("button");
            button.type = "button";
            button.dataset.clearMode = mode;
            button.textContent = label;
            button.addEventListener("click", () => clearMode(mode));
            clearMenu.appendChild(button);
        });
        anchor.setAttribute("aria-expanded", "true");
        placeFloating(clearMenu, anchor);
    }

    function buildClearControl() {
        const original = document.querySelector('[data-ribbon-command="clear"]');
        if (!original || document.getElementById("stage4-clear-control")) return;
        original.hidden = true;
        const control = document.createElement("div");
        control.id = "stage4-clear-control";
        control.className = "stage4-clear-control";
        const main = document.createElement("button");
        main.type = "button";
        main.className = "stage4-clear-main";
        main.innerHTML = `${svg("clear")}<span>Очистить</span>`;
        main.title = "Повторить последнюю операцию очистки";
        main.addEventListener("click", () => clearMode(lastClearMode));
        const arrow = document.createElement("button");
        arrow.id = "stage4-clear-arrow";
        arrow.type = "button";
        arrow.className = "stage4-clear-arrow";
        arrow.textContent = "▾";
        arrow.title = "Варианты очистки";
        arrow.setAttribute("aria-haspopup", "menu");
        arrow.setAttribute("aria-expanded", "false");
        arrow.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            if (clearMenu) closeClearMenu();
            else openClearMenu(arrow);
        });
        control.append(main, arrow);
        original.insertAdjacentElement("beforebegin", control);
    }

    function buildFindDialog() {
        if (document.getElementById("stage4-find-dialog")) return;
        const dialog = document.createElement("dialog");
        dialog.id = "stage4-find-dialog";
        dialog.className = "stage4-find-dialog";
        dialog.innerHTML = `
            <form method="dialog" class="stage4-find-panel">
                <header class="stage4-find-header">
                    <div><h2>Найти и заменить</h2><p>Поиск выполняется по реальным данным журнала и черновым строкам.</p></div>
                    <button class="stage4-find-close" value="close" aria-label="Закрыть">×</button>
                </header>
                <div class="stage4-find-fields">
                    <label><span>Найти</span><input id="stage4-find-text" type="text" autocomplete="off"></label>
                    <label><span>Заменить на</span><input id="stage4-replace-text" type="text" autocomplete="off"></label>
                    <label><span>Область поиска</span><select id="stage4-find-scope"><option value="all">Весь журнал</option><option value="column">Текущий столбец</option><option value="selection">Выделение</option></select></label>
                </div>
                <div class="stage4-find-options">
                    <label><input id="stage4-find-case" type="checkbox">Учитывать регистр</label>
                    <label><input id="stage4-find-whole" type="checkbox">Ячейка целиком</label>
                </div>
                <div class="stage4-find-buttons">
                    <button id="stage4-find-prev" type="button">Найти предыдущее</button>
                    <button id="stage4-find-next" type="button">Найти далее</button>
                    <button id="stage4-find-all" type="button">Найти все</button>
                    <button id="stage4-replace-one" type="button">Заменить</button>
                    <button id="stage4-replace-all" type="button">Заменить всё</button>
                </div>
                <output id="stage4-find-status" class="stage4-find-status">Введите текст для поиска.</output>
            </form>
        `;
        document.body.appendChild(dialog);
        dialog.addEventListener("close", clearFindMarks);
        dialog.addEventListener("click", (event) => {
            if (event.target === dialog) dialog.close();
        });
        document.getElementById("stage4-find-prev")?.addEventListener("click", () => findDirection(-1));
        document.getElementById("stage4-find-next")?.addEventListener("click", () => findDirection(1));
        document.getElementById("stage4-find-all")?.addEventListener("click", findAll);
        document.getElementById("stage4-replace-one")?.addEventListener("click", replaceCurrent);
        document.getElementById("stage4-replace-all")?.addEventListener("click", replaceAll);
        ["stage4-find-text", "stage4-replace-text", "stage4-find-scope", "stage4-find-case", "stage4-find-whole"]
            .forEach((id) => document.getElementById(id)?.addEventListener("input", invalidateMatches));
        document.getElementById("stage4-find-text")?.addEventListener("keydown", (event) => {
            if (event.key !== "Enter") return;
            event.preventDefault();
            findDirection(event.shiftKey ? -1 : 1);
        });
    }

    function buildFindRibbonControl() {
        const group = document.querySelector('[data-ribbon-panel="data"] .ribbon-group--search');
        if (!group || document.getElementById("stage4-open-find")) return;
        const actions = document.createElement("div");
        actions.className = "stage4-search-actions";
        const button = document.createElement("button");
        button.id = "stage4-open-find";
        button.type = "button";
        button.className = "ribbon-command stage4-open-find";
        button.innerHTML = `${svg("search")}<span>Найти и заменить</span>`;
        button.title = "Найти и заменить (Ctrl+H)";
        button.addEventListener("click", () => openFindDialog(false));
        actions.appendChild(button);
        group.insertBefore(actions, group.querySelector(".ribbon-group__label"));
    }

    function openFindDialog(replaceFocus = false) {
        const dialog = document.getElementById("stage4-find-dialog");
        if (!(dialog instanceof HTMLDialogElement)) return;
        if (!dialog.open) dialog.showModal();
        const target = document.getElementById(replaceFocus ? "stage4-replace-text" : "stage4-find-text");
        target?.focus();
        target?.select();
    }

    function searchOptions() {
        return {
            query: document.getElementById("stage4-find-text")?.value || "",
            replacement: document.getElementById("stage4-replace-text")?.value || "",
            scope: document.getElementById("stage4-find-scope")?.value || "all",
            caseSensitive: Boolean(document.getElementById("stage4-find-case")?.checked),
            whole: Boolean(document.getElementById("stage4-find-whole")?.checked),
        };
    }

    function currentField() {
        return selectedCells()[0]?.getField() || activeCellFromDom()?.getField() || null;
    }

    function scopedCells(scope) {
        if (scope === "selection") {
            const cells = selectedCells();
            if (cells.length) return cells;
        }
        const field = scope === "column" ? currentField() : null;
        return table.getRows("active").flatMap((row) => editableFields
            .filter((candidate) => !field || candidate === field)
            .map((candidate) => row.getCell(candidate))
            .filter(isCell));
    }

    function valueMatches(value, options) {
        const source = String(value ?? "");
        const query = options.query;
        if (!query) return false;
        const left = options.caseSensitive ? source : source.toLocaleLowerCase("ru");
        const right = options.caseSensitive ? query : query.toLocaleLowerCase("ru");
        return options.whole ? left === right : left.includes(right);
    }

    function signature(options) {
        return JSON.stringify({
            query: options.query,
            scope: options.scope,
            caseSensitive: options.caseSensitive,
            whole: options.whole,
            selection: options.scope === "selection" ? selectedCells().map(cellId) : [],
            field: options.scope === "column" ? currentField() : null,
        });
    }

    function rebuildMatches(force = false) {
        const options = searchOptions();
        const nextSignature = signature(options);
        if (!force && nextSignature === currentSignature) return options;
        currentSignature = nextSignature;
        matches = scopedCells(options.scope).filter((cell) => valueMatches(cell.getValue(), options));
        matchIds = new Set(matches.map(cellId));
        currentMatch = -1;
        scheduleFindMarks();
        return options;
    }

    function invalidateMatches() {
        currentSignature = "";
        currentMatch = -1;
        matches = [];
        matchIds.clear();
        scheduleFindMarks();
        setFindStatus("Параметры поиска изменены.");
    }

    function setFindStatus(message) {
        document.getElementById("stage4-find-status")?.replaceChildren(message);
    }

    function applyFindMarks() {
        markFrame = 0;
        root.querySelectorAll(".stage4-find-match, .stage4-find-current").forEach((element) => {
            element.classList.remove("stage4-find-match", "stage4-find-current");
        });
        table.getRows("active").forEach((row) => row.getCells().forEach((cell) => {
            const element = cell.getElement?.();
            if (!element?.isConnected || !matchIds.has(cellId(cell))) return;
            element.classList.add("stage4-find-match");
        }));
        const current = matches[currentMatch];
        const currentElement = current?.getElement?.();
        if (currentElement?.isConnected) currentElement.classList.add("stage4-find-current");
    }

    function scheduleFindMarks() {
        cancelAnimationFrame(markFrame);
        markFrame = requestAnimationFrame(applyFindMarks);
    }

    function clearFindMarks() {
        matches = [];
        matchIds.clear();
        currentMatch = -1;
        currentSignature = "";
        scheduleFindMarks();
    }

    async function focusMatch(index) {
        if (!matches.length) return;
        currentMatch = ((index % matches.length) + matches.length) % matches.length;
        const cell = matches[currentMatch];
        try { await cell.getRow().scrollTo("center", false); } catch (_error) { /* virtual row */ }
        requestAnimationFrame(() => {
            (table.getRanges?.() || []).forEach((range) => {
                try { range.remove(); } catch (_error) { /* stale range */ }
            });
            try { table.addRange(cell, cell); } catch (_error) { /* filtered cell */ }
            const element = cell.getElement?.();
            element?.scrollIntoView({block: "center", inline: "center"});
            element?.classList.add("journal-active-cell");
            scheduleFindMarks();
        });
        setFindStatus(`Совпадение ${currentMatch + 1} из ${matches.length}.`);
    }

    function findDirection(direction) {
        const options = rebuildMatches();
        if (!options.query) {
            setFindStatus("Введите текст для поиска.");
            return;
        }
        if (!matches.length) {
            setFindStatus("Совпадений не найдено.");
            return;
        }
        void focusMatch(currentMatch + direction);
    }

    function findAll() {
        const options = rebuildMatches(true);
        if (!options.query) {
            setFindStatus("Введите текст для поиска.");
            return;
        }
        scheduleFindMarks();
        setFindStatus(matches.length ? `Найдено ячеек: ${matches.length}.` : "Совпадений не найдено.");
        if (matches.length) void focusMatch(0);
    }

    function escapedRegExp(value) {
        return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }

    function replaceValue(source, options, allOccurrences) {
        if (options.whole) return valueMatches(source, options) ? options.replacement : source;
        const flags = `${allOccurrences ? "g" : ""}${options.caseSensitive ? "" : "i"}`;
        return String(source).replace(new RegExp(escapedRegExp(options.query), flags), options.replacement);
    }

    function replaceCurrent() {
        const options = rebuildMatches();
        if (!options.query || !matches.length) {
            findDirection(1);
            return;
        }
        if (currentMatch < 0) currentMatch = 0;
        const cell = matches[currentMatch];
        const next = replaceValue(String(cell.getValue() ?? ""), options, false);
        cell.setValue(next, true);
        currentSignature = "";
        rebuildMatches(true);
        setFindStatus("Заменено одно совпадение.");
        if (matches.length) void focusMatch(Math.min(currentMatch, matches.length - 1));
    }

    function replaceAll() {
        const options = rebuildMatches(true);
        if (!options.query) {
            setFindStatus("Введите текст для поиска.");
            return;
        }
        let changed = 0;
        table.blockRedraw?.();
        try {
            matches.forEach((cell) => {
                const before = String(cell.getValue() ?? "");
                const after = replaceValue(before, options, true);
                if (before === after) return;
                changed += 1;
                cell.setValue(after, true);
            });
        } finally {
            table.restoreRedraw?.();
        }
        table.redraw?.(false);
        currentSignature = "";
        rebuildMatches(true);
        setFindStatus(changed ? `Заменено ячеек: ${changed}.` : "Совпадений не найдено.");
    }

    function migrateResetKey(row) {
        const current = row.getData()._rowKey;
        const previous = rowLastKey.get(row);
        if (previous && previous !== current) {
            const resets = load(keys.resets, {});
            if (resets[previous]) {
                resets[current] = {...(resets[current] || {}), ...resets[previous]};
                delete resets[previous];
                save(keys.resets, resets);
            }
        }
        rowLastKey.set(row, current);
    }

    window.addEventListener("pointerdown", (event) => {
        if (!(event.target instanceof Element)) return;
        if (clearMenu && !clearMenu.contains(event.target) && !event.target.closest("#stage4-clear-control")) {
            closeClearMenu();
        }
    }, true);

    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeClearMenu();
        if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
        if (event.key.toLocaleLowerCase("ru") === "f") {
            event.preventDefault();
            openFindDialog(false);
        }
        if (event.key.toLocaleLowerCase("ru") === "h") {
            event.preventDefault();
            openFindDialog(true);
        }
    }, true);

    table.on("renderComplete", () => {
        table.getRows("active").forEach(migrateResetKey);
        scheduleFormatting();
        scheduleFindMarks();
    });
    table.on("rowUpdated", (row) => {
        migrateResetKey(row);
        scheduleFormatting();
        scheduleFindMarks();
    });
    table.on("cellEdited", () => {
        currentSignature = "";
        scheduleFormatting();
        scheduleFindMarks();
    });

    buildClearControl();
    buildFindDialog();
    buildFindRibbonControl();
    bindAuthoritativeFormatting();
    table.getRows("active").forEach(migrateResetKey);
    scheduleFormatting();

    window.shiftHelperAcceptanceStage4 = {
        clearMode,
        closeClearMenu,
        openFindDialog,
        findAll,
        replaceAll,
        selectedCells,
        updateTextProperty,
        updateAlignment,
    };
    root.dataset.acceptanceStage4 = "ready";
})();
