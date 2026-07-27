"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const ribbon = document.getElementById("journal-ribbon");
    const saveState = document.getElementById("journal-save-state");
    const saveText = saveState?.querySelector(".save-state__text");
    const selectionSummary = document.getElementById("journal-selection-summary");
    const filterIndicator = document.getElementById("journal-active-filters");
    const filterIndicatorText = document.getElementById("journal-active-filters-text");

    if (!root || !table || !ribbon || !saveState || !saveText) {
        return;
    }

    const iconUrl = "/static/shift_helper_icons_v1.svg";
    const editableFields = [
        "start_date",
        "start_time",
        "asset_label",
        "description",
        "reason",
        "actions",
        "performer",
        "end_date",
        "end_time",
        "author",
    ];
    const ribbonKey = "shift-helper-ribbon-state-v1";
    const textStyleKey = "shift-helper-event-cell-text-style-v1";
    const baseSavedMessage = "Все изменения сохранены";
    const styleStore = loadJson(textStyleKey, {});
    const rowLastKey = new WeakMap();
    let ribbonState = loadJson(ribbonKey, {collapsed: false, activeTab: "home"});
    let floatingMenu = null;
    let transientTimer = 0;
    let internalClipboard = "";
    let guardingInvisibleState = false;

    function loadJson(key, fallback) {
        try {
            const raw = window.localStorage.getItem(key);
            return raw === null ? structuredClone(fallback) : {
                ...structuredClone(fallback),
                ...JSON.parse(raw),
            };
        } catch (_error) {
            return structuredClone(fallback);
        }
    }

    function saveJson(key, value) {
        try {
            window.localStorage.setItem(key, JSON.stringify(value));
        } catch (_error) {
            // Local presentation preferences must never block journal work.
        }
    }

    function svg(name) {
        return `<svg class="ribbon-icon" aria-hidden="true"><use href="${iconUrl}#${name}"></use></svg>`;
    }

    function allRows() {
        return table.getRows();
    }

    function selectedRowKeys() {
        return new Set(window.shiftHelperSelectedRowKeys || []);
    }

    function selectedRows() {
        const keys = selectedRowKeys();
        return keys.size
            ? allRows().filter((row) => keys.has(row.getData()._rowKey))
            : [];
    }

    function isCell(candidate) {
        return Boolean(
            candidate
            && typeof candidate.getField === "function"
            && typeof candidate.getRow === "function"
            && typeof candidate.getElement === "function",
        );
    }

    function cellFromElement(element) {
        const cellElement = element?.closest?.(".tabulator-cell");
        if (!cellElement) {
            return null;
        }
        for (const row of table.getRows("active")) {
            const cell = row.getCells().find((candidate) => candidate.getElement() === cellElement);
            if (cell) {
                return cell;
            }
        }
        return null;
    }

    function rowFromElement(element) {
        const rowElement = element?.closest?.(".tabulator-row");
        return rowElement
            ? allRows().find((row) => row.getElement() === rowElement) || null
            : null;
    }

    function rangeCells() {
        const range = table.getRanges?.().at(-1);
        const raw = range?.getCells?.() || [];
        const flat = raw.length && Array.isArray(raw[0]) ? raw.flat() : raw;
        return [...new Set(flat.filter(isCell))];
    }

    function selectedCells() {
        const rows = selectedRows();
        if (rows.length) {
            return rows.flatMap((row) => editableFields
                .map((field) => row.getCell(field))
                .filter(isCell));
        }
        return rangeCells().filter((cell) => editableFields.includes(cell.getField()));
    }

    function selectSingleCell(cell) {
        if (!isCell(cell) || !editableFields.includes(cell.getField())) {
            return;
        }
        const current = rangeCells();
        if (current.includes(cell)) {
            return;
        }
        (table.getRanges?.() || []).forEach((range) => range.remove());
        table.addRange(cell, cell);
        cell.getElement().click();
    }

    function formatName(field) {
        return {
            start_date: "Дата останова",
            start_time: "Время останова",
            asset_label: "Оборудование",
            description: "Описание",
            reason: "Причина",
            actions: "Действия",
            performer: "Исполнитель",
            end_date: "Дата пуска",
            end_time: "Время пуска",
            author: "Автор",
        }[field] || field;
    }

    function syncSelectionState() {
        const rows = selectedRows();
        const cells = selectedCells();
        const rowMode = rows.length > 0;
        root.dataset.selectionMode = rowMode ? "rows" : "cells";
        dedupeFillHandles();

        if (selectionSummary) {
            if (rowMode) {
                selectionSummary.textContent = `Выбрано строк: ${rows.length}`;
            } else if (cells.length > 1) {
                selectionSummary.textContent = `Выбрано ячеек: ${cells.length}`;
            } else if (cells.length === 1) {
                selectionSummary.textContent = `Ячейка: ${formatName(cells[0].getField())}`;
            } else {
                selectionSummary.textContent = "Выделение отсутствует";
            }
        }
        syncFontControls();
    }

    function dedupeFillHandles() {
        const handles = [...document.querySelectorAll(".journal-fill-handle")];
        handles.slice(1).forEach((handle) => handle.remove());
        const handle = handles[0];
        if (handle && selectedRows().length) {
            handle.hidden = true;
        }
    }

    function styleEntry(cell, create = false) {
        const key = cell.getRow().getData()._rowKey;
        const field = cell.getField();
        if (create) {
            styleStore[key] ||= {};
            styleStore[key][field] ||= {};
        }
        return styleStore[key]?.[field] || null;
    }

    function applyStyleToCell(cell) {
        if (!isCell(cell)) {
            return;
        }
        const value = cell.getElement()?.querySelector(".journal-cell-value");
        if (!value) {
            return;
        }
        const style = styleEntry(cell) || {};
        value.style.fontFamily = style.fontFamily || "";
        value.style.fontSize = style.fontSize ? `${style.fontSize}px` : "";
        value.style.fontWeight = style.bold ? "700" : "";
        value.style.fontStyle = style.italic ? "italic" : "";
        value.style.textDecoration = style.underline ? "underline" : "";
        if (style.color) {
            value.style.color = style.color;
        }
        value.style.whiteSpace = style.wrap ? "pre-wrap" : "";
        value.style.overflowWrap = style.wrap ? "anywhere" : "";
    }

    function applyAllTextStyles() {
        window.requestAnimationFrame(() => {
            allRows().forEach((row) => row.getCells().forEach(applyStyleToCell));
        });
    }

    function migrateStyleKey(row) {
        const current = row.getData()._rowKey;
        const previous = rowLastKey.get(row);
        if (previous && previous !== current && styleStore[previous]) {
            styleStore[current] = {
                ...(styleStore[current] || {}),
                ...styleStore[previous],
            };
            delete styleStore[previous];
            saveJson(textStyleKey, styleStore);
        }
        rowLastKey.set(row, current);
    }

    function commonStyle(property, fallback = "") {
        const cells = selectedCells();
        if (!cells.length) {
            return fallback;
        }
        const values = cells.map((cell) => styleEntry(cell)?.[property] ?? fallback);
        return values.every((value) => value === values[0]) ? values[0] : null;
    }

    function applyTextStyle(property, value, {toggle = false} = {}) {
        const cells = selectedCells();
        if (!cells.length) {
            return;
        }
        let next = value;
        if (toggle) {
            next = !cells.every((cell) => Boolean(styleEntry(cell)?.[property]));
        }
        cells.forEach((cell) => {
            const entry = styleEntry(cell, true);
            if (next === "" || next === false || next === null) {
                delete entry[property];
            } else {
                entry[property] = next;
            }
            applyStyleToCell(cell);
        });
        saveJson(textStyleKey, styleStore);
        syncFontControls();
    }

    function syncFontControls() {
        const family = document.getElementById("ribbon-font-family");
        const size = document.getElementById("ribbon-font-size");
        const commonFamily = commonStyle("fontFamily", "Segoe UI");
        const commonSize = commonStyle("fontSize", 13);
        if (family && commonFamily) {
            family.value = commonFamily;
        }
        if (size && commonSize) {
            size.value = String(commonSize);
        }
        document.querySelectorAll("[data-text-style]").forEach((button) => {
            const property = button.dataset.textStyle;
            const active = commonStyle(property, false) === true;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", String(active));
        });
    }

    function dispatchClipboardEvent(type, text = "") {
        const transfer = new DataTransfer();
        if (text) {
            transfer.setData("text/plain", text);
        }
        const event = new ClipboardEvent(type, {
            bubbles: true,
            cancelable: true,
            clipboardData: transfer,
        });
        document.dispatchEvent(event);
        return transfer.getData("text/plain");
    }

    async function copySelection(cut = false) {
        const text = dispatchClipboardEvent(cut ? "cut" : "copy");
        if (!text) {
            return;
        }
        internalClipboard = text;
        try {
            await navigator.clipboard.writeText(text);
        } catch (_error) {
            // The application clipboard remains available.
        }
    }

    async function pasteSelection() {
        let text = internalClipboard;
        try {
            text = await navigator.clipboard.readText() || text;
        } catch (_error) {
            // Use the last copied application value.
        }
        if (text) {
            internalClipboard = text;
            dispatchClipboardEvent("paste", text);
        }
    }

    function dispatchKey(key, options = {}) {
        document.dispatchEvent(new KeyboardEvent("keydown", {
            key,
            bubbles: true,
            cancelable: true,
            ...options,
        }));
    }

    function clearSelection() {
        dispatchKey("Delete");
    }

    function fillSelection(direction) {
        dispatchKey(direction === "down" ? "d" : "r", {ctrlKey: true});
    }

    function clearAllFilters() {
        document.querySelector('[data-status-filter="all"]')?.click();
        const search = document.getElementById("journal-search");
        if (search) {
            search.value = "";
            search.dispatchEvent(new Event("input", {bubbles: true}));
        }
        table.clearHeaderFilter?.();
        syncFilterIndicator();
    }

    function activeFilterDescriptions() {
        const descriptions = [];
        const status = document.querySelector('[data-status-filter][aria-pressed="true"]');
        if (status?.dataset.statusFilter && status.dataset.statusFilter !== "all") {
            descriptions.push(status.textContent.trim());
        }
        const search = document.getElementById("journal-search")?.value.trim();
        if (search) {
            descriptions.push(`Поиск: «${search}»`);
        }
        const headerFilters = table.getHeaderFilters?.() || [];
        if (headerFilters.length) {
            descriptions.push(`Фильтры колонок: ${headerFilters.length}`);
        }
        return descriptions;
    }

    function syncFilterIndicator() {
        if (!filterIndicator || !filterIndicatorText) {
            return;
        }
        const descriptions = activeFilterDescriptions();
        filterIndicator.hidden = descriptions.length === 0;
        filterIndicatorText.textContent = descriptions.length
            ? `Активны фильтры: ${descriptions.join(" · ")}`
            : "Активны фильтры";
    }

    function guardInvisibleData() {
        if (guardingInvisibleState) {
            return;
        }
        const persisted = table.getData().filter((row) => !row._draft).length;
        const visible = table.getRows("active")
            .filter((row) => !row.getData()._draft).length;
        if (!persisted || visible || activeFilterDescriptions().length) {
            return;
        }
        guardingInvisibleState = true;
        table.clearHeaderFilter?.();
        table.clearSort?.();
        document.querySelector('[data-status-filter="all"]')?.click();
        const search = document.getElementById("journal-search");
        if (search) {
            search.value = "";
            search.dispatchEvent(new Event("input", {bubbles: true}));
        }
        document.getElementById("reset-grid-layout")?.click();
        window.setTimeout(() => {
            guardingInvisibleState = false;
            syncFilterIndicator();
        }, 200);
    }

    function scheduleSavedMessageReset() {
        window.clearTimeout(transientTimer);
        const message = saveText.textContent.trim();
        if (saveState.dataset.state !== "saved" || message === baseSavedMessage) {
            return;
        }
        transientTimer = window.setTimeout(() => {
            if (saveState.dataset.state === "saved" && saveText.textContent.trim() === message) {
                saveText.textContent = baseSavedMessage;
            }
        }, 2600);
    }

    function activateTab(name, temporary = false) {
        const target = ["home", "data", "view"].includes(name) ? name : "home";
        ribbonState.activeTab = target;
        saveJson(ribbonKey, ribbonState);
        document.querySelectorAll("[data-ribbon-tab]").forEach((button) => {
            button.setAttribute("aria-selected", String(button.dataset.ribbonTab === target));
        });
        document.querySelectorAll("[data-ribbon-panel]").forEach((panel) => {
            panel.hidden = panel.dataset.ribbonPanel !== target;
        });
        if (temporary) {
            ribbon.dataset.ribbonState = "temporary";
        }
    }

    function setRibbonCollapsed(collapsed) {
        ribbonState.collapsed = collapsed;
        saveJson(ribbonKey, ribbonState);
        ribbon.dataset.ribbonState = collapsed ? "collapsed" : "expanded";
        const button = document.getElementById("ribbon-collapse");
        if (button) {
            button.setAttribute("aria-expanded", String(!collapsed));
            button.title = collapsed ? "Развернуть ленту" : "Свернуть ленту";
            button.innerHTML = `${svg(collapsed ? "expand" : "collapse")}<span class="visually-hidden">${
                collapsed ? "Развернуть ленту" : "Свернуть ленту"
            }</span>`;
        }
        table.redraw?.(true);
    }

    function closeTemporaryRibbon() {
        if (ribbon.dataset.ribbonState === "temporary") {
            ribbon.dataset.ribbonState = "collapsed";
        }
    }

    function closeFloatingMenu() {
        floatingMenu?.remove();
        floatingMenu = null;
    }

    function contextButton(label, iconName, action, options = {}) {
        const button = document.createElement("button");
        button.type = "button";
        button.innerHTML = `${svg(iconName)}<span>${label}</span>`;
        button.disabled = Boolean(options.disabled);
        button.classList.toggle("is-danger", Boolean(options.danger));
        button.addEventListener("click", () => {
            closeFloatingMenu();
            void action();
        });
        return button;
    }

    function contextSeparator() {
        const separator = document.createElement("div");
        separator.className = "journal-context-separator";
        return separator;
    }

    function buildMiniToolbar() {
        const bar = document.createElement("div");
        bar.className = "journal-mini-toolbar";

        const family = document.createElement("select");
        ["Segoe UI", "Arial", "Tahoma", "Verdana", "Georgia"].forEach((value) => {
            family.add(new Option(value, value));
        });
        family.value = commonStyle("fontFamily", "Segoe UI") || "Segoe UI";
        family.title = "Шрифт";
        family.addEventListener("change", () => applyTextStyle("fontFamily", family.value));

        const size = document.createElement("select");
        [10, 11, 12, 13, 14, 16, 18, 20].forEach((value) => {
            size.add(new Option(String(value), String(value)));
        });
        size.value = String(commonStyle("fontSize", 13) || 13);
        size.title = "Размер шрифта";
        size.addEventListener("change", () => applyTextStyle("fontSize", Number(size.value)));

        const formatButton = (property, iconName, title) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "ribbon-icon-button";
            button.innerHTML = svg(iconName);
            button.title = title;
            button.classList.toggle("is-active", commonStyle(property, false) === true);
            button.addEventListener("click", () => {
                applyTextStyle(property, true, {toggle: true});
                button.classList.toggle("is-active", commonStyle(property, false) === true);
            });
            return button;
        };

        const fill = document.createElement("button");
        fill.type = "button";
        fill.className = "ribbon-icon-button";
        fill.innerHTML = svg("fill");
        fill.title = "Применить текущую заливку";
        fill.addEventListener("click", () => document.getElementById("apply-cell-fill")?.click());

        const align = document.createElement("button");
        align.type = "button";
        align.className = "ribbon-icon-button";
        align.innerHTML = svg("align-center");
        align.title = "Выровнять по центру";
        align.addEventListener("click", () => document.querySelector('[data-align-horizontal="center"]')?.click());

        bar.append(
            family,
            size,
            formatButton("bold", "bold", "Полужирный"),
            formatButton("italic", "italic", "Курсив"),
            fill,
            align,
        );
        return bar;
    }

    function showContextMenu(event, mode) {
        closeFloatingMenu();
        const rows = selectedRows();
        const rowCount = rows.length;
        floatingMenu = document.createElement("div");
        floatingMenu.className = "journal-context-shell";
        floatingMenu.appendChild(buildMiniToolbar());

        const menu = document.createElement("div");
        menu.className = "journal-context-menu";
        if (mode === "rows") {
            const suffix = rowCount > 1 ? ` ${rowCount} строк` : " строку";
            menu.append(
                contextButton(`Копировать${suffix}`, "copy", () => copySelection(false)),
                contextButton(`Вырезать${suffix}`, "cut", () => copySelection(true)),
                contextButton(`Вставить в выбранные строки`, "paste", () => pasteSelection()),
                contextSeparator(),
                contextButton(`Удалить${suffix}`, "delete-row", () => clearSelection(), {danger: true}),
            );
        } else {
            menu.append(
                contextButton("Копировать", "copy", () => copySelection(false)),
                contextButton("Вырезать", "cut", () => copySelection(true)),
                contextButton("Вставить", "paste", () => pasteSelection()),
                contextSeparator(),
                contextButton("Заполнить вниз", "vertical-bottom", () => fillSelection("down")),
                contextButton("Заполнить вправо", "align-right", () => fillSelection("right")),
                contextButton("Очистить содержимое", "clear", () => clearSelection()),
            );
        }
        floatingMenu.appendChild(menu);
        document.body.appendChild(floatingMenu);

        const rect = floatingMenu.getBoundingClientRect();
        const margin = 8;
        const left = Math.min(event.clientX, window.innerWidth - rect.width - margin);
        let top = event.clientY;
        if (top + rect.height > window.innerHeight - margin) {
            top = Math.max(margin, event.clientY - rect.height);
        }
        floatingMenu.style.left = `${Math.max(margin, left)}px`;
        floatingMenu.style.top = `${Math.max(margin, top)}px`;
    }

    function bindRibbon() {
        activateTab(ribbonState.activeTab || "home");
        setRibbonCollapsed(Boolean(ribbonState.collapsed));

        document.querySelectorAll("[data-ribbon-tab]").forEach((button) => {
            button.addEventListener("click", () => {
                const temporary = ribbon.dataset.ribbonState === "collapsed";
                activateTab(button.dataset.ribbonTab, temporary);
            });
            button.addEventListener("dblclick", () => {
                setRibbonCollapsed(!ribbonState.collapsed);
            });
        });
        document.getElementById("ribbon-collapse")?.addEventListener("click", () => {
            setRibbonCollapsed(!ribbonState.collapsed);
        });

        document.querySelectorAll("[data-ribbon-command]").forEach((button) => {
            button.addEventListener("click", () => {
                const command = button.dataset.ribbonCommand;
                if (command === "copy") {
                    void copySelection(false);
                } else if (command === "cut") {
                    void copySelection(true);
                } else if (command === "paste") {
                    void pasteSelection();
                } else if (command === "clear" || command === "delete-rows") {
                    clearSelection();
                } else if (command === "wrap") {
                    applyTextStyle("wrap", true, {toggle: true});
                } else if (command === "clear-filters") {
                    clearAllFilters();
                } else if (command === "collapse") {
                    setRibbonCollapsed(true);
                }
                closeTemporaryRibbon();
            });
        });

        document.getElementById("clear-all-filters")?.addEventListener("click", clearAllFilters);
        document.getElementById("ribbon-font-family")?.addEventListener("change", (event) => {
            applyTextStyle("fontFamily", event.target.value);
        });
        document.getElementById("ribbon-font-size")?.addEventListener("change", (event) => {
            applyTextStyle("fontSize", Number(event.target.value));
        });
        document.querySelectorAll("[data-text-style]").forEach((button) => {
            button.addEventListener("click", () => {
                applyTextStyle(button.dataset.textStyle, true, {toggle: true});
            });
        });
        document.getElementById("ribbon-text-color")?.addEventListener("input", (event) => {
            applyTextStyle("color", event.target.value);
        });

        const themeSelect = document.getElementById("journal-theme");
        document.querySelectorAll("[data-theme-choice]").forEach((button) => {
            button.addEventListener("click", () => {
                if (!themeSelect) {
                    return;
                }
                themeSelect.value = button.dataset.themeChoice;
                themeSelect.dispatchEvent(new Event("change", {bubbles: true}));
                syncMirroredViewControls();
            });
        });

        const frozenSelect = document.getElementById("journal-frozen-through");
        document.getElementById("ribbon-frozen-through")?.addEventListener("change", (event) => {
            if (!frozenSelect) {
                return;
            }
            frozenSelect.value = event.target.value;
            frozenSelect.dispatchEvent(new Event("change", {bubbles: true}));
        });

        const zoom = document.getElementById("journal-zoom");
        const ribbonZoom = document.getElementById("ribbon-zoom");
        ribbonZoom?.addEventListener("input", () => {
            if (!zoom) {
                return;
            }
            zoom.value = ribbonZoom.value;
            zoom.dispatchEvent(new Event("input", {bubbles: true}));
            syncMirroredViewControls();
        });
        document.getElementById("ribbon-zoom-out")?.addEventListener("click", () => adjustZoom(-5));
        document.getElementById("ribbon-zoom-in")?.addEventListener("click", () => adjustZoom(5));

        themeSelect?.addEventListener("change", syncMirroredViewControls);
        frozenSelect?.addEventListener("change", syncMirroredViewControls);
        zoom?.addEventListener("input", syncMirroredViewControls);
        syncMirroredViewControls();
    }

    function adjustZoom(delta) {
        const ribbonZoom = document.getElementById("ribbon-zoom");
        if (!ribbonZoom) {
            return;
        }
        const next = Math.min(140, Math.max(75, Number(ribbonZoom.value) + delta));
        ribbonZoom.value = String(next);
        ribbonZoom.dispatchEvent(new Event("input", {bubbles: true}));
    }

    function syncMirroredViewControls() {
        const theme = document.getElementById("journal-theme")?.value || "dark";
        const frozen = document.getElementById("journal-frozen-through")?.value || "asset_label";
        const zoom = document.getElementById("journal-zoom")?.value || "100";
        document.querySelectorAll("[data-theme-choice]").forEach((button) => {
            button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme));
        });
        const ribbonFrozen = document.getElementById("ribbon-frozen-through");
        if (ribbonFrozen && [...ribbonFrozen.options].some((option) => option.value === frozen)) {
            ribbonFrozen.value = frozen;
        }
        const ribbonZoom = document.getElementById("ribbon-zoom");
        const ribbonZoomValue = document.getElementById("ribbon-zoom-value");
        if (ribbonZoom) {
            ribbonZoom.value = zoom;
        }
        if (ribbonZoomValue) {
            ribbonZoomValue.textContent = `${zoom}%`;
        }
    }

    window.addEventListener("pointerdown", (event) => {
        if (event.button !== 2 || !(event.target instanceof Element)) {
            return;
        }
        const rowNumber = event.target.closest(".journal-row-number");
        if (rowNumber && root.contains(rowNumber)) {
            event.stopImmediatePropagation();
        }
    }, true);

    window.addEventListener("contextmenu", (event) => {
        if (!(event.target instanceof Element) || !root.contains(event.target)) {
            return;
        }
        const rowNumber = event.target.closest(".journal-row-number");
        const cell = cellFromElement(event.target);
        if (!rowNumber && !cell) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();

        if (rowNumber) {
            const row = rowFromElement(rowNumber);
            if (row && !selectedRowKeys().has(row.getData()._rowKey)) {
                rowNumber.dispatchEvent(new PointerEvent("pointerdown", {
                    bubbles: true,
                    cancelable: true,
                    composed: true,
                    button: 0,
                    buttons: 1,
                }));
            }
            window.setTimeout(() => {
                syncSelectionState();
                showContextMenu(event, "rows");
            }, 0);
            return;
        }

        selectSingleCell(cell);
        window.setTimeout(() => {
            syncSelectionState();
            showContextMenu(event, "cells");
        }, 0);
    }, true);

    window.addEventListener("pointerdown", (event) => {
        if (floatingMenu && event.target instanceof Element && !floatingMenu.contains(event.target)) {
            closeFloatingMenu();
        }
        if (
            ribbon.dataset.ribbonState === "temporary"
            && event.target instanceof Element
            && !ribbon.contains(event.target)
        ) {
            closeTemporaryRibbon();
        }
    }, true);

    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeFloatingMenu();
            closeTemporaryRibbon();
        }
    }, true);
    window.addEventListener("resize", closeFloatingMenu);
    root.addEventListener("scroll", closeFloatingMenu, true);

    const statusObserver = new MutationObserver(scheduleSavedMessageReset);
    statusObserver.observe(saveState, {subtree: true, childList: true, characterData: true, attributes: true});

    const handleObserver = new MutationObserver(dedupeFillHandles);
    handleObserver.observe(document.body, {childList: true, subtree: true});

    table.on("cellClick", () => window.setTimeout(syncSelectionState, 0));
    table.on("rangeChanged", () => window.setTimeout(syncSelectionState, 0));
    table.on("dataFiltered", () => {
        syncFilterIndicator();
        window.setTimeout(guardInvisibleData, 0);
    });
    table.on("headerFilterChanged", syncFilterIndicator);
    table.on("rowUpdated", (row) => {
        migrateStyleKey(row);
        applyAllTextStyles();
    });
    table.on("cellEdited", (cell) => window.requestAnimationFrame(() => applyStyleToCell(cell)));
    table.on("renderComplete", () => {
        allRows().forEach(migrateStyleKey);
        applyAllTextStyles();
        dedupeFillHandles();
        syncSelectionState();
        syncFilterIndicator();
    });
    table.on("tableBuilt", () => {
        allRows().forEach(migrateStyleKey);
        applyAllTextStyles();
        syncSelectionState();
        syncFilterIndicator();
        window.setTimeout(guardInvisibleData, 100);
    });

    document.querySelectorAll("[data-status-filter]").forEach((button) => {
        button.addEventListener("click", () => window.setTimeout(syncFilterIndicator, 0));
    });
    document.getElementById("journal-search")?.addEventListener("input", syncFilterIndicator);

    bindRibbon();
    applyAllTextStyles();
    syncSelectionState();
    syncFilterIndicator();
    scheduleSavedMessageReset();
})();
