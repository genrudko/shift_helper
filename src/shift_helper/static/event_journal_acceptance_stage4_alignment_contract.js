"use strict";

/*
 * Final formatting compositor.
 *
 * Stage 4 remains the command owner. This contract is the last DOM renderer:
 * every repaint composes text, alignment, fill and rule formatting from the
 * same persisted snapshot. It also routes the dynamically-created split color
 * controls through that compositor so changing text color cannot erase fill,
 * alignment or font state.
 */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table || root.dataset.stage4AlignmentContract === "ready") return;

    const keys = {
        text: "shift-helper-event-cell-text-style-v1",
        alignment: "shift-helper-event-cell-alignment-v3",
        fill: "shift-helper-event-cell-fill-v3",
        rules: "shift-helper-event-format-rules-v3",
    };
    const defaults = {
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
    let renderFrame = 0;
    let controlFrame = 0;

    function load(key, fallback = {}) {
        try {
            return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
        } catch (_error) {
            return structuredClone(fallback);
        }
    }

    function save(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (_error) {
            // Presentation state must never block journal input.
        }
    }

    function isCell(candidate) {
        return Boolean(
            candidate
            && typeof candidate.getField === "function"
            && typeof candidate.getRow === "function"
            && typeof candidate.getElement === "function",
        );
    }

    function selectedCells() {
        const stage4 = window.shiftHelperAcceptanceStage4?.selectedCells?.() || [];
        if (stage4.length) return stage4.filter(isCell);
        return (window.shiftHelperOperatorRepair?.selectedCells?.() || []).filter(isCell);
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

    function stores() {
        return {
            text: load(keys.text),
            alignment: load(keys.alignment),
            fill: load(keys.fill),
            rules: load(keys.rules, []),
        };
    }

    function applyCell(cell, state) {
        const field = cell.getField();
        if (!field) return;
        const rowKey = cell.getRow().getData()._rowKey;
        const element = cell.getElement?.();
        const value = element?.querySelector(".journal-cell-value");
        if (!element || !value) return;

        const text = state.text[rowKey]?.[field] || {};
        const alignment = state.alignment[rowKey]?.[field]
            || defaults[field]
            || {horizontal: "left", vertical: "middle"};
        const manualFill = state.fill[rowKey]?.[field] || "";
        const ruleFill = state.rules.find(
            (rule) => ruleMatches(rule, field, cell.getValue()),
        )?.color || "";
        const fill = manualFill || ruleFill;

        if (fill) element.style.setProperty("background-color", fill, "important");
        else element.style.removeProperty("background-color");
        element.style.textAlign = alignment.horizontal || "left";
        element.style.alignItems = verticalMap[alignment.vertical] || "center";

        value.dataset.horizontal = alignment.horizontal || "left";
        value.dataset.vertical = alignment.vertical || "middle";
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
    }

    function applyAll() {
        cancelAnimationFrame(renderFrame);
        renderFrame = 0;
        const state = stores();
        table.getRows("active").forEach((row) => {
            row.getCells().forEach((cell) => applyCell(cell, state));
        });
        syncControls();
        window.shiftHelperFrozenColumns?.reapply?.();
    }

    function scheduleApply() {
        cancelAnimationFrame(renderFrame);
        renderFrame = requestAnimationFrame(applyAll);
    }

    function common(cells, read, fallback = null) {
        if (!cells.length) return fallback;
        const values = cells.map(read);
        return values.every((value) => value === values[0]) ? values[0] : null;
    }

    function syncControls() {
        cancelAnimationFrame(controlFrame);
        controlFrame = 0;
        const cells = selectedCells();
        if (!cells.length) return;
        const state = stores();

        const textProperty = (property, fallback) => common(
            cells,
            (cell) => state.text[cell.getRow().getData()._rowKey]?.[cell.getField()]?.[property]
                ?? fallback,
            fallback,
        );
        const alignmentProperty = (axis) => common(cells, (cell) => {
            const field = cell.getField();
            const rowKey = cell.getRow().getData()._rowKey;
            return (
                state.alignment[rowKey]?.[field]
                || defaults[field]
                || {horizontal: "left", vertical: "middle"}
            )[axis];
        });
        const commonFill = common(
            cells,
            (cell) => state.fill[cell.getRow().getData()._rowKey]?.[cell.getField()] || "",
            "",
        );

        document.querySelectorAll("[data-text-style]").forEach((button) => {
            const active = textProperty(button.dataset.textStyle, false) === true;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", String(active));
        });
        const horizontal = alignmentProperty("horizontal");
        const vertical = alignmentProperty("vertical");
        document.querySelectorAll("[data-align-horizontal]").forEach((button) => {
            const active = horizontal !== null && button.dataset.alignHorizontal === horizontal;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", String(active));
        });
        document.querySelectorAll("[data-align-vertical]").forEach((button) => {
            const active = vertical !== null && button.dataset.alignVertical === vertical;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", String(active));
        });

        const family = textProperty("fontFamily", "Segoe UI");
        const size = textProperty("fontSize", 13);
        const familyControl = document.getElementById("ribbon-font-family");
        const sizeControl = document.getElementById("ribbon-font-size");
        if (familyControl && family) familyControl.value = family;
        if (sizeControl && size !== null) sizeControl.value = String(size);

        const textColor = textProperty("color", "");
        const textControl = document.getElementById("operator-text-color-control");
        const fillControl = document.getElementById("operator-fill-control");
        if (textControl && textColor !== null) {
            textControl.style.setProperty("--operator-fill-color", textColor || "#1f2937");
        }
        if (fillControl && commonFill !== null) {
            fillControl.style.setProperty("--operator-fill-color", commonFill || "#fff2cc");
        }
    }

    function scheduleControlSync() {
        cancelAnimationFrame(controlFrame);
        controlFrame = requestAnimationFrame(syncControls);
    }

    function updateColor(owner, color) {
        const cells = selectedCells();
        if (!cells.length) return;
        const storageKey = owner === "text" ? keys.text : keys.fill;
        const store = load(storageKey);

        cells.forEach((cell) => {
            const rowKey = cell.getRow().getData()._rowKey;
            const field = cell.getField();
            store[rowKey] ||= {};
            if (owner === "text") {
                store[rowKey][field] ||= {};
                if (color) store[rowKey][field].color = color;
                else delete store[rowKey][field].color;
                if (!Object.keys(store[rowKey][field]).length) delete store[rowKey][field];
            } else if (color) {
                store[rowKey][field] = color;
            } else {
                delete store[rowKey][field];
            }
            if (!Object.keys(store[rowKey]).length) delete store[rowKey];
        });
        save(storageKey, store);
        applyAll();
    }

    function colorFromControl(control) {
        return control.style.getPropertyValue("--operator-fill-color").trim()
            || (control.dataset.owner === "text" ? "#1f2937" : "#fff2cc");
    }

    window.addEventListener("click", (event) => {
        if (!(event.target instanceof Element)) return;
        const palette = event.target.closest(".operator-color-palette");
        const swatch = event.target.closest(".operator-color-swatch, .operator-color-none");
        if (palette && swatch) {
            event.preventDefault();
            event.stopImmediatePropagation();
            const color = swatch.classList.contains("operator-color-none")
                ? ""
                : swatch.getAttribute("title") || swatch.getAttribute("aria-label") || "";
            updateColor(palette.dataset.owner, color);
            window.shiftHelperOperatorRepair?.closePalette?.();
            return;
        }

        const main = event.target.closest(".operator-split-control .operator-fill-main");
        if (main) {
            event.preventDefault();
            event.stopImmediatePropagation();
            const control = main.closest(".operator-split-control");
            updateColor(control.dataset.owner, colorFromControl(control));
        }
    }, true);

    table.on("renderComplete", scheduleApply);
    table.on("rowUpdated", scheduleApply);
    table.on("cellEdited", scheduleApply);
    table.on("rangeChanged", scheduleControlSync);
    table.on("cellClick", scheduleControlSync);
    window.addEventListener("shifthelper:zoom", scheduleApply, true);

    new MutationObserver(scheduleControlSync).observe(root, {
        attributes: true,
        attributeFilter: ["style", "class", "data-horizontal", "data-vertical"],
        subtree: true,
    });

    window.shiftHelperFormattingContract = {
        apply: applyAll,
        schedule: scheduleApply,
        selectedCells,
        syncControls,
        updateColor,
    };
    scheduleApply();
    root.dataset.stage4AlignmentContract = "ready";
})();
