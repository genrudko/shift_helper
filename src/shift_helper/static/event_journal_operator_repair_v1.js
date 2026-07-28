"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const ribbon = document.getElementById("journal-ribbon");
    if (!root || !table || !ribbon || root.dataset.operatorRepair === "ready") return;
    root.dataset.operatorRepair = "ready";

    const ICONS = "/static/shift_helper_icons_v1.svg";
    const KEYS = {
        fills: "shift-helper-event-cell-fill-v3",
        rules: "shift-helper-event-format-rules-v3",
        text: "shift-helper-event-cell-text-style-v1",
        alignment: "shift-helper-event-cell-alignment-v3",
        ribbon: "shift-helper-ribbon-state-v1",
    };
    const editable = [
        "start_date", "start_time", "asset_label", "description", "reason",
        "actions", "performer", "end_date", "end_time", "author",
    ];
    const fonts = [
        "Segoe UI", "Aptos", "Calibri", "Arial", "Tahoma", "Verdana", "Georgia",
        "Times New Roman", "Courier New", "Trebuchet MS", "Carlito", "Caladea",
        "Liberation Sans", "Liberation Serif", "Liberation Mono", "DejaVu Sans",
        "DejaVu Serif", "DejaVu Sans Mono", "Noto Sans", "Noto Serif",
        "Noto Sans Mono", "Roboto", "Ubuntu", "Cantarell", "Source Sans 3",
        "Source Serif 4", "Fira Sans", "Fira Code", "PT Sans", "PT Serif",
    ];
    const sizes = [8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 22, 24, 26, 28, 32, 36, 48, 72, 96];
    const colors = [
        "#ffffff", "#f2f2f2", "#d9e1f2", "#dae9f8", "#e2f0d9", "#fff2cc", "#fce4d6", "#f4cccc",
        "#d9d9d9", "#b4c6e7", "#9dc3e6", "#a9d18e", "#ffd966", "#f4b183", "#ea9999", "#d5a6bd",
        "#a6a6a6", "#4472c4", "#5b9bd5", "#70ad47", "#ffc000", "#ed7d31", "#c00000", "#7030a0",
        "#7f7f7f", "#2f5597", "#2e75b6", "#548235", "#bf9000", "#c65911", "#9c0006", "#5f497a",
        "#000000", "#203864", "#1f4e78", "#375623", "#806000", "#843c0c", "#660000", "#3f3151",
    ];

    let palette = null;
    let paletteTrigger = null;
    let activeCell = null;
    let pan = null;

    const load = (key, fallback) => {
        try {
            const raw = localStorage.getItem(key);
            return raw === null ? structuredClone(fallback) : JSON.parse(raw);
        } catch (_error) {
            return structuredClone(fallback);
        }
    };
    const save = (key, value) => {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (_error) {
            // Formatting is optional and must never block operator input.
        }
    };
    const svg = (name) => (
        `<svg class="ribbon-icon" aria-hidden="true"><use href="${ICONS}#${name}"></use></svg>`
    );
    const clamp = (value, low, high, fallback) => {
        const number = Number(value);
        return Number.isFinite(number) ? Math.min(high, Math.max(low, number)) : fallback;
    };

    function selectedRows() {
        const keys = new Set(window.shiftHelperSelectedRowKeys || []);
        return keys.size
            ? table.getRows().filter((row) => keys.has(row.getData()._rowKey))
            : [];
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
    function stores() {
        return {
            fills: load(KEYS.fills, {}),
            rules: load(KEYS.rules, []),
            text: load(KEYS.text, {}),
            alignment: load(KEYS.alignment, {}),
        };
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
            try {
                return new RegExp(rule.value, "iu").test(value);
            } catch (_error) {
                return false;
            }
        }
        return false;
    }
    function contrast(color) {
        const hex = String(color || "").replace("#", "");
        if (!/^[0-9a-f]{6}$/i.test(hex)) return "";
        const red = Number.parseInt(hex.slice(0, 2), 16);
        const green = Number.parseInt(hex.slice(2, 4), 16);
        const blue = Number.parseInt(hex.slice(4, 6), 16);
        return ((red * 0.299) + (green * 0.587) + (blue * 0.114)) > 155
            ? "#18212a"
            : "#f7fafc";
    }
    function applyCell(cell, state = stores()) {
        const element = cell?.getElement?.();
        if (!element) return;
        const data = cell.getRow().getData();
        const field = cell.getField();
        const key = data._rowKey;
        const fill = state.fills[key]?.[field]
            || state.rules.find((rule) => ruleMatches(rule, field, cell.getValue()))?.color
            || "";
        if (fill) element.style.setProperty("background-color", fill, "important");
        else element.style.removeProperty("background-color");

        const value = element.querySelector(".journal-cell-value");
        if (!value) return;
        const style = state.text[key]?.[field] || {};
        const alignment = state.alignment[key]?.[field] || {};
        value.style.fontFamily = style.fontFamily || "";
        value.style.fontSize = style.fontSize ? `${style.fontSize}px` : "";
        value.style.fontWeight = style.bold ? "700" : "";
        value.style.fontStyle = style.italic ? "italic" : "";
        value.style.textDecoration = style.underline ? "underline" : "";
        value.style.whiteSpace = style.wrap ? "pre-wrap" : "";
        value.style.overflowWrap = style.wrap ? "anywhere" : "";
        value.style.color = style.color || (fill ? contrast(fill) : "");
        const rotation = Number(style.rotation || 0);
        value.style.transform = rotation ? `rotate(${rotation}deg)` : "";
        value.style.transformOrigin = "center";
        if (alignment.horizontal) value.dataset.horizontal = alignment.horizontal;
        if (alignment.vertical) value.dataset.vertical = alignment.vertical;
    }
    function applyAll() {
        const state = stores();
        table.getRows().forEach((row) => row.getCells().forEach((cell) => applyCell(cell, state)));
    }
    function updateTextStyle(property, value) {
        const cells = selectedCells();
        if (!cells.length) return;
        const state = load(KEYS.text, {});
        cells.forEach((cell) => {
            const key = cell.getRow().getData()._rowKey;
            state[key] ||= {};
            state[key][cell.getField()] ||= {};
            if (value === "" || value === false || value === null) {
                delete state[key][cell.getField()][property];
            } else {
                state[key][cell.getField()][property] = value;
            }
        });
        save(KEYS.text, state);
        const current = stores();
        current.text = state;
        cells.forEach((cell) => applyCell(cell, current));
    }
    function updateFill(color) {
        const cells = selectedCells();
        if (!cells.length) return;
        const state = load(KEYS.fills, {});
        cells.forEach((cell) => {
            const key = cell.getRow().getData()._rowKey;
            state[key] ||= {};
            if (color) state[key][cell.getField()] = color;
            else {
                delete state[key][cell.getField()];
                if (!Object.keys(state[key]).length) delete state[key];
            }
        });
        save(KEYS.fills, state);
        const current = stores();
        current.fills = state;
        cells.forEach((cell) => applyCell(cell, current));
    }
    function updateAlignment(axis, alignmentValue) {
        const cells = selectedCells();
        if (!cells.length) return;
        const state = load(KEYS.alignment, {});
        cells.forEach((cell) => {
            const key = cell.getRow().getData()._rowKey;
            state[key] ||= {};
            state[key][cell.getField()] ||= {};
            state[key][cell.getField()][axis] = alignmentValue;
        });
        save(KEYS.alignment, state);
        const current = stores();
        current.alignment = state;
        cells.forEach((cell) => applyCell(cell, current));
        const saveState = document.getElementById("journal-save-state");
        const saveText = saveState?.querySelector(".save-state__text");
        if (saveState && saveText) {
            saveState.dataset.state = "saved";
            saveText.textContent = "Выравнивание сохранено";
        }
    }

    function closePalette({restoreFocus = false} = {}) {
        palette?.remove();
        palette = null;
        if (paletteTrigger) {
            paletteTrigger.setAttribute("aria-expanded", "false");
            if (restoreFocus) paletteTrigger.focus({preventScroll: true});
        }
        paletteTrigger = null;
    }
    function openPalette(trigger, owner, currentColor, applyColor, clearLabel) {
        if (palette && paletteTrigger === trigger) {
            closePalette({restoreFocus: true});
            return;
        }
        closePalette();
        paletteTrigger = trigger;
        trigger.setAttribute("aria-expanded", "true");
        palette = document.createElement("div");
        palette.className = "operator-color-palette";
        palette.dataset.owner = owner;
        palette.setAttribute("role", "menu");
        palette.setAttribute("aria-label", owner === "text" ? "Цвет текста" : "Цвет заливки");

        colors.forEach((color) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "operator-color-swatch";
            button.style.backgroundColor = color;
            button.title = color;
            button.setAttribute("aria-label", color);
            button.setAttribute("role", "menuitem");
            if (color.toLowerCase() === String(currentColor || "").toLowerCase()) {
                button.classList.add("is-current");
            }
            button.addEventListener("click", () => {
                applyColor(color);
                closePalette({restoreFocus: true});
            });
            palette.appendChild(button);
        });

        const none = document.createElement("button");
        none.type = "button";
        none.className = "operator-color-none";
        none.textContent = clearLabel;
        none.setAttribute("role", "menuitem");
        none.addEventListener("click", () => {
            applyColor("");
            closePalette({restoreFocus: true});
        });
        palette.appendChild(none);
        document.body.appendChild(palette);

        const anchor = trigger.getBoundingClientRect();
        const box = palette.getBoundingClientRect();
        palette.style.left = `${Math.max(8, Math.min(anchor.left, innerWidth - box.width - 8))}px`;
        palette.style.top = `${Math.max(8, Math.min(anchor.bottom + 4, innerHeight - box.height - 8))}px`;
        palette.querySelector("button")?.focus({preventScroll: true});
    }
    function makeSplitControl({id, icon, owner, defaultColor, title, clearLabel, applyColor}) {
        const control = document.createElement("div");
        control.id = id;
        control.className = "operator-split-control";
        control.dataset.owner = owner;
        control.style.setProperty("--operator-fill-color", defaultColor);

        const main = document.createElement("button");
        main.type = "button";
        main.className = "operator-fill-main";
        main.innerHTML = `${svg(icon)}<span class="operator-color-line"></span>`;
        main.title = `Применить последний ${title.toLocaleLowerCase("ru")}`;

        const arrow = document.createElement("button");
        arrow.type = "button";
        arrow.className = "operator-fill-arrow";
        arrow.textContent = "▾";
        arrow.title = title;
        arrow.setAttribute("aria-haspopup", "menu");
        arrow.setAttribute("aria-expanded", "false");

        let current = defaultColor;
        main.addEventListener("click", () => applyColor(current));
        arrow.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            openPalette(arrow, owner, current, (color) => {
                if (color) {
                    current = color;
                    control.style.setProperty("--operator-fill-color", color);
                }
                applyColor(color);
            }, clearLabel);
        });
        control.append(main, arrow);
        return control;
    }
    function bindPalettes() {
        const textInput = document.getElementById("ribbon-text-color");
        const textLabel = textInput?.closest(".ribbon-color-button");
        const fillInput = document.getElementById("cell-fill-color");
        const fillLabel = fillInput?.closest(".ribbon-color-button");
        const fillApply = document.getElementById("apply-cell-fill");
        const fillClear = document.getElementById("clear-cell-fill");
        const row = textLabel?.parentElement || fillLabel?.parentElement;
        if (!row || document.getElementById("operator-text-color-control")) return;

        textLabel?.classList.add("operator-hidden-control");
        fillLabel?.classList.add("operator-hidden-control");
        fillApply?.classList.add("operator-hidden-control");
        fillClear?.classList.add("operator-hidden-control");

        const textControl = makeSplitControl({
            id: "operator-text-color-control",
            icon: "font-color",
            owner: "text",
            defaultColor: textInput?.value || "#1f2937",
            title: "Выбрать цвет текста",
            clearLabel: "Автоматический цвет",
            applyColor: (color) => updateTextStyle("color", color),
        });
        const fillControl = makeSplitControl({
            id: "operator-fill-control",
            icon: "fill",
            owner: "fill",
            defaultColor: fillInput?.value || "#fff2cc",
            title: "Выбрать цвет заливки",
            clearLabel: "Нет заливки",
            applyColor: updateFill,
        });
        row.insertBefore(textControl, textLabel || row.firstChild);
        row.insertBefore(fillControl, fillLabel || row.firstChild);

        document.addEventListener("pointerdown", (event) => {
            if (
                palette
                && event.target instanceof Element
                && !palette.contains(event.target)
                && !event.target.closest(".operator-split-control")
            ) {
                closePalette();
            }
        }, true);
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && palette) {
                event.preventDefault();
                event.stopImmediatePropagation();
                closePalette({restoreFocus: true});
            }
        }, true);
        window.addEventListener("resize", () => closePalette());
        root.addEventListener("scroll", () => closePalette(), true);
    }

    function fillSelect(select, values, fallback) {
        if (!select) return;
        const normalized = values.map(String);
        const current = select.value || String(fallback);
        select.replaceChildren(...normalized.map((value) => new Option(value, value)));
        select.value = normalized.includes(current) ? current : String(fallback);
    }
    function setFontSize(value) {
        const select = document.getElementById("ribbon-font-size");
        if (!select) return;
        const size = clamp(value, 1, 200, 13);
        if (![...select.options].some((option) => Number(option.value) === size)) {
            select.add(new Option(String(size), String(size)));
        }
        select.value = String(size);
        select.dispatchEvent(new Event("change", {bubbles: true}));
    }
    function bindFonts() {
        fillSelect(document.getElementById("ribbon-font-family"), fonts, "Segoe UI");
        fillSelect(document.getElementById("journal-font-family"), fonts, "Segoe UI");
        const select = document.getElementById("ribbon-font-size");
        if (!select || document.getElementById("operator-font-decrease")) return;
        fillSelect(select, sizes, 13);
        select.classList.remove("operator-hidden-control");
        select.title = "Размер шрифта";
        select.setAttribute("aria-label", "Размер шрифта");

        const decrease = document.createElement("button");
        decrease.id = "operator-font-decrease";
        decrease.type = "button";
        decrease.className = "ribbon-icon-button operator-font-step";
        decrease.innerHTML = svg("font-decrease");
        decrease.title = "Уменьшить размер шрифта";

        const increase = document.createElement("button");
        increase.id = "operator-font-increase";
        increase.type = "button";
        increase.className = "ribbon-icon-button operator-font-step";
        increase.innerHTML = svg("font-increase");
        increase.title = "Увеличить размер шрифта";

        select.closest(".ribbon-font-row")?.append(decrease, increase);
        decrease.addEventListener("click", () => setFontSize(Number(select.value || 13) - 1));
        increase.addEventListener("click", () => setFontSize(Number(select.value || 13) + 1));

        const observer = new MutationObserver(() => {
            document.querySelectorAll(".journal-mini-toolbar").forEach((bar) => {
                const lists = bar.querySelectorAll("select");
                fillSelect(lists[0], fonts, "Segoe UI");
                fillSelect(lists[1], sizes, 13);
            });
        });
        observer.observe(document.body, {childList: true, subtree: true});
    }

    function bindAlignment() {
        document.addEventListener("click", (event) => {
            if (!(event.target instanceof Element)) return;
            const horizontal = event.target.closest("[data-align-horizontal]");
            const vertical = event.target.closest("[data-align-vertical]");
            if (!horizontal && !vertical) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            if (horizontal) updateAlignment("horizontal", horizontal.dataset.alignHorizontal);
            if (vertical) updateAlignment("vertical", vertical.dataset.alignVertical);
        }, true);
    }
    function bindDirection() {
        const group = document.querySelector(
            ".ribbon-group--alignment .ribbon-button-row:last-of-type",
        );
        if (!group || document.getElementById("operator-text-direction")) return;
        const button = document.createElement("button");
        button.id = "operator-text-direction";
        button.type = "button";
        button.className = "ribbon-icon-button";
        button.innerHTML = svg("text-direction");
        button.title = "Направление текста: 0° / −90° / 90°";
        const values = [0, -90, 90];
        let index = 0;
        button.addEventListener("click", () => {
            index = (index + 1) % values.length;
            updateTextStyle("rotation", values[index]);
        });
        group.appendChild(button);
    }
    function mark(cell) {
        activeCell?.classList.remove("journal-active-cell");
        activeCell = cell?.getElement?.() || null;
        activeCell?.classList.add("journal-active-cell");
    }
    function bindPan() {
        const holder = root.querySelector(".tabulator-tableholder");
        if (!holder || holder.dataset.middlePan === "ready") return;
        holder.dataset.middlePan = "ready";
        holder.addEventListener("pointerdown", (event) => {
            if (event.button !== 1) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            pan = {
                id: event.pointerId,
                x: event.clientX,
                y: event.clientY,
                left: holder.scrollLeft,
                top: holder.scrollTop,
            };
            holder.setPointerCapture?.(event.pointerId);
            root.classList.add("operator-middle-panning");
        }, true);
        holder.addEventListener("pointermove", (event) => {
            if (!pan || event.pointerId !== pan.id) return;
            event.preventDefault();
            holder.scrollLeft = pan.left - (event.clientX - pan.x);
            holder.scrollTop = pan.top - (event.clientY - pan.y);
        }, true);
        const finish = (event) => {
            if (!pan || event.pointerId !== pan.id) return;
            holder.releasePointerCapture?.(event.pointerId);
            pan = null;
            root.classList.remove("operator-middle-panning");
        };
        holder.addEventListener("pointerup", finish, true);
        holder.addEventListener("pointercancel", finish, true);
        holder.addEventListener("auxclick", (event) => {
            if (event.button === 1) event.preventDefault();
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
            button.innerHTML = `${svg(value ? "expand" : "collapse")}<span class="visually-hidden">${
                value ? "Развернуть ленту" : "Свернуть ленту"
            }</span>`;
        }
        requestAnimationFrame(() => table.redraw?.(false));
    }
    function bindCollapse() {
        document.getElementById("ribbon-collapse")?.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopImmediatePropagation();
            collapse(ribbon.dataset.ribbonState === "expanded");
        }, true);
        document.querySelector('[data-ribbon-command="collapse"]')?.addEventListener(
            "click",
            (event) => {
                event.preventDefault();
                event.stopImmediatePropagation();
                collapse(true);
            },
            true,
        );
        document.querySelectorAll("[data-ribbon-tab]").forEach((tab) => {
            tab.addEventListener("dblclick", (event) => {
                event.preventDefault();
                event.stopImmediatePropagation();
                collapse(ribbon.dataset.ribbonState === "expanded");
            }, true);
        });
    }

    function init() {
        bindFonts();
        bindPalettes();
        bindAlignment();
        bindDirection();
        bindCollapse();
        bindPan();
        table.on("cellClick", (_event, cell) => mark(cell));
        table.on("rangeChanged", (range) => {
            const raw = range?.getCells?.() || [];
            mark((raw.length && Array.isArray(raw[0]) ? raw.flat() : raw).at(-1));
        });
        table.on("renderComplete", () => {
            applyAll();
            bindPan();
        });
        table.on("rowUpdated", applyAll);
        table.on("cellEdited", (cell) => applyCell(cell));
        applyAll();
        window.shiftHelperOperatorRepair = {
            applyAll,
            closePalette,
            selectedCells,
            updateAlignment,
        };
        root.dataset.operatorRepairReady = "true";
    }

    init();
})();
