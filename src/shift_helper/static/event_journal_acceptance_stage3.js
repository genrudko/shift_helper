"use strict";

/*
 * Acceptance stage 3 now owns borders only.
 * Font controls and Ribbon geometry are authoritative in operator_repair_v1.
 */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table || root.dataset.acceptanceStage3 === "ready") return;

    const borderKey = "shift-helper-event-cell-border-v1";
    let borderMenu = null;
    let lastBorderMode = "all";
    let borderFrame = 0;

    const loadBorders = () => {
        try {
            return JSON.parse(localStorage.getItem(borderKey) || "{}");
        } catch (_error) {
            return {};
        }
    };
    const saveBorders = (store) => {
        try {
            localStorage.setItem(borderKey, JSON.stringify(store));
        } catch (_error) {
            // Presentation settings must never block journal input.
        }
    };
    const selectedCells = () => window.shiftHelperOperatorRepair?.selectedCells?.() || [];

    function closeMenus() {
        borderMenu?.remove();
        borderMenu = null;
        document.getElementById("stage3-border-arrow")?.setAttribute(
            "aria-expanded",
            "false",
        );
    }
    function placeMenu(menu, anchor) {
        document.body.appendChild(menu);
        const anchorBox = anchor.getBoundingClientRect();
        const menuBox = menu.getBoundingClientRect();
        menu.style.left = `${Math.max(8, Math.min(
            anchorBox.left,
            innerWidth - menuBox.width - 8,
        ))}px`;
        menu.style.top = `${Math.max(8, Math.min(
            anchorBox.bottom + 4,
            innerHeight - menuBox.height - 8,
        ))}px`;
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
        const rowIndexes = cells
            .map((cell) => rows.indexOf(cell.getRow()))
            .filter((index) => index >= 0);
        const columnIndexes = cells
            .map((cell) => fields.indexOf(cell.getField()))
            .filter((index) => index >= 0);
        if (!rowIndexes.length || !columnIndexes.length) return;
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
            let entry;
            if (mode === "all") {
                entry = {top: true, right: true, bottom: true, left: true};
            } else if (mode === "outside") {
                entry = {
                    top: rowIndex === minRow,
                    right: columnIndex === maxColumn,
                    bottom: rowIndex === maxRow,
                    left: columnIndex === minColumn,
                };
            } else if (mode === "bottom") {
                entry = {top: false, right: false, bottom: true, left: false};
            } else {
                entry = {top: true, right: false, bottom: false, left: false};
            }
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
        if (event.target.closest(".stage3-border-menu, .stage3-border-control")) return;
        closeMenus();
    }, true);
    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeMenus();
    }, true);
    window.addEventListener("shifthelper:zoom", scheduleBorders);
    table.on("renderComplete", scheduleBorders);
    table.on("rowUpdated", scheduleBorders);

    buildBorderControl();
    applyAllBorders();
    window.shiftHelperAcceptanceStage3 = {applyBorderMode, closeMenus};
    root.dataset.acceptanceStage3 = "ready";
})();
