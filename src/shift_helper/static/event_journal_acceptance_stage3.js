"use strict";

/*
 * Operator acceptance stage 3.
 * Provides a real font-size combo, consistent Ribbon geometry and the first
 * Excel-like border-formatting command.
 */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table || root.dataset.acceptanceStage3 === "ready") return;

    const fontSizes = [8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72, 96];
    const borderKey = "shift-helper-event-cell-border-v1";
    const editableFields = [
        "start_date", "start_time", "asset_label", "description", "reason",
        "actions", "performer", "end_date", "end_time", "author",
    ];
    let fontMenu = null;
    let borderMenu = null;
    let lastBorderMode = "all";
    let borderFrame = 0;

    function loadBorders() {
        try {
            return JSON.parse(localStorage.getItem(borderKey) || "{}");
        } catch (_error) {
            return {};
        }
    }

    function saveBorders(store) {
        try {
            localStorage.setItem(borderKey, JSON.stringify(store));
        } catch (_error) {
            // Presentation settings must never block journal input.
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

    function rangeCells() {
        const cells = (table.getRanges?.() || []).flatMap((range) => {
            const raw = range.getCells?.() || [];
            return raw.length && Array.isArray(raw[0]) ? raw.flat() : raw;
        });
        return [...new Set(cells.filter(isCell))];
    }

    function activeCellFromDom() {
        const element = root.querySelector(".journal-active-cell");
        if (!element) return null;
        for (const row of table.getRows("active")) {
            const cell = row.getCells().find((candidate) => candidate.getElement?.() === element);
            if (cell) return cell;
        }
        return null;
    }

    function selectedCells() {
        const selectedRows = new Set(window.shiftHelperSelectedRowKeys || []);
        if (selectedRows.size) {
            return table.getRows("active")
                .filter((row) => selectedRows.has(row.getData()._rowKey))
                .flatMap((row) => editableFields.map((field) => row.getCell(field)).filter(isCell));
        }
        const ranged = rangeCells().filter((cell) => editableFields.includes(cell.getField()));
        if (ranged.length) return ranged;
        const active = activeCellFromDom();
        return active && editableFields.includes(active.getField()) ? [active] : [];
    }

    function closeMenus() {
        fontMenu?.remove();
        borderMenu?.remove();
        fontMenu = null;
        borderMenu = null;
        document.getElementById("stage3-font-size-arrow")?.setAttribute("aria-expanded", "false");
        document.getElementById("stage3-border-arrow")?.setAttribute("aria-expanded", "false");
    }

    function placeMenu(menu, anchor) {
        document.body.appendChild(menu);
        const anchorBox = anchor.getBoundingClientRect();
        const menuBox = menu.getBoundingClientRect();
        const left = Math.max(8, Math.min(anchorBox.left, innerWidth - menuBox.width - 8));
        const top = Math.max(8, Math.min(anchorBox.bottom + 4, innerHeight - menuBox.height - 8));
        menu.style.left = `${left}px`;
        menu.style.top = `${top}px`;
    }

    function commitFontSize(value) {
        const input = document.getElementById("operator-font-size");
        if (!input) return;
        input.value = String(Math.min(200, Math.max(1, Number(value) || 13)));
        input.dispatchEvent(new Event("change", {bubbles: true}));
    }

    function openFontMenu(anchor) {
        closeMenus();
        fontMenu = document.createElement("div");
        fontMenu.id = "stage3-font-size-menu";
        fontMenu.className = "stage3-font-size-menu";
        fontMenu.setAttribute("role", "menu");
        const current = Number(document.getElementById("operator-font-size")?.value || 13);
        fontSizes.forEach((size) => {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = String(size);
            button.setAttribute("role", "menuitem");
            button.setAttribute("aria-current", String(size === current));
            button.addEventListener("click", () => {
                commitFontSize(size);
                closeMenus();
            });
            fontMenu.appendChild(button);
        });
        anchor.setAttribute("aria-expanded", "true");
        placeMenu(fontMenu, anchor);
    }

    function buildFontSizeCombo() {
        const select = document.getElementById("ribbon-font-size");
        const input = document.getElementById("operator-font-size");
        const host = input?.parentElement;
        if (!select || !input || !host || document.getElementById("stage3-font-size-arrow")) return;

        const buttons = [...host.querySelectorAll(".ribbon-icon-button")];
        const decrease = buttons.find((button) => button.title.includes("Уменьшить"));
        const increase = buttons.find((button) => button.title.includes("Увеличить"));
        const cluster = document.createElement("div");
        cluster.className = "stage3-font-size-cluster";
        const combo = document.createElement("div");
        combo.className = "stage3-font-size-combo";
        input.classList.add("stage3-font-size-input");
        const arrow = document.createElement("button");
        arrow.id = "stage3-font-size-arrow";
        arrow.type = "button";
        arrow.className = "stage3-font-size-arrow";
        arrow.textContent = "▾";
        arrow.title = "Выбрать размер шрифта";
        arrow.setAttribute("aria-haspopup", "menu");
        arrow.setAttribute("aria-expanded", "false");
        arrow.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            if (fontMenu) closeMenus();
            else openFontMenu(arrow);
        });
        combo.append(input, arrow);
        cluster.append(combo);
        if (decrease) cluster.appendChild(decrease);
        if (increase) cluster.appendChild(increase);
        host.classList.add("stage3-size-host");
        host.appendChild(cluster);
    }

    function applyBorderLayer(cell, entry) {
        const element = cell?.getElement?.();
        if (!element) return;
        element.style.position = "relative";
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

    function applyAllBorders() {
        const store = loadBorders();
        table.getRows("active").forEach((row) => {
            const rowKey = row.getData()._rowKey;
            row.getCells().forEach((cell) => {
                applyBorderLayer(cell, store[rowKey]?.[cell.getField()] || null);
            });
        });
    }

    function scheduleBorders() {
        cancelAnimationFrame(borderFrame);
        borderFrame = requestAnimationFrame(applyAllBorders);
    }

    function applyBorderMode(mode) {
        const cells = selectedCells();
        if (!cells.length) return;
        const rows = table.getRows("active");
        const fields = table.getColumns().map((column) => column.getField()).filter(Boolean);
        const rowIndexes = cells.map((cell) => rows.indexOf(cell.getRow())).filter((index) => index >= 0);
        const columnIndexes = cells.map((cell) => fields.indexOf(cell.getField())).filter((index) => index >= 0);
        const minRow = Math.min(...rowIndexes);
        const maxRow = Math.max(...rowIndexes);
        const minColumn = Math.min(...columnIndexes);
        const maxColumn = Math.max(...columnIndexes);
        const store = loadBorders();

        cells.forEach((cell) => {
            const rowKey = cell.getRow().getData()._rowKey;
            const field = cell.getField();
            const rowIndex = rows.indexOf(cell.getRow());
            const columnIndex = fields.indexOf(field);
            store[rowKey] ||= {};
            if (mode === "none") {
                delete store[rowKey][field];
                if (!Object.keys(store[rowKey]).length) delete store[rowKey];
                return;
            }
            const entry = mode === "all"
                ? {top: true, right: true, bottom: true, left: true}
                : mode === "outside"
                    ? {
                        top: rowIndex === minRow,
                        right: columnIndex === maxColumn,
                        bottom: rowIndex === maxRow,
                        left: columnIndex === minColumn,
                    }
                    : mode === "bottom"
                        ? {top: false, right: false, bottom: true, left: false}
                        : {top: true, right: false, bottom: false, left: false};
            store[rowKey][field] = entry;
        });
        lastBorderMode = mode;
        saveBorders(store);
        applyAllBorders();
    }

    function openBorderMenu(anchor) {
        closeMenus();
        borderMenu = document.createElement("div");
        borderMenu.id = "stage3-border-menu";
        borderMenu.className = "stage3-border-menu";
        borderMenu.setAttribute("role", "menu");
        [
            ["all", "Все границы"],
            ["outside", "Внешняя граница"],
            ["bottom", "Нижняя граница"],
            ["top", "Верхняя граница"],
            ["none", "Убрать границы"],
        ].forEach(([mode, label]) => {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = label;
            button.setAttribute("role", "menuitem");
            button.dataset.borderMode = mode;
            button.addEventListener("click", () => {
                applyBorderMode(mode);
                closeMenus();
            });
            borderMenu.appendChild(button);
        });
        anchor.setAttribute("aria-expanded", "true");
        placeMenu(borderMenu, anchor);
    }

    function buildBorderControl() {
        const row = document.querySelector(".ribbon-group--font .ribbon-button-row");
        if (!row || document.getElementById("stage3-border-control")) return;
        const control = document.createElement("div");
        control.id = "stage3-border-control";
        control.className = "stage3-border-control";
        const main = document.createElement("button");
        main.type = "button";
        main.className = "stage3-border-main";
        main.title = "Применить последние границы";
        main.innerHTML = '<span class="stage3-border-icon" aria-hidden="true"></span>';
        main.addEventListener("click", () => applyBorderMode(lastBorderMode));
        const arrow = document.createElement("button");
        arrow.id = "stage3-border-arrow";
        arrow.type = "button";
        arrow.className = "stage3-border-arrow";
        arrow.textContent = "▾";
        arrow.title = "Границы ячеек";
        arrow.setAttribute("aria-haspopup", "menu");
        arrow.setAttribute("aria-expanded", "false");
        arrow.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            if (borderMenu) closeMenus();
            else openBorderMenu(arrow);
        });
        control.append(main, arrow);
        row.appendChild(control);
    }

    window.addEventListener("pointerdown", (event) => {
        if (!(event.target instanceof Element)) return;
        if (event.target.closest(
            ".stage3-font-size-menu, .stage3-border-menu, "
            + ".stage3-font-size-combo, .stage3-border-control",
        )) return;
        closeMenus();
    }, true);

    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeMenus();
    }, true);

    table.on("renderComplete", scheduleBorders);
    table.on("rowUpdated", scheduleBorders);
    new MutationObserver(scheduleBorders).observe(root, {childList: true, subtree: true});

    buildFontSizeCombo();
    buildBorderControl();
    applyAllBorders();
    window.shiftHelperAcceptanceStage3 = {
        applyBorderMode,
        closeMenus,
    };
    root.dataset.acceptanceStage3 = "ready";
})();
