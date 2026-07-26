"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const suggestionsElement = document.getElementById("event-journal-suggestions");
    const OriginalTabulator = window.Tabulator;

    if (!root || !suggestionsElement || typeof OriginalTabulator !== "function") {
        return;
    }

    const suggestions = JSON.parse(suggestionsElement.textContent || "{}");
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
    const editableFieldSet = new Set(editableFields);
    const clipboardFields = [
        "start_date",
        "start_time",
        "asset_label",
        "description",
        "reason",
        "actions",
        "performer",
        "end_date",
        "end_time",
        "downtime",
        "author",
        "downtime_losses_rub",
    ];
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
    const selectedRowKeys = new Set();

    let table = null;
    let activeCell = null;
    let typedSeed = null;
    let internalClipboard = null;
    let lastCopiedText = "";
    let lastSelectedRowKey = null;

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
            // Workstation-local presentation settings must not block journal input.
        }
    }

    function showStatus(state, message) {
        const saveState = document.getElementById("journal-save-state");
        const text = saveState?.querySelector(".save-state__text");
        if (saveState) {
            saveState.dataset.state = state;
        }
        if (text) {
            text.textContent = message;
        }
    }

    function pad(value) {
        return String(value).padStart(2, "0");
    }

    function currentDate(now = new Date()) {
        return `${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${now.getFullYear()}`;
    }

    function currentTime(now = new Date()) {
        return `${pad(now.getHours())}:${pad(now.getMinutes())}`;
    }

    function hasDraftContent(data) {
        return editableFields.some((field) => {
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
            return values.slice(0, 12);
        }
        return values
            .filter((value) => value.toLocaleLowerCase("ru").includes(normalized))
            .slice(0, 12);
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
        editor.dataset.multiline = String(multiline);
        editor.value = seeded === null ? String(cell.getValue() ?? "") : seeded;
        editor.autocomplete = "off";
        editor.spellcheck = multiline;

        let finished = false;
        let popup = null;

        function resize() {
            if (!multiline) {
                return;
            }
            editor.style.height = "32px";
            editor.style.height = `${Math.min(Math.max(editor.scrollHeight, 32), 240)}px`;
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
                    editor.dispatchEvent(new Event("input", {bubbles: true}));
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
            editor.style.visibility = "hidden";

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

        function handleEditorKeydown(event) {
            if (event.key === "Escape") {
                event.preventDefault();
                event.stopImmediatePropagation();
                finish(false);
                return;
            }

            const isEnter = event.key === "Enter" || event.code === "NumpadEnter";
            if (isEnter) {
                if (multiline && event.shiftKey) {
                    return;
                }
                event.preventDefault();
                event.stopImmediatePropagation();
                finish(true, "down");
                return;
            }

            if (event.key === "Tab") {
                event.preventDefault();
                event.stopImmediatePropagation();
                finish(true, event.shiftKey ? "previous" : "next");
            }
        }

        editor.addEventListener("input", () => {
            resize();
            showSuggestions();
        });
        editor.addEventListener("focus", showSuggestions);
        editor.addEventListener("keydown", handleEditorKeydown, true);
        editor.addEventListener("blur", () => finish(true));

        onRendered(() => {
            resize();
            editor.focus({preventScroll: true});
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
            ? cells.filter((cell) => editableFieldSet.has(cell.getField()))
            : cells;
    }

    function cellFromSelectedElement() {
        const element = root.querySelector(
            ".tabulator-cell.tabulator-range-active, "
            + ".tabulator-cell.tabulator-range-selected, "
            + ".tabulator-cell[aria-selected='true']",
        );
        if (!element || !table) {
            return null;
        }
        for (const row of table.getRows("active")) {
            for (const cell of row.getCells()) {
                if (cell.getElement() === element) {
                    return cell;
                }
            }
        }
        return null;
    }

    function currentCell() {
        return cellFromSelectedElement() || activeCell;
    }

    function rowForElement(element) {
        if (!table) {
            return null;
        }
        return table.getRows("active").find((row) => row.getElement() === element) || null;
    }

    function selectedRows() {
        if (!table) {
            return [];
        }
        return table
            .getRows("active")
            .filter((row) => selectedRowKeys.has(row.getData()._rowKey));
    }

    function refreshRowSelection() {
        if (!table) {
            return;
        }
        for (const row of table.getRows()) {
            row.getElement().classList.toggle(
                "journal-row--selected",
                selectedRowKeys.has(row.getData()._rowKey),
            );
        }
    }

    function selectOnlyRow(row) {
        selectedRowKeys.clear();
        selectedRowKeys.add(row.getData()._rowKey);
        lastSelectedRowKey = row.getData()._rowKey;
        refreshRowSelection();
    }

    function selectRowFromHeader(event, cell) {
        const row = cell.getRow();
        const rowKey = row.getData()._rowKey;
        const rows = table.getRows("active");

        if (event.shiftKey && lastSelectedRowKey) {
            const anchor = rows.findIndex(
                (candidate) => candidate.getData()._rowKey === lastSelectedRowKey,
            );
            const target = rows.indexOf(row);
            if (anchor >= 0 && target >= 0) {
                if (!event.ctrlKey && !event.metaKey) {
                    selectedRowKeys.clear();
                }
                const from = Math.min(anchor, target);
                const to = Math.max(anchor, target);
                rows.slice(from, to + 1).forEach((candidate) => {
                    selectedRowKeys.add(candidate.getData()._rowKey);
                });
            }
        } else if (event.ctrlKey || event.metaKey) {
            if (selectedRowKeys.has(rowKey)) {
                selectedRowKeys.delete(rowKey);
            } else {
                selectedRowKeys.add(rowKey);
            }
            lastSelectedRowKey = rowKey;
        } else {
            selectedRowKeys.clear();
            selectedRowKeys.add(rowKey);
            lastSelectedRowKey = rowKey;
        }
        refreshRowSelection();
        event.preventDefault();
        event.stopPropagation();
    }

    function quoteTsv(value) {
        const text = String(value ?? "");
        if (!/[\t\r\n"]/.test(text)) {
            return text;
        }
        return `"${text.replaceAll('"', '""')}"`;
    }

    function matrixToTsv(matrix) {
        return matrix
            .map((row) => row.map(quoteTsv).join("\t"))
            .join("\r\n");
    }

    function parseTsv(text) {
        const rows = [];
        let row = [];
        let value = "";
        let quoted = false;

        for (let index = 0; index < text.length; index += 1) {
            const character = text[index];
            if (quoted) {
                if (character === '"' && text[index + 1] === '"') {
                    value += '"';
                    index += 1;
                } else if (character === '"') {
                    quoted = false;
                } else {
                    value += character;
                }
                continue;
            }

            if (character === '"') {
                quoted = true;
            } else if (character === "\t") {
                row.push(value);
                value = "";
            } else if (character === "\n") {
                row.push(value.replace(/\r$/, ""));
                rows.push(row);
                row = [];
                value = "";
            } else {
                value += character;
            }
        }

        row.push(value.replace(/\r$/, ""));
        rows.push(row);
        return rows.filter((candidate) => candidate.some((cell) => cell !== ""));
    }

    async function writeClipboard(text) {
        lastCopiedText = text;
        try {
            await navigator.clipboard.writeText(text);
            showStatus("saved", "Скопировано в буфер обмена");
            return true;
        } catch (_error) {
            showStatus("error", "Браузер не разрешил запись в буфер обмена");
            return false;
        }
    }

    async function readClipboard() {
        try {
            return await navigator.clipboard.readText();
        } catch (_error) {
            showStatus("error", "Браузер не разрешил чтение буфера обмена");
            return "";
        }
    }

    async function copyCells() {
        const matrix = selectedMatrix();
        if (!matrix.length) {
            return;
        }
        const values = matrix.map((row) => row.map((cell) => cell.getValue()));
        internalClipboard = {kind: "cells", values};
        await writeClipboard(matrixToTsv(values));
    }

    async function copyRows(rows = selectedRows()) {
        if (!rows.length) {
            const row = currentCell()?.getRow();
            if (row) {
                rows = [row];
                selectOnlyRow(row);
            }
        }
        if (!rows.length) {
            showStatus("error", "Сначала выберите строку по её номеру");
            return;
        }
        const values = rows.map((row) => {
            const data = row.getData();
            return clipboardFields.map((field) => data[field] ?? "");
        });
        internalClipboard = {
            kind: "rows",
            rows: rows.map((row) => ({...row.getData()})),
            values,
        };
        await writeClipboard(matrixToTsv(values));
    }

    async function cutCells() {
        const cells = selectedCells({editableOnly: true});
        if (!cells.length) {
            return;
        }
        const persistedRequired = cells.some((cell) => {
            const data = cell.getRow().getData();
            return !data._draft && [
                "start_date",
                "start_time",
                "asset_label",
                "description",
            ].includes(cell.getField());
        });
        if (persistedRequired) {
            showStatus(
                "error",
                "Нельзя вырезать обязательные поля сохранённой строки; используйте копирование",
            );
            return;
        }
        await copyCells();
        cells.forEach((cell) => cell.setValue("", true));
    }

    async function cutRows(rows = selectedRows()) {
        if (!rows.length) {
            return;
        }
        if (rows.some((row) => !row.getData()._draft)) {
            showStatus(
                "error",
                "Вырезание сохранённой строки появится вместе с безопасным удалением записи",
            );
            return;
        }
        await copyRows(rows);
        for (const row of rows) {
            for (const field of editableFields) {
                row.getCell(field)?.setValue("", true);
            }
        }
    }

    function valuesForEditableFields(source) {
        if (Array.isArray(source)) {
            if (source.length >= clipboardFields.length) {
                const result = {};
                clipboardFields.forEach((field, index) => {
                    if (editableFieldSet.has(field)) {
                        result[field] = source[index] ?? "";
                    }
                });
                return result;
            }
            const result = {};
            editableFields.forEach((field, index) => {
                result[field] = source[index] ?? "";
            });
            return result;
        }
        const result = {};
        editableFields.forEach((field) => {
            result[field] = source[field] ?? "";
        });
        return result;
    }

    function applyRowValues(row, values) {
        const normalized = valuesForEditableFields(values);
        for (const field of editableFields) {
            row.getCell(field)?.setValue(normalized[field] ?? "", true);
        }
        row.reformat();
    }

    function targetRowsFrom(row, count) {
        const rows = table.getRows("active");
        const start = Math.max(0, rows.indexOf(row));
        return rows.slice(start, start + count);
    }

    async function pasteRowsAt(targetRow, suppliedText = null) {
        if (!targetRow) {
            showStatus("error", "Сначала выберите строку по её номеру");
            return;
        }

        const text = suppliedText === null ? await readClipboard() : suppliedText;
        let sources;
        if (internalClipboard?.kind === "rows" && (!text || text === lastCopiedText)) {
            sources = internalClipboard.rows;
        } else {
            sources = parseTsv(text);
        }
        if (!sources?.length) {
            return;
        }

        const targets = targetRowsFrom(targetRow, sources.length);
        targets.forEach((row, index) => applyRowValues(row, sources[index]));
        selectedRowKeys.clear();
        targets.forEach((row) => selectedRowKeys.add(row.getData()._rowKey));
        refreshRowSelection();
        showStatus("dirty", `Вставлено строк: ${targets.length}`);
    }

    async function pasteCellsAt(cell, suppliedText = null) {
        if (!cell) {
            return;
        }
        const text = suppliedText === null ? await readClipboard() : suppliedText;
        const matrix = internalClipboard?.kind === "cells" && (!text || text === lastCopiedText)
            ? internalClipboard.values
            : parseTsv(text);
        if (!matrix.length) {
            return;
        }

        const rows = table.getRows("active");
        const columns = table.getColumns().filter((column) => editableFieldSet.has(column.getField()));
        const startRow = rows.indexOf(cell.getRow());
        const startColumn = columns.findIndex((column) => column.getField() === cell.getField());
        if (startRow < 0 || startColumn < 0) {
            return;
        }

        matrix.forEach((sourceRow, rowOffset) => {
            const targetRow = rows[startRow + rowOffset];
            if (!targetRow) {
                return;
            }
            sourceRow.forEach((value, columnOffset) => {
                const targetColumn = columns[startColumn + columnOffset];
                targetRow.getCell(targetColumn?.getField())?.setValue(value, true);
            });
        });
    }

    function clearSelectedCells() {
        selectedCells({editableOnly: true}).forEach((cell) => cell.setValue("", true));
    }

    function copyValueFromAbove(cell) {
        const rows = table.getRows("active");
        const index = rows.indexOf(cell.getRow());
        if (index <= 0) {
            return;
        }
        cell.setValue(rows[index - 1].getData()[cell.getField()] ?? "", true);
    }

    function fillRange(direction) {
        const matrix = selectedMatrix();
        if (!matrix.length || !matrix[0]?.length) {
            return;
        }
        if (direction === "down") {
            const source = matrix[0].map((cell) => cell.getValue());
            matrix.slice(1).forEach((row) => {
                row.forEach((cell, index) => {
                    if (editableFieldSet.has(cell.getField())) {
                        cell.setValue(source[index] ?? "", true);
                    }
                });
            });
        } else {
            matrix.forEach((row) => {
                const source = row[0]?.getValue() ?? "";
                row.slice(1).forEach((cell) => {
                    if (editableFieldSet.has(cell.getField())) {
                        cell.setValue(source, true);
                    }
                });
            });
        }
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

    function applyAlignment(axis, value) {
        const button = document.querySelector(`[data-align-${axis}="${value}"]`);
        button?.click();
    }

    const cellContextMenu = [
        {
            label: "Копировать",
            action: (_event, cell) => {
                activeCell = cell;
                void copyCells();
            },
        },
        {
            label: "Вырезать",
            action: (_event, cell) => {
                activeCell = cell;
                void cutCells();
            },
        },
        {
            label: "Вставить",
            action: (_event, cell) => {
                activeCell = cell;
                void pasteCellsAt(cell);
            },
        },
        {separator: true},
        {
            label: "Заполнить вниз (Ctrl+D)",
            action: () => fillRange("down"),
        },
        {
            label: "Заполнить вправо (Ctrl+R)",
            action: () => fillRange("right"),
        },
        {
            label: "Значение из строки выше",
            action: (_event, cell) => copyValueFromAbove(cell),
        },
        {separator: true},
        {
            label: "По левому краю",
            action: (_event, cell) => {
                activeCell = cell;
                applyAlignment("horizontal", "left");
            },
        },
        {
            label: "По центру",
            action: (_event, cell) => {
                activeCell = cell;
                applyAlignment("horizontal", "center");
            },
        },
        {
            label: "По правому краю",
            action: (_event, cell) => {
                activeCell = cell;
                applyAlignment("horizontal", "right");
            },
        },
        {separator: true},
        {
            label: "Очистить содержимое",
            action: (_event, cell) => {
                activeCell = cell;
                clearSelectedCells();
            },
        },
    ];

    function rowMenuFor(row) {
        selectOnlyRow(row);
        return [
            {
                label: "Копировать строку",
                action: () => void copyRows(),
            },
            {
                label: "Вырезать строку",
                action: () => void cutRows(),
            },
            {
                label: "Вставить строку",
                action: () => void pasteRowsAt(row),
            },
            {separator: true},
            {
                label: "Очистить черновую строку",
                action: () => {
                    const rows = selectedRows();
                    if (rows.some((candidate) => !candidate.getData()._draft)) {
                        showStatus("error", "Сохранённую строку нельзя очистить как черновик");
                        return;
                    }
                    rows.forEach((candidate) => {
                        editableFields.forEach((field) => {
                            candidate.getCell(field)?.setValue("", true);
                        });
                    });
                },
            },
        ];
    }

    function rowHeaderContextMenu(cell) {
        return rowMenuFor(cell.getRow());
    }

    function rowContextMenu(row) {
        return rowMenuFor(row);
    }

    function patchColumns(options) {
        for (const column of options.columns || []) {
            delete column.cellContextMenu;
            column.contextMenu = cellContextMenu;

            if (column.field === "losses_mwh") {
                column.field = "downtime_losses_rub";
                column.title = "Потери от простоя, руб.";
                column.width = 145;
                column.minWidth = 110;
                column.editor = false;
                column.formatter = currencyFormatter;
                continue;
            }

            if (editableFieldSet.has(column.field)) {
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
            formatter: "rownum",
            editor: false,
            cellClick: selectRowFromHeader,
            contextMenu: rowHeaderContextMenu,
        };
        options.rowContextMenu = rowContextMenu;
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
        if (selectedRowKeys.delete(oldKey)) {
            selectedRowKeys.add(data._rowKey);
        }
        rowOriginalKeys.set(row, data._rowKey);
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

    function installInteractionHandlers(instance) {
        instance.getRows().forEach((row) => rowOriginalKeys.set(row, row.getData()._rowKey));
        instance.on("cellClick", (_event, cell) => {
            activeCell = cell;
        });
        instance.on("rangeChanged", (range) => {
            const bounds = range.getBounds?.();
            activeCell = bounds?.end || bounds?.bottomRight || activeCell;
        });
        instance.on("rowUpdated", (row) => {
            migrateRowFill(row);
            patchRowComponent(row);
            refreshRowSelection();
        });
        instance.on("renderComplete", refreshRowSelection);
        instance.on("cellEdited", (cell) => {
            const row = cell.getRow();
            const data = row.getData();
            if (!data._draft || !hasDraftContent(data)) {
                return;
            }
            const timestamp = {};
            if (!String(data.start_date ?? "").trim()) {
                timestamp.start_date = currentDate();
            }
            if (!String(data.start_time ?? "").trim()) {
                timestamp.start_time = currentTime();
            }
            if (Object.keys(timestamp).length) {
                void row.update(timestamp);
            }
        });

        document.addEventListener("keydown", (event) => {
            const target = event.target;
            const editing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
            if (editing) {
                return;
            }

            const modifier = event.ctrlKey || event.metaKey;
            const key = event.key.toLocaleLowerCase("ru");
            const rows = selectedRows();

            if (modifier && key === "c" && rows.length) {
                event.preventDefault();
                event.stopImmediatePropagation();
                void copyRows(rows);
                return;
            }
            if (modifier && key === "x" && rows.length) {
                event.preventDefault();
                event.stopImmediatePropagation();
                void cutRows(rows);
                return;
            }
            if (modifier && key === "d") {
                event.preventDefault();
                fillRange("down");
                return;
            }
            if (modifier && key === "r") {
                event.preventDefault();
                fillRange("right");
                return;
            }

            const cell = currentCell();
            if (!cell || !editableFieldSet.has(cell.getField())) {
                return;
            }
            if (event.key === "Enter" || event.key === "F2") {
                event.preventDefault();
                event.stopImmediatePropagation();
                cell.edit();
                return;
            }
            if (event.key.length === 1 && !modifier && !event.altKey) {
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

        document.addEventListener("paste", (event) => {
            const target = event.target;
            if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
                return;
            }
            const rows = selectedRows();
            if (!rows.length) {
                return;
            }
            const text = event.clipboardData?.getData("text/plain") || "";
            event.preventDefault();
            event.stopImmediatePropagation();
            void pasteRowsAt(rows[0], text);
        }, true);

        root.addEventListener("click", (event) => {
            const header = event.target.closest(".journal-row-number");
            const rowElement = header?.closest(".tabulator-row");
            const row = rowElement ? rowForElement(rowElement) : null;
            if (!row || header?.dataset.shiftHelperHandled === "true") {
                return;
            }
            selectOnlyRow(row);
        });

        installToolbar();
    }

    function PatchedTabulator(element, options) {
        patchOptions(options);
        const instance = new OriginalTabulator(element, options);
        table = instance;

        const originalGetRows = instance.getRows.bind(instance);
        instance.getRows = (...args) => originalGetRows(...args).map(patchRowComponent);
        window.shiftHelperEventGrid = instance;
        window.setTimeout(() => installInteractionHandlers(instance), 0);
        return instance;
    }

    Object.setPrototypeOf(PatchedTabulator, OriginalTabulator);
    PatchedTabulator.prototype = OriginalTabulator.prototype;
    window.Tabulator = PatchedTabulator;
})();
