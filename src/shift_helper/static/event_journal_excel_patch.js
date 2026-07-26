"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const suggestionsElement = document.getElementById("event-journal-suggestions");
    const OriginalTabulator = window.Tabulator;

    if (!root || !suggestionsElement || typeof OriginalTabulator !== "function") {
        return;
    }

    const suggestions = JSON.parse(suggestionsElement.textContent || "{}");
    const editableFields = new Set([
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
    ]);
    const multilineFields = new Set(["description", "reason", "actions"]);
    const suggestionFields = new Set([
        "asset_label",
        "description",
        "reason",
        "actions",
        "performer",
        "author",
    ]);
    const fillStorageKey = "shift-helper-event-cell-fill-v1";
    const rulesStorageKey = "shift-helper-event-format-rules-v1";
    const manualFillStore = loadJson(fillStorageKey, {});
    const formatRules = loadJson(rulesStorageKey, []);
    const rowOriginalKeys = new WeakMap();
    let table = null;
    let activeCell = null;
    let typedSeed = null;
    let internalClipboard = null;

    function loadJson(key, fallback) {
        try {
            const raw = window.localStorage.getItem(key);
            return raw === null ? fallback : JSON.parse(raw);
        } catch (_error) {
            return fallback;
        }
    }

    function saveJson(key, value) {
        try {
            window.localStorage.setItem(key, JSON.stringify(value));
        } catch (_error) {
            // Formatting is workstation-local and must never block journal input.
        }
    }

    function hasDraftContent(data) {
        return [...editableFields].some((field) => {
            if (field === "start_date" || field === "start_time") {
                return false;
            }
            return String(data[field] ?? "").trim() !== "";
        });
    }

    function patchRowComponent(row) {
        if (row.__shiftHelperPatched) {
            return row;
        }
        Object.defineProperty(row, "__shiftHelperPatched", {value: true});
        const originalUpdate = row.update.bind(row);
        row.update = (values) => {
            const data = row.getData();
            const keys = values && typeof values === "object" ? Object.keys(values) : [];
            const isAutomaticDraftSeed = Boolean(
                data._draft
                && !hasDraftContent(data)
                && keys.length === 2
                && keys.includes("start_date")
                && keys.includes("start_time"),
            );
            if (isAutomaticDraftSeed) {
                return Promise.resolve();
            }
            return originalUpdate(values);
        };
        return row;
    }

    function clearInitialDraftSeeds(options) {
        for (const row of options.data || []) {
            if (row._draft && !hasDraftContent(row)) {
                row.start_date = "";
                row.start_time = "";
            }
        }
    }

    function editorValues(field, query) {
        const values = Array.isArray(suggestions[field]) ? suggestions[field] : [];
        const normalized = query.trim().toLocaleLowerCase("ru");
        if (!normalized) {
            return values.slice(0, 10);
        }
        return values
            .filter((value) => value.toLocaleLowerCase("ru").includes(normalized))
            .slice(0, 10);
    }

    function excelEditor(cell, onRendered, success, cancel, params = {}) {
        const multiline = Boolean(params.multiline);
        const editor = document.createElement(multiline ? "textarea" : "input");
        const rowKey = cell.getRow().getData()._rowKey;
        const field = cell.getField();
        const seeded = typedSeed
            && typedSeed.rowKey === rowKey
            && typedSeed.field === field
            ? typedSeed.text
            : null;
        typedSeed = null;
        editor.className = "journal-excel-editor";
        editor.value = seeded === null ? String(cell.getValue() ?? "") : seeded;
        editor.autocomplete = "off";
        editor.spellcheck = multiline;

        let finished = false;
        let popup = null;

        function resize() {
            if (!multiline) {
                return;
            }
            editor.style.height = "34px";
            editor.style.height = `${Math.min(Math.max(editor.scrollHeight, 34), 260)}px`;
            cell.getElement().style.minHeight = editor.style.height;
            cell.checkHeight();
        }

        function closePopup() {
            popup?.remove();
            popup = null;
        }

        function showSuggestions() {
            closePopup();
            if (!params.suggestionField) {
                return;
            }
            const values = editorValues(params.suggestionField, editor.value);
            if (!values.length) {
                return;
            }
            const rect = cell.getElement().getBoundingClientRect();
            popup = document.createElement("div");
            popup.className = "journal-editor-suggestions";
            popup.style.left = `${Math.max(4, rect.left)}px`;
            popup.style.top = `${Math.min(window.innerHeight - 245, rect.bottom + 2)}px`;
            popup.style.width = `${Math.max(240, rect.width)}px`;
            for (const value of values) {
                const option = document.createElement("button");
                option.type = "button";
                option.textContent = value;
                option.addEventListener("mousedown", (event) => {
                    event.preventDefault();
                    editor.value = value;
                    resize();
                    closePopup();
                    editor.focus();
                });
                popup.appendChild(option);
            }
            document.body.appendChild(popup);
        }

        function finish(commit, navigation = null) {
            if (finished) {
                return;
            }
            finished = true;
            closePopup();
            cell.getElement().style.minHeight = "";
            if (commit) {
                success(editor.value);
            } else {
                cancel();
            }
            window.requestAnimationFrame(() => {
                cell.checkHeight();
                if (navigation === "down") {
                    cell.navigateDown();
                } else if (navigation === "next") {
                    cell.navigateNext();
                } else if (navigation === "previous") {
                    cell.navigatePrev();
                }
            });
        }

        editor.addEventListener("input", () => {
            resize();
            showSuggestions();
        });
        editor.addEventListener("focus", showSuggestions);
        editor.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                event.preventDefault();
                finish(false);
                return;
            }
            if (event.key === "Enter") {
                if (multiline && event.shiftKey) {
                    return;
                }
                event.preventDefault();
                event.stopPropagation();
                finish(true, "down");
                return;
            }
            if (event.key === "Tab") {
                event.preventDefault();
                event.stopPropagation();
                finish(true, event.shiftKey ? "previous" : "next");
            }
        });
        editor.addEventListener("blur", () => finish(true));

        onRendered(() => {
            resize();
            editor.focus();
            const caret = editor.value.length;
            editor.setSelectionRange(caret, caret);
        });
        return editor;
    }

    function contrastingTextColor(color) {
        const hex = String(color || "").replace("#", "");
        if (!/^[0-9a-f]{6}$/i.test(hex)) {
            return "";
        }
        const red = Number.parseInt(hex.slice(0, 2), 16);
        const green = Number.parseInt(hex.slice(2, 4), 16);
        const blue = Number.parseInt(hex.slice(4, 6), 16);
        return ((0.299 * red) + (0.587 * green) + (0.114 * blue)) > 155
            ? "#18212a"
            : "#f7fafc";
    }

    function ruleMatches(rule, field, rawValue) {
        if (rule.field !== "*" && rule.field !== field) {
            return false;
        }
        const value = String(rawValue ?? "");
        const normalized = value.toLocaleLowerCase("ru");
        const expected = String(rule.value ?? "").toLocaleLowerCase("ru");
        if (rule.operator === "contains") {
            return normalized.includes(expected);
        }
        if (rule.operator === "equals") {
            return normalized === expected;
        }
        if (rule.operator === "starts") {
            return normalized.startsWith(expected);
        }
        if (rule.operator === "nonempty") {
            return value.trim() !== "";
        }
        if (rule.operator === "empty") {
            return value.trim() === "";
        }
        if (rule.operator === "regex") {
            try {
                return new RegExp(rule.value, "iu").test(value);
            } catch (_error) {
                return false;
            }
        }
        return false;
    }

    function fillForCell(cell) {
        const data = cell.getRow().getData();
        const manual = manualFillStore[data._rowKey]?.[cell.getField()];
        if (manual) {
            return manual;
        }
        return formatRules.find((rule) => ruleMatches(
            rule,
            cell.getField(),
            cell.getValue(),
        ))?.color || "";
    }

    function applyFill(cell) {
        const element = cell.getElement();
        const valueElement = element.querySelector(".journal-cell-value");
        const fill = fillForCell(cell);
        element.style.backgroundColor = fill;
        if (valueElement) {
            valueElement.style.color = fill ? contrastingTextColor(fill) : "";
        }
    }

    function wrapFormatter(column) {
        const originalFormatter = column.formatter;
        column.formatter = (cell, params, onRendered) => {
            const result = typeof originalFormatter === "function"
                ? originalFormatter(cell, params, onRendered)
                : String(cell.getValue() ?? "");
            onRendered(() => applyFill(cell));
            return result;
        };
    }

    function currencyFormatter(cell, _params, onRendered) {
        const element = document.createElement("div");
        element.className = "journal-cell-value journal-cell-value--currency";
        const raw = String(cell.getValue() ?? "").trim();
        if (raw) {
            const numeric = Number(raw.replace(/\s/g, "").replace(",", "."));
            element.textContent = Number.isFinite(numeric)
                ? `${new Intl.NumberFormat("ru-RU", {maximumFractionDigits: 0}).format(numeric)} ₽`
                : raw;
        }
        onRendered(() => applyFill(cell));
        return element;
    }

    function patchColumns(options) {
        for (const column of options.columns || []) {
            if (column.field === "losses_mwh") {
                column.field = "downtime_losses_rub";
                column.title = "Потери от простоя, руб.";
                column.width = 145;
                column.minWidth = 110;
                column.editor = false;
                column.formatter = currencyFormatter;
                continue;
            }
            if (editableFields.has(column.field)) {
                column.editor = excelEditor;
                column.editorParams = {
                    multiline: multilineFields.has(column.field),
                    suggestionField: suggestionFields.has(column.field)
                        ? column.field
                        : null,
                };
            }
            wrapFormatter(column);
        }
    }

    function patchOptions(options) {
        clearInitialDraftSeeds(options);
        patchColumns(options);
        options.columnDefaults = {
            ...(options.columnDefaults || {}),
            resizable: "header",
        };
        options.rowHeader = {
            ...(options.rowHeader || {}),
            field: "rownum",
            accessorClipboard: "rownum",
            editor: false,
        };
    }

    function PatchedTabulator(element, options) {
        patchOptions(options);
        const instance = new OriginalTabulator(element, options);
        table = instance;

        const originalGetRows = instance.getRows.bind(instance);
        instance.getRows = (...args) => originalGetRows(...args).map(patchRowComponent);
        window.shiftHelperEventGrid = instance;
        window.setTimeout(() => installExcelBehaviour(instance), 0);
        return instance;
    }

    Object.setPrototypeOf(PatchedTabulator, OriginalTabulator);
    PatchedTabulator.prototype = OriginalTabulator.prototype;
    window.Tabulator = PatchedTabulator;

    function currentCell() {
        const ranges = table?.getRanges?.() || [];
        const bounds = ranges.at(-1)?.getBounds?.();
        return bounds?.end || activeCell;
    }

    function selectedMatrix() {
        const ranges = table?.getRanges?.() || [];
        const range = ranges.at(-1);
        if (!range) {
            return activeCell ? [[activeCell]] : [];
        }
        if (typeof range.getStructuredCells === "function") {
            return range.getStructuredCells();
        }
        const cells = range.getCells?.() || [];
        return cells.length && !Array.isArray(cells[0]) ? [cells] : cells;
    }

    function selectedCells({editableOnly = false} = {}) {
        const cells = [...new Set(selectedMatrix().flat())];
        return editableOnly
            ? cells.filter((cell) => editableFields.has(cell.getField()))
            : cells;
    }

    function migrateRowFill(row) {
        const data = row.getData();
        const oldKey = rowOriginalKeys.get(row);
        if (!oldKey) {
            rowOriginalKeys.set(row, data._rowKey);
            return;
        }
        if (oldKey === data._rowKey) {
            return;
        }
        if (manualFillStore[oldKey]) {
            manualFillStore[data._rowKey] = {
                ...(manualFillStore[data._rowKey] || {}),
                ...manualFillStore[oldKey],
            };
            delete manualFillStore[oldKey];
            saveJson(fillStorageKey, manualFillStore);
        }
        rowOriginalKeys.set(row, data._rowKey);
    }

    function applyManualFill(color) {
        const rows = new Set();
        for (const cell of selectedCells()) {
            const data = cell.getRow().getData();
            manualFillStore[data._rowKey] ||= {};
            if (color) {
                manualFillStore[data._rowKey][cell.getField()] = color;
            } else {
                delete manualFillStore[data._rowKey][cell.getField()];
                if (!Object.keys(manualFillStore[data._rowKey]).length) {
                    delete manualFillStore[data._rowKey];
                }
            }
            rows.add(cell.getRow());
        }
        saveJson(fillStorageKey, manualFillStore);
        rows.forEach((row) => row.reformat());
    }

    function clearSelection() {
        const rows = new Set();
        for (const cell of selectedCells({editableOnly: true})) {
            cell.setValue("", true);
            rows.add(cell.getRow());
        }
        rows.forEach((row) => row.reformat());
    }

    function captureClipboardMetadata() {
        const matrix = selectedMatrix();
        internalClipboard = matrix.map((row) => row.map((cell) => {
            const data = cell.getRow().getData();
            return {
                fill: manualFillStore[data._rowKey]?.[cell.getField()] || "",
            };
        }));
    }

    async function cutSelection() {
        const matrix = selectedMatrix();
        if (!matrix.length) {
            return;
        }
        captureClipboardMetadata();
        const text = matrix
            .map((row) => row.map((cell) => String(cell.getValue() ?? "")).join("\t"))
            .join("\n");
        try {
            await navigator.clipboard.writeText(text);
        } catch (_error) {
            return;
        }
        clearSelection();
    }

    function pasteFormatting() {
        if (!internalClipboard) {
            return;
        }
        const matrix = selectedMatrix();
        const rows = new Set();
        matrix.forEach((row, rowIndex) => {
            row.forEach((cell, columnIndex) => {
                const source = internalClipboard[rowIndex % internalClipboard.length]
                    ?. [columnIndex % internalClipboard[0].length];
                if (!source?.fill) {
                    return;
                }
                const data = cell.getRow().getData();
                manualFillStore[data._rowKey] ||= {};
                manualFillStore[data._rowKey][cell.getField()] = source.fill;
                rows.add(cell.getRow());
            });
        });
        saveJson(fillStorageKey, manualFillStore);
        rows.forEach((row) => row.reformat());
    }

    function renderRules() {
        const list = document.getElementById("format-rules-list");
        if (!list) {
            return;
        }
        list.replaceChildren();
        if (!formatRules.length) {
            const empty = document.createElement("p");
            empty.className = "format-rules-list__empty";
            empty.textContent = "Правила ещё не созданы.";
            list.appendChild(empty);
            return;
        }
        for (const rule of formatRules) {
            const row = document.createElement("div");
            row.className = "format-rule-row";
            const swatch = document.createElement("span");
            swatch.className = "format-rule-row__swatch";
            swatch.style.backgroundColor = rule.color;
            const description = document.createElement("span");
            description.className = "format-rule-row__text";
            description.textContent = `${rule.field}: ${rule.operator}${rule.value ? ` «${rule.value}»` : ""}`;
            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "format-rule-row__remove";
            remove.textContent = "Удалить";
            remove.addEventListener("click", () => {
                const index = formatRules.findIndex((candidate) => candidate.id === rule.id);
                if (index >= 0) {
                    formatRules.splice(index, 1);
                    saveJson(rulesStorageKey, formatRules);
                    renderRules();
                    table.getRows().forEach((tableRow) => tableRow.reformat());
                }
            });
            row.append(swatch, description, remove);
            list.appendChild(row);
        }
    }

    function installToolbar() {
        const fillColor = document.getElementById("cell-fill-color");
        document.getElementById("apply-cell-fill")?.addEventListener(
            "click",
            () => applyManualFill(fillColor?.value || "#fff2cc"),
        );
        document.getElementById("clear-cell-fill")?.addEventListener(
            "click",
            () => applyManualFill(""),
        );

        const dialog = document.getElementById("format-rules-dialog");
        document.getElementById("open-format-rules")?.addEventListener("click", () => {
            renderRules();
            dialog?.showModal();
        });
        document.getElementById("add-format-rule")?.addEventListener("click", () => {
            const field = document.getElementById("format-rule-column")?.value || "*";
            const operator = document.getElementById("format-rule-operator")?.value || "contains";
            const valueInput = document.getElementById("format-rule-value");
            const value = valueInput?.value.trim() || "";
            if (!["empty", "nonempty"].includes(operator) && !value) {
                valueInput?.focus();
                return;
            }
            formatRules.push({
                id: `rule-${Date.now()}-${Math.random().toString(16).slice(2)}`,
                field,
                operator,
                value,
                color: document.getElementById("format-rule-color")?.value || "#f4cccc",
            });
            saveJson(rulesStorageKey, formatRules);
            if (valueInput) {
                valueInput.value = "";
            }
            renderRules();
            table.getRows().forEach((row) => row.reformat());
        });
    }

    function installExcelBehaviour(instance) {
        instance.getRows().forEach((row) => rowOriginalKeys.set(row, row.getData()._rowKey));
        instance.on("cellClick", (_event, cell) => {
            activeCell = cell;
        });
        instance.on("rangeChanged", (range) => {
            activeCell = range.getBounds?.().end || activeCell;
        });
        instance.on("rowUpdated", (row) => {
            migrateRowFill(row);
            patchRowComponent(row);
        });
        instance.on("clipboardPasted", () => {
            window.requestAnimationFrame(pasteFormatting);
        });

        root.addEventListener("keydown", (event) => {
            const target = event.target;
            const editing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
            if (editing) {
                return;
            }
            const cell = currentCell();
            if (!cell) {
                return;
            }
            const modifier = event.ctrlKey || event.metaKey;
            const key = event.key.toLowerCase();
            if (modifier && key === "c") {
                captureClipboardMetadata();
                return;
            }
            if (modifier && key === "x") {
                event.preventDefault();
                event.stopImmediatePropagation();
                void cutSelection();
                return;
            }
            if (event.key === "F2" && editableFields.has(cell.getField())) {
                event.preventDefault();
                cell.edit();
                return;
            }
            if (event.key === "Enter" && editableFields.has(cell.getField())) {
                event.preventDefault();
                event.stopImmediatePropagation();
                cell.edit();
                return;
            }
            if (
                editableFields.has(cell.getField())
                && event.key.length === 1
                && !modifier
                && !event.altKey
            ) {
                event.preventDefault();
                event.stopImmediatePropagation();
                typedSeed = {
                    rowKey: cell.getRow().getData()._rowKey,
                    field: cell.getField(),
                    text: event.key,
                };
                cell.edit();
            }
        }, true);
        installToolbar();
    }
})();
