"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const dataElement = document.getElementById("event-journal-data");
    const suggestionsElement = document.getElementById("event-journal-suggestions");
    const saveState = document.getElementById("journal-save-state");
    const saveStateText = saveState?.querySelector(".save-state__text");
    const recordCount = document.getElementById("journal-record-count");
    const searchInput = document.getElementById("journal-search");
    const filterToggle = document.getElementById("toggle-header-filters");
    const resetLayoutButton = document.getElementById("reset-grid-layout");

    if (
        !root
        || !dataElement
        || !suggestionsElement
        || !saveState
        || !saveStateText
        || typeof window.Tabulator !== "function"
    ) {
        return;
    }

    const initialRows = JSON.parse(dataElement.textContent || "[]");
    const suggestions = JSON.parse(suggestionsElement.textContent || "{}");
    const fieldOrder = [
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
    const editableFields = fieldOrder.filter(
        (field) => !["downtime", "downtime_losses_rub"].includes(field),
    );
    const operationalFields = editableFields.filter(
        (field) => !["start_date", "start_time"].includes(field),
    );
    const requiredFields = ["start_date", "start_time", "asset_label", "description"];
    const suggestionFields = new Set([
        "asset_label",
        "description",
        "reason",
        "actions",
        "performer",
        "author",
    ]);
    const multilineFields = new Set(["description", "reason", "actions"]);
    const draftBatchSize = 80;
    const saveTimers = new Map();
    const saveQueues = new Map();
    const alignmentKey = "shift-helper-event-cell-alignment-v3";
    const fillKey = "shift-helper-event-cell-fill-v3";
    const rulesKey = "shift-helper-event-format-rules-v3";
    const filterVisibilityKey = "shift-helper-event-header-filter-visible-v3";
    const alignmentStore = loadJson(alignmentKey, {});
    const fillStore = loadJson(fillKey, {});
    const formatRules = loadJson(rulesKey, []);
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
        downtime: {horizontal: "center", vertical: "middle"},
        author: {horizontal: "left", vertical: "middle"},
        downtime_losses_rub: {horizontal: "right", vertical: "middle"},
    };

    let table = null;
    let activeCell = null;
    let selectedRow = null;
    let pendingSeed = null;
    let internalClipboard = "";
    let draftSequence = 0;
    let normalizing = false;
    let addingDraftRows = false;
    let currentStatus = root.dataset.selectedStatus || "all";
    let currentSearch = "";
    let headerFiltersVisible = loadJson(filterVisibilityKey, true) !== false;
    let defaultColumnLayout = null;

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
            // Presentation settings are optional and must never block operator input.
        }
    }

    function isRealTextControl(target) {
        if (!(target instanceof Element)) {
            return false;
        }
        if (target.closest(".journal-stable-editor")) {
            return true;
        }
        if (target.closest("#journal-search, .tabulator-header-filter, .format-rules-dialog")) {
            return true;
        }
        return (
            !root.contains(target)
            && (
                target instanceof HTMLInputElement
                || target instanceof HTMLTextAreaElement
                || target instanceof HTMLSelectElement
                || target.isContentEditable
            )
        );
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

    function makeDraftRow() {
        draftSequence += 1;
        return {
            _draft: true,
            _rowKey: `draft-${Date.now()}-${draftSequence}`,
            _saving: false,
            _saveError: false,
            revision: 0,
            status: "draft",
            start_date: "",
            start_time: "",
            asset_label: "",
            description: "",
            reason: "",
            actions: "",
            performer: "",
            end_date: "",
            end_time: "",
            downtime: "",
            author: "",
            downtime_losses_rub: "",
        };
    }

    function makeDraftRows(count) {
        return Array.from({length: count}, () => makeDraftRow());
    }

    function buildInitialData() {
        return [
            ...initialRows.map((row) => ({
                ...row,
                _draft: false,
                _rowKey: `event-${row.id}`,
                _saving: false,
                _saveError: false,
            })),
            ...makeDraftRows(draftBatchSize),
        ];
    }

    function isMeaningfulDraft(data) {
        return operationalFields.some((field) => String(data[field] ?? "").trim() !== "");
    }

    function requiredFieldsComplete(data) {
        return requiredFields.every((field) => String(data[field] ?? "").trim() !== "");
    }

    function setSaveState(state, message) {
        saveState.dataset.state = state;
        saveStateText.textContent = message;
    }

    function updateRecordCount() {
        if (!table || !recordCount) {
            return;
        }
        const all = table.getData().filter((row) => !row._draft).length;
        const visible = table.getRows("active").filter((row) => !row.getData()._draft).length;
        recordCount.textContent = all === visible
            ? `Записей: ${all}`
            : `Записей: ${all} · показано: ${visible}`;
    }

    function previousRowValue(row, field) {
        const rows = table?.getRows("active") || [];
        const index = rows.indexOf(row);
        return index > 0 ? rows[index - 1].getData()[field] ?? "" : "";
    }

    function parseDate(value) {
        const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(value);
        if (!match) {
            return null;
        }
        const parsed = new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1]));
        return Number.isNaN(parsed.getTime()) ? null : parsed;
    }

    function parseTime(value) {
        const match = /^(\d{2}):(\d{2})$/.exec(value);
        if (!match) {
            return null;
        }
        const hours = Number(match[1]);
        const minutes = Number(match[2]);
        if (hours > 23 || minutes > 59) {
            return null;
        }
        const parsed = new Date();
        parsed.setHours(hours, minutes, 0, 0);
        return parsed;
    }

    function normalizeDate(value, row) {
        const cleaned = String(value ?? "").trim();
        if (!cleaned) {
            return "";
        }
        if (cleaned === "!") {
            return currentDate();
        }
        if (/^\+\d+$/.test(cleaned)) {
            const base = parseDate(String(previousRowValue(row, "start_date"))) || new Date();
            base.setDate(base.getDate() + Number(cleaned.slice(1)));
            return currentDate(base);
        }
        const digits = cleaned.replace(/\D/g, "");
        if (digits.length === 4) {
            return `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${new Date().getFullYear()}`;
        }
        if (digits.length === 6) {
            return `${digits.slice(0, 2)}.${digits.slice(2, 4)}.20${digits.slice(4, 6)}`;
        }
        if (digits.length === 8) {
            return `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4, 8)}`;
        }
        return cleaned;
    }

    function normalizeTime(value, row, field) {
        const cleaned = String(value ?? "").trim();
        if (!cleaned) {
            return "";
        }
        if (cleaned === "!") {
            return currentTime();
        }
        if (/^\+\d+$/.test(cleaned)) {
            const base = parseTime(String(previousRowValue(row, field))) || new Date();
            base.setMinutes(base.getMinutes() + Number(cleaned.slice(1)));
            return currentTime(base);
        }
        const digits = cleaned.replace(/\D/g, "");
        if (/^\d{3,4}$/.test(cleaned)) {
            const padded = digits.padStart(4, "0");
            return `${padded.slice(0, 2)}:${padded.slice(2, 4)}`;
        }
        return cleaned;
    }

    function normalizeCellValue(cell) {
        const field = cell.getField();
        const row = cell.getRow();
        let value = String(cell.getValue() ?? "");
        if (value.trim() === ".") {
            value = String(previousRowValue(row, field) ?? "");
        }
        if (["start_date", "end_date"].includes(field)) {
            return normalizeDate(value, row);
        }
        if (["start_time", "end_time"].includes(field)) {
            return normalizeTime(value, row, field);
        }
        return value;
    }

    function payloadForRow(data) {
        const payload = {revision: Number(data.revision || 0)};
        editableFields.forEach((field) => {
            payload[field] = data[field] ?? "";
        });
        return payload;
    }

    async function readResponse(response) {
        let payload;
        try {
            payload = await response.json();
        } catch (_error) {
            payload = {ok: false, error: "Приложение вернуло некорректный ответ."};
        }
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || "Не удалось сохранить строку.");
        }
        return payload;
    }

    function migrateStore(store, oldKey, newKey, storageKey) {
        if (oldKey === newKey || !store[oldKey]) {
            return;
        }
        store[newKey] = {...(store[newKey] || {}), ...store[oldKey]};
        delete store[oldKey];
        saveJson(storageKey, store);
    }

    function addSuggestion(field, value) {
        const cleaned = String(value ?? "").trim();
        const values = suggestions[field];
        if (!cleaned || !Array.isArray(values) || values.includes(cleaned)) {
            return;
        }
        values.push(cleaned);
        values.sort((left, right) => left.localeCompare(right, "ru"));
        rebuildDatalist(field);
    }

    async function saveRowOnce(row) {
        const data = row.getData();
        const isDraft = Boolean(data._draft);
        if (isDraft && (!isMeaningfulDraft(data) || !requiredFieldsComplete(data))) {
            return false;
        }

        await row.update({_saving: true, _saveError: false});
        row.reformat();
        setSaveState("saving", "Сохранение…");

        try {
            const response = await fetch(
                isDraft ? root.dataset.createUrl : `${root.dataset.updateBase}/${data.id}/row`,
                {
                    method: isDraft ? "POST" : "PATCH",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(payloadForRow(row.getData())),
                },
            );
            const payload = await readResponse(response);
            const oldKey = data._rowKey;
            const newKey = `event-${payload.row.id}`;
            migrateStore(alignmentStore, oldKey, newKey, alignmentKey);
            migrateStore(fillStore, oldKey, newKey, fillKey);
            await row.update({
                ...payload.row,
                _draft: false,
                _rowKey: newKey,
                _saving: false,
                _saveError: false,
            });
            suggestionFields.forEach((field) => addSuggestion(field, payload.row[field]));
            ensureDraftRows();
            applyCombinedFilter();
            row.reformat();
            setSaveState("saved", "Все изменения сохранены");
            updateRecordCount();
            return true;
        } catch (error) {
            await row.update({_saving: false, _saveError: true});
            row.reformat();
            setSaveState("error", error.message);
            return false;
        }
    }

    function queueSave(row) {
        const rowKey = row.getData()._rowKey;
        const previous = saveQueues.get(rowKey) || Promise.resolve();
        const next = previous
            .catch(() => undefined)
            .then(() => saveRowOnce(row))
            .finally(() => {
                if (saveQueues.get(rowKey) === next) {
                    saveQueues.delete(rowKey);
                }
            });
        saveQueues.set(rowKey, next);
        return next;
    }

    function scheduleSave(row, delay = 260) {
        const rowKey = row.getData()._rowKey;
        window.clearTimeout(saveTimers.get(rowKey));
        setSaveState("dirty", "Есть несохранённые изменения");
        const timer = window.setTimeout(() => {
            saveTimers.delete(rowKey);
            void queueSave(row);
        }, delay);
        saveTimers.set(rowKey, timer);
    }

    function ensureDraftRows() {
        const draftCount = table.getData().filter((row) => row._draft).length;
        if (draftCount < draftBatchSize) {
            void table.addData(makeDraftRows(draftBatchSize - draftCount), false);
        }
    }

    function datalistId(field) {
        return `journal-suggestions-${field}`;
    }

    function rebuildDatalist(field) {
        let list = document.getElementById(datalistId(field));
        if (!list) {
            list = document.createElement("datalist");
            list.id = datalistId(field);
            document.body.appendChild(list);
        }
        list.replaceChildren();
        (suggestions[field] || []).slice(0, 200).forEach((value) => {
            const option = document.createElement("option");
            option.value = value;
            list.appendChild(option);
        });
    }

    suggestionFields.forEach(rebuildDatalist);

    function rowAndFieldTarget(cell, direction) {
        const rows = table.getRows("active");
        const rowIndex = rows.indexOf(cell.getRow());
        const fieldIndex = editableFields.indexOf(cell.getField());
        if (rowIndex < 0 || fieldIndex < 0) {
            return null;
        }
        if (direction === "down") {
            return rows[rowIndex + 1]?.getCell(cell.getField()) || null;
        }
        if (direction === "next") {
            return rows[rowIndex].getCell(editableFields[fieldIndex + 1])
                || rows[rowIndex + 1]?.getCell(editableFields[0])
                || null;
        }
        if (direction === "previous") {
            return rows[rowIndex].getCell(editableFields[fieldIndex - 1])
                || rows[rowIndex - 1]?.getCell(editableFields.at(-1))
                || null;
        }
        return null;
    }

    function clearRanges() {
        (table.getRanges?.() || []).forEach((range) => range.remove());
    }

    function clearSelectedRow() {
        if (selectedRow) {
            selectedRow.getElement().classList.remove("journal-row--selected");
        }
        selectedRow = null;
    }

    function selectCell(cell) {
        if (!cell) {
            return;
        }
        clearSelectedRow();
        clearRanges();
        table.addRange(cell, cell);
        activeCell = cell;
        cell.getElement().scrollIntoView({block: "nearest", inline: "nearest"});
    }

    function journalEditor(cell, onRendered, success, cancel, params = {}) {
        const multiline = Boolean(params.multiline);
        const editor = document.createElement(multiline ? "textarea" : "input");
        const data = cell.getRow().getData();
        const seeded = pendingSeed
            && pendingSeed.rowKey === data._rowKey
            && pendingSeed.field === cell.getField()
            ? pendingSeed.text
            : null;
        pendingSeed = null;
        editor.className = "journal-stable-editor";
        editor.value = seeded === null ? String(cell.getValue() ?? "") : seeded;
        editor.spellcheck = multiline;
        editor.autocomplete = "off";
        if (params.suggestionField) {
            editor.setAttribute("list", datalistId(params.suggestionField));
        }

        let finished = false;
        const finish = (commit, direction = null) => {
            if (finished) {
                return;
            }
            finished = true;
            const next = direction ? rowAndFieldTarget(cell, direction) : null;
            if (commit) {
                success(editor.value);
            } else {
                cancel();
            }
            window.setTimeout(() => {
                if (next) {
                    selectCell(next);
                } else {
                    activeCell = cell;
                }
            }, 0);
        };

        editor.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                event.preventDefault();
                event.stopImmediatePropagation();
                finish(false);
                return;
            }
            if (event.key === "Enter") {
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
        }, true);
        editor.addEventListener("blur", () => finish(true));

        onRendered(() => {
            editor.focus({preventScroll: true});
            const caret = editor.value.length;
            editor.setSelectionRange(caret, caret);
        });
        return editor;
    }

    function alignmentFor(data, field) {
        return {
            ...defaultAlignment[field],
            ...(alignmentStore[data._rowKey]?.[field] || {}),
        };
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
        if (rule.operator === "empty") {
            return value.trim() === "";
        }
        if (rule.operator === "nonempty") {
            return value.trim() !== "";
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
        const manual = fillStore[data._rowKey]?.[cell.getField()];
        if (manual) {
            return manual;
        }
        return formatRules.find((rule) => ruleMatches(rule, cell.getField(), cell.getValue()))
            ?.color || "";
    }

    function journalFormatter(cell, params, onRendered) {
        const element = document.createElement("div");
        element.className = "journal-cell-value";
        if (params?.multiline) {
            element.classList.add("journal-cell-value--multiline");
        }
        if (params?.currency) {
            element.classList.add("journal-cell-value--currency");
            const raw = String(cell.getValue() ?? "").trim();
            if (raw) {
                const numeric = Number(raw.replace(/\s/g, "").replace(",", "."));
                element.textContent = Number.isFinite(numeric)
                    ? `${new Intl.NumberFormat("ru-RU", {maximumFractionDigits: 0}).format(numeric)} ₽`
                    : raw;
            }
        } else {
            element.textContent = String(cell.getValue() ?? "");
        }
        onRendered(() => {
            const alignment = alignmentFor(cell.getRow().getData(), cell.getField());
            element.dataset.horizontal = alignment.horizontal;
            element.dataset.vertical = alignment.vertical;
            const fill = fillForCell(cell);
            cell.getElement().style.backgroundColor = fill;
            element.style.color = fill ? contrastingTextColor(fill) : "";
        });
        return element;
    }

    function selectRow(row) {
        clearSelectedRow();
        clearRanges();
        selectedRow = row;
        row.getElement().classList.add("journal-row--selected");
        const first = row.getCell(editableFields[0]);
        const last = row.getCell(editableFields.at(-1));
        activeCell = first;
        if (first && last) {
            table.addRange(first, last);
        }
    }

    function rangeMatrix() {
        if (selectedRow) {
            return [editableFields.map((field) => selectedRow.getCell(field))];
        }
        const range = table.getRanges?.().at(-1);
        if (!range) {
            return activeCell ? [[activeCell]] : [];
        }
        const cells = range.getCells?.() || [];
        return cells.length && !Array.isArray(cells[0]) ? [cells] : cells;
    }

    function matrixText(matrix = rangeMatrix()) {
        return matrix
            .map((row) => row.map((cell) => String(cell?.getValue() ?? "")).join("\t"))
            .join("\n");
    }

    function selectedEditableCells() {
        return [...new Set(rangeMatrix().flat())]
            .filter((cell) => cell && editableFields.includes(cell.getField()));
    }

    function clearSelection() {
        if (selectedRow && !selectedRow.getData()._draft) {
            setSaveState("error", "Сохранённую строку нельзя очистить целиком без удаления записи.");
            return;
        }
        const rows = new Set();
        normalizing = true;
        selectedEditableCells().forEach((cell) => {
            cell.setValue("", true);
            rows.add(cell.getRow());
        });
        normalizing = false;
        rows.forEach((row) => scheduleSave(row, 80));
    }

    async function ensurePasteRows(startRow, rowCount) {
        let rows = table.getRows();
        const startIndex = rows.indexOf(startRow);
        const missing = (startIndex + rowCount) - rows.length;
        if (missing > 0) {
            await table.addData(makeDraftRows(missing), false);
            rows = table.getRows();
        }
        return {rows, startIndex};
    }

    async function pasteText(text) {
        const startCell = selectedRow?.getCell(editableFields[0]) || activeCell;
        if (!startCell || !text) {
            return;
        }
        const lines = text.replace(/\r/g, "").replace(/\n$/, "").split("\n");
        const values = lines.map((line) => line.split("\t"));
        const startFieldIndex = selectedRow ? 0 : editableFields.indexOf(startCell.getField());
        if (startFieldIndex < 0) {
            return;
        }
        const {rows, startIndex} = await ensurePasteRows(startCell.getRow(), values.length);
        const changedRows = new Set();
        normalizing = true;
        values.forEach((rowValues, rowOffset) => {
            const targetRow = rows[startIndex + rowOffset];
            rowValues.forEach((value, columnOffset) => {
                const field = editableFields[startFieldIndex + columnOffset];
                const targetCell = field ? targetRow?.getCell(field) : null;
                if (targetCell) {
                    targetCell.setValue(value, true);
                    changedRows.add(targetRow);
                }
            });
        });
        normalizing = false;
        changedRows.forEach((row) => {
            const data = row.getData();
            if (isMeaningfulDraft(data)) {
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
            }
            scheduleSave(row, 100);
        });
    }

    async function copyToSystemClipboard() {
        const text = matrixText();
        if (!text) {
            return;
        }
        internalClipboard = text;
        try {
            await navigator.clipboard.writeText(text);
            setSaveState("saved", selectedRow ? "Строка скопирована" : "Выделение скопировано");
        } catch (_error) {
            setSaveState("saved", "Скопировано во внутренний буфер приложения");
        }
    }

    async function pasteFromSystemClipboard() {
        let text = internalClipboard;
        try {
            text = await navigator.clipboard.readText() || text;
        } catch (_error) {
            // Use the application clipboard when browser clipboard read is unavailable.
        }
        await pasteText(text);
    }

    function copyValueFromAbove(cell) {
        normalizing = true;
        cell.setValue(previousRowValue(cell.getRow(), cell.getField()), true);
        normalizing = false;
        scheduleSave(cell.getRow(), 80);
    }

    function fillRange(direction) {
        const matrix = rangeMatrix();
        if (!matrix.length || !matrix[0]?.length) {
            return;
        }
        const rows = new Set();
        normalizing = true;
        if (direction === "down") {
            const source = matrix[0].map((cell) => cell.getValue());
            matrix.slice(1).forEach((row) => {
                row.forEach((cell, index) => {
                    if (editableFields.includes(cell.getField())) {
                        cell.setValue(source[index] ?? "", true);
                        rows.add(cell.getRow());
                    }
                });
            });
        } else {
            matrix.forEach((row) => {
                const source = row[0]?.getValue() ?? "";
                row.slice(1).forEach((cell) => {
                    if (editableFields.includes(cell.getField())) {
                        cell.setValue(source, true);
                        rows.add(cell.getRow());
                    }
                });
            });
        }
        normalizing = false;
        rows.forEach((row) => scheduleSave(row, 80));
    }

    function setActiveCell(cell) {
        clearSelectedRow();
        activeCell = cell;
    }

    const cellMenu = [
        {label: "Копировать", action: (_event, cell) => {
            setActiveCell(cell);
            void copyToSystemClipboard();
        }},
        {label: "Вырезать", action: (_event, cell) => {
            setActiveCell(cell);
            void copyToSystemClipboard().then(clearSelection);
        }},
        {label: "Вставить", action: (_event, cell) => {
            setActiveCell(cell);
            void pasteFromSystemClipboard();
        }},
        {separator: true},
        {label: "Значение из строки выше", action: (_event, cell) => copyValueFromAbove(cell)},
        {label: "Заполнить вниз", action: () => fillRange("down")},
        {label: "Заполнить вправо", action: () => fillRange("right")},
        {separator: true},
        {label: "Очистить выделение", action: () => clearSelection()},
    ];

    const rowHeaderMenu = [
        {label: "Копировать строку", action: (_event, cell) => {
            selectRow(cell.getRow());
            void copyToSystemClipboard();
        }},
        {label: "Вставить строку", action: (_event, cell) => {
            selectRow(cell.getRow());
            void pasteFromSystemClipboard();
        }},
        {separator: true},
        {label: "Очистить черновую строку", action: (_event, cell) => {
            selectRow(cell.getRow());
            clearSelection();
        }},
    ];

    function column({title, field, width, minWidth, frozen = false, multiline = false, currency = false}) {
        return {
            title,
            field,
            width,
            minWidth,
            frozen,
            editor: editableFields.includes(field) ? journalEditor : false,
            editorParams: {
                multiline,
                suggestionField: suggestionFields.has(field) ? field : null,
            },
            headerFilter: "input",
            headerFilterPlaceholder: title,
            formatter: journalFormatter,
            formatterParams: {multiline, currency},
            variableHeight: multiline,
            contextMenu: cellMenu,
        };
    }

    const columns = [
        column({title: "Дата останова", field: "start_date", width: 112, minWidth: 96, frozen: true}),
        column({title: "Время", field: "start_time", width: 78, minWidth: 68, frozen: true}),
        column({title: "№ ВЭУ / оборудование", field: "asset_label", width: 158, minWidth: 120, frozen: true}),
        column({title: "Описание события", field: "description", width: 330, minWidth: 180, multiline: true}),
        column({title: "Причина", field: "reason", width: 270, minWidth: 160, multiline: true}),
        column({title: "Действия персонала", field: "actions", width: 300, minWidth: 180, multiline: true}),
        column({title: "Исполнитель", field: "performer", width: 170, minWidth: 120}),
        column({title: "Дата пуска", field: "end_date", width: 112, minWidth: 96}),
        column({title: "Время", field: "end_time", width: 78, minWidth: 68}),
        column({title: "Простой", field: "downtime", width: 118, minWidth: 90}),
        column({title: "Кто внёс запись", field: "author", width: 170, minWidth: 120}),
        column({
            title: "Потери от простоя, руб.",
            field: "downtime_losses_rub",
            width: 145,
            minWidth: 110,
            currency: true,
        }),
    ];

    function rowFormatter(row) {
        const element = row.getElement();
        const data = row.getData();
        element.classList.toggle("journal-row--draft", Boolean(data._draft));
        element.classList.toggle("journal-row--closed", data.status === "closed");
        element.classList.toggle("journal-row--saving", Boolean(data._saving));
        element.classList.toggle("journal-row--error", Boolean(data._saveError));
        element.classList.toggle("journal-row--selected", row === selectedRow);
    }

    table = new window.Tabulator(root, {
        data: buildInitialData(),
        index: "_rowKey",
        height: "100%",
        layout: "fitDataFill",
        renderHorizontal: "virtual",
        movableColumns: true,
        resizableRows: true,
        resizableColumnFit: true,
        history: true,
        editTriggerEvent: "dblclick",
        selectableRange: 1,
        selectableRangeColumns: true,
        selectableRangeRows: true,
        selectableRangeClearCells: false,
        persistence: {
            columns: true,
            sort: true,
            headerFilter: true,
        },
        persistenceID: "shift-helper-event-grid-v3",
        persistenceMode: "local",
        headerFilterLiveFilterDelay: 180,
        rowHeight: 34,
        rowHeader: {
            formatter: "rownum",
            headerSort: false,
            frozen: true,
            width: 46,
            minWidth: 46,
            resizable: false,
            hozAlign: "center",
            cssClass: "journal-row-number",
            editor: false,
            cellClick: (_event, cell) => selectRow(cell.getRow()),
            contextMenu: rowHeaderMenu,
        },
        columnDefaults: {
            resizable: "header",
            headerSort: true,
            vertAlign: "middle",
        },
        rowFormatter,
        columns,
    });
    window.shiftHelperEventGrid = table;

    function combinedFilter(data) {
        if (data._draft) {
            return currentStatus !== "closed" && currentSearch === "";
        }
        if (currentStatus !== "all" && data.status !== currentStatus) {
            return false;
        }
        if (!currentSearch) {
            return true;
        }
        return fieldOrder
            .map((field) => String(data[field] ?? ""))
            .join("\n")
            .toLocaleLowerCase("ru")
            .includes(currentSearch);
    }

    function applyCombinedFilter() {
        table.setFilter(combinedFilter);
        updateRecordCount();
    }

    function updateStatusButtons() {
        document.querySelectorAll("[data-status-filter]").forEach((button) => {
            button.setAttribute("aria-pressed", String(button.dataset.statusFilter === currentStatus));
        });
    }

    table.on("tableBuilt", () => {
        defaultColumnLayout = columns.map((definition) => ({
            title: definition.title,
            field: definition.field,
            width: definition.width,
            visible: true,
            frozen: Boolean(definition.frozen),
        }));
        root.classList.toggle("header-filters-hidden", !headerFiltersVisible);
        filterToggle?.setAttribute("aria-pressed", String(headerFiltersVisible));
        applyCombinedFilter();
        updateStatusButtons();
        updateRecordCount();

        const holder = root.querySelector(".tabulator-tableholder");
        holder?.addEventListener("scroll", () => {
            const remaining = holder.scrollHeight - holder.scrollTop - holder.clientHeight;
            if (remaining < 700 && !addingDraftRows) {
                addingDraftRows = true;
                void table.addData(makeDraftRows(draftBatchSize), false).finally(() => {
                    addingDraftRows = false;
                });
            }
        });
    });

    table.on("cellClick", (_event, cell) => {
        setActiveCell(cell);
    });

    table.on("rangeChanged", (range) => {
        if (selectedRow) {
            return;
        }
        const bounds = range.getBounds?.();
        activeCell = bounds?.end || bounds?.bottomRight || activeCell;
    });

    table.on("cellEdited", (cell) => {
        activeCell = cell;
        if (normalizing) {
            return;
        }
        const normalized = normalizeCellValue(cell);
        if (normalized !== String(cell.getValue() ?? "")) {
            normalizing = true;
            cell.setValue(normalized, true);
            normalizing = false;
        }
        const row = cell.getRow();
        const data = row.getData();
        if (data._draft && isMeaningfulDraft(data)) {
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
        }
        scheduleSave(row);
    });

    table.on("dataFiltered", updateRecordCount);

    document.addEventListener("keydown", (event) => {
        if (isRealTextControl(event.target)) {
            return;
        }
        const modifier = event.ctrlKey || event.metaKey;
        const key = event.key.toLocaleLowerCase("ru");
        if (modifier && key === "f" && activeCell) {
            event.preventDefault();
            searchInput?.focus();
            searchInput?.select();
            return;
        }
        if (modifier && key === "d" && activeCell) {
            event.preventDefault();
            fillRange("down");
            return;
        }
        if (modifier && key === "r" && activeCell) {
            event.preventDefault();
            fillRange("right");
            return;
        }
        if (!activeCell || !editableFields.includes(activeCell.getField())) {
            return;
        }
        if (event.key === "F2") {
            event.preventDefault();
            activeCell.edit();
            return;
        }
        if (event.key === "Enter") {
            event.preventDefault();
            selectCell(rowAndFieldTarget(activeCell, "down") || activeCell);
            return;
        }
        if (!modifier && !event.altKey && event.key.length === 1) {
            event.preventDefault();
            event.stopImmediatePropagation();
            pendingSeed = {
                rowKey: activeCell.getRow().getData()._rowKey,
                field: activeCell.getField(),
                text: event.key,
            };
            activeCell.edit();
        }
    }, true);

    document.addEventListener("copy", (event) => {
        if (!activeCell || isRealTextControl(event.target) || !event.clipboardData) {
            return;
        }
        const text = matrixText();
        if (!text) {
            return;
        }
        event.preventDefault();
        event.clipboardData.setData("text/plain", text);
        internalClipboard = text;
        setSaveState("saved", selectedRow ? "Строка скопирована" : "Выделение скопировано");
    });

    document.addEventListener("cut", (event) => {
        if (!activeCell || isRealTextControl(event.target) || !event.clipboardData) {
            return;
        }
        const text = matrixText();
        if (!text) {
            return;
        }
        event.preventDefault();
        event.clipboardData.setData("text/plain", text);
        internalClipboard = text;
        clearSelection();
    });

    document.addEventListener("paste", (event) => {
        if (!activeCell || isRealTextControl(event.target) || !event.clipboardData) {
            return;
        }
        const text = event.clipboardData.getData("text/plain");
        if (!text) {
            return;
        }
        event.preventDefault();
        internalClipboard = text;
        void pasteText(text);
    });

    function applyAlignment(axis, value) {
        const cells = selectedEditableCells();
        if (!cells.length) {
            setSaveState("error", "Сначала выделите ячейку или диапазон.");
            return;
        }
        const rows = new Set();
        cells.forEach((cell) => {
            const data = cell.getRow().getData();
            alignmentStore[data._rowKey] ||= {};
            alignmentStore[data._rowKey][cell.getField()] ||= {};
            alignmentStore[data._rowKey][cell.getField()][axis] = value;
            rows.add(cell.getRow());
        });
        saveJson(alignmentKey, alignmentStore);
        rows.forEach((row) => row.reformat());
        setSaveState("saved", "Выравнивание сохранено");
    }

    function applyManualFill(color) {
        const rows = new Set();
        selectedEditableCells().forEach((cell) => {
            const data = cell.getRow().getData();
            fillStore[data._rowKey] ||= {};
            if (color) {
                fillStore[data._rowKey][cell.getField()] = color;
            } else {
                delete fillStore[data._rowKey][cell.getField()];
                if (!Object.keys(fillStore[data._rowKey]).length) {
                    delete fillStore[data._rowKey];
                }
            }
            rows.add(cell.getRow());
        });
        saveJson(fillKey, fillStore);
        rows.forEach((row) => row.reformat());
    }

    document.querySelectorAll("[data-status-filter]").forEach((button) => {
        button.addEventListener("click", () => {
            currentStatus = button.dataset.statusFilter || "all";
            updateStatusButtons();
            applyCombinedFilter();
        });
    });

    searchInput?.addEventListener("input", () => {
        currentSearch = searchInput.value.trim().toLocaleLowerCase("ru");
        applyCombinedFilter();
    });

    filterToggle?.addEventListener("click", () => {
        headerFiltersVisible = !headerFiltersVisible;
        root.classList.toggle("header-filters-hidden", !headerFiltersVisible);
        filterToggle.setAttribute("aria-pressed", String(headerFiltersVisible));
        saveJson(filterVisibilityKey, headerFiltersVisible);
        table.redraw(true);
    });

    document.querySelectorAll("[data-align-horizontal]").forEach((button) => {
        button.addEventListener("click", () => applyAlignment(
            "horizontal",
            button.dataset.alignHorizontal,
        ));
    });

    document.querySelectorAll("[data-align-vertical]").forEach((button) => {
        button.addEventListener("click", () => applyAlignment(
            "vertical",
            button.dataset.alignVertical,
        ));
    });

    const fillColor = document.getElementById("cell-fill-color");
    document.getElementById("apply-cell-fill")?.addEventListener("click", () => {
        applyManualFill(fillColor?.value || "#fff2cc");
    });
    document.getElementById("clear-cell-fill")?.addEventListener("click", () => {
        applyManualFill("");
    });

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
        formatRules.forEach((rule) => {
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
                    saveJson(rulesKey, formatRules);
                    renderRules();
                    table.getRows().forEach((tableRow) => tableRow.reformat());
                }
            });
            row.append(swatch, description, remove);
            list.appendChild(row);
        });
    }

    const rulesDialog = document.getElementById("format-rules-dialog");
    document.getElementById("open-format-rules")?.addEventListener("click", () => {
        renderRules();
        rulesDialog?.showModal();
    });
    document.getElementById("add-format-rule")?.addEventListener("click", () => {
        const field = document.getElementById("format-rule-column")?.value || "*";
        const operator = document.getElementById("format-rule-operator")?.value || "contains";
        const input = document.getElementById("format-rule-value");
        const value = input?.value.trim() || "";
        if (!["empty", "nonempty"].includes(operator) && !value) {
            input?.focus();
            return;
        }
        formatRules.push({
            id: `rule-${Date.now()}-${Math.random().toString(16).slice(2)}`,
            field,
            operator,
            value,
            color: document.getElementById("format-rule-color")?.value || "#f4cccc",
        });
        saveJson(rulesKey, formatRules);
        if (input) {
            input.value = "";
        }
        renderRules();
        table.getRows().forEach((row) => row.reformat());
    });

    resetLayoutButton?.addEventListener("click", () => {
        if (defaultColumnLayout) {
            void table.setColumnLayout(defaultColumnLayout);
        }
        table.clearHeaderFilter();
        table.clearSort();
        currentStatus = "all";
        currentSearch = "";
        if (searchInput) {
            searchInput.value = "";
        }
        Object.keys(alignmentStore).forEach((key) => delete alignmentStore[key]);
        Object.keys(fillStore).forEach((key) => delete fillStore[key]);
        saveJson(alignmentKey, alignmentStore);
        saveJson(fillKey, fillStore);
        clearSelectedRow();
        updateStatusButtons();
        applyCombinedFilter();
        table.getRows().forEach((row) => row.reformat());
        setSaveState("saved", "Стандартный вид восстановлен");
    });

    window.addEventListener("beforeunload", (event) => {
        if (saveTimers.size || saveQueues.size) {
            event.preventDefault();
            event.returnValue = "";
        }
    });
})();
