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
    const suggestionValues = JSON.parse(suggestionsElement.textContent || "{}");
    const fields = [
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
    const editableFields = fields.filter(
        (field) => !["downtime", "downtime_losses_rub"].includes(field),
    );
    const operationalFields = editableFields.filter(
        (field) => !["start_date", "start_time"].includes(field),
    );
    const requiredFields = ["start_date", "start_time", "asset_label", "description"];
    const multilineFields = new Set(["description", "reason", "actions"]);
    const suggestionFields = new Set([
        "asset_label",
        "description",
        "reason",
        "actions",
        "performer",
        "author",
    ]);
    const draftBatchSize = 80;
    const saveTimers = new Map();
    const saveQueues = new Map();
    const persistenceId = "shift-helper-event-grid-v2";
    const headerFilterStorageKey = "shift-helper-event-header-filter-visible-v2";
    const alignmentStorageKey = "shift-helper-event-cell-alignment-v2";
    const fillStorageKey = "shift-helper-event-cell-fill-v2";
    const rulesStorageKey = "shift-helper-event-format-rules-v2";
    const alignmentStore = loadJson(alignmentStorageKey, {});
    const fillStore = loadJson(fillStorageKey, {});
    const formatRules = loadJson(rulesStorageKey, []);
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

    let draftSequence = 0;
    let table = null;
    let activeCell = null;
    let pendingTypedSeed = null;
    let normalizingCell = false;
    let addingDraftRows = false;
    let currentStatus = root.dataset.selectedStatus || "all";
    let currentSearch = "";
    let headerFiltersVisible = loadJson(headerFilterStorageKey, true) !== false;
    let defaultColumnLayout = null;

    root.tabIndex = 0;

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
            // Workstation-local presentation settings must never block journal input.
        }
    }

    function pad(value) {
        return String(value).padStart(2, "0");
    }

    function localDateValue(now = new Date()) {
        return `${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${now.getFullYear()}`;
    }

    function localTimeValue(now = new Date()) {
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

    function initialData() {
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

    function parseJournalDate(value) {
        const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(value);
        if (!match) {
            return null;
        }
        const parsed = new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1]));
        return Number.isNaN(parsed.getTime()) ? null : parsed;
    }

    function parseJournalTime(value) {
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
            return localDateValue();
        }
        if (/^\+\d+$/.test(cleaned)) {
            const base = parseJournalDate(String(previousRowValue(row, "start_date"))) || new Date();
            base.setDate(base.getDate() + Number(cleaned.slice(1)));
            return localDateValue(base);
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
            return localTimeValue();
        }
        if (/^\+\d+$/.test(cleaned)) {
            const base = parseJournalTime(String(previousRowValue(row, field))) || new Date();
            base.setMinutes(base.getMinutes() + Number(cleaned.slice(1)));
            return localTimeValue(base);
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

    function migratePresentationStore(store, oldKey, newKey, storageKey) {
        if (oldKey === newKey || !store[oldKey]) {
            return;
        }
        store[newKey] = {...(store[newKey] || {}), ...store[oldKey]};
        delete store[oldKey];
        saveJson(storageKey, store);
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
            migratePresentationStore(alignmentStore, oldKey, newKey, alignmentStorageKey);
            migratePresentationStore(fillStore, oldKey, newKey, fillStorageKey);
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
        const key = row.getData()._rowKey;
        const previous = saveQueues.get(key) || Promise.resolve();
        const next = previous
            .catch(() => undefined)
            .then(() => saveRowOnce(row))
            .finally(() => {
                if (saveQueues.get(key) === next) {
                    saveQueues.delete(key);
                }
            });
        saveQueues.set(key, next);
        return next;
    }

    function scheduleSave(row, delay = 260) {
        const key = row.getData()._rowKey;
        window.clearTimeout(saveTimers.get(key));
        setSaveState("dirty", "Есть несохранённые изменения");
        const timer = window.setTimeout(() => {
            saveTimers.delete(key);
            void queueSave(row);
        }, delay);
        saveTimers.set(key, timer);
    }

    function ensureDraftRows() {
        if (!table) {
            return;
        }
        const draftCount = table.getData().filter((row) => row._draft).length;
        if (draftCount < draftBatchSize) {
            void table.addData(makeDraftRows(draftBatchSize - draftCount), false);
        }
    }

    function addSuggestion(field, value) {
        const cleaned = String(value ?? "").trim();
        const values = suggestionValues[field];
        if (!cleaned || !Array.isArray(values) || values.includes(cleaned)) {
            return;
        }
        values.push(cleaned);
        values.sort((left, right) => left.localeCompare(right, "ru"));
        rebuildDatalist(field);
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
        (suggestionValues[field] || []).slice(0, 200).forEach((value) => {
            const option = document.createElement("option");
            option.value = value;
            list.appendChild(option);
        });
    }

    suggestionFields.forEach(rebuildDatalist);

    function finishEditor(cell, editor, success, cancel, commit, navigation, state) {
        if (state.finished) {
            return;
        }
        state.finished = true;
        if (commit) {
            success(editor.value);
        } else {
            cancel();
        }
        window.setTimeout(() => {
            if (navigation === "down") {
                cell.navigateDown();
            } else if (navigation === "next") {
                cell.navigateNext();
            } else if (navigation === "previous") {
                cell.navigatePrev();
            }
        }, 0);
    }

    function journalEditor(cell, onRendered, success, cancel, params = {}) {
        const multiline = Boolean(params.multiline);
        const editor = document.createElement(multiline ? "textarea" : "input");
        const data = cell.getRow().getData();
        const field = cell.getField();
        const seedMatches = pendingTypedSeed
            && pendingTypedSeed.rowKey === data._rowKey
            && pendingTypedSeed.field === field;
        editor.className = "journal-stable-editor";
        editor.value = seedMatches ? pendingTypedSeed.text : String(cell.getValue() ?? "");
        pendingTypedSeed = null;
        editor.autocomplete = "off";
        editor.spellcheck = multiline;
        if (params.suggestionField) {
            editor.setAttribute("list", datalistId(params.suggestionField));
        }

        const state = {finished: false};
        editor.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                event.preventDefault();
                event.stopImmediatePropagation();
                finishEditor(cell, editor, success, cancel, false, null, state);
                return;
            }
            if (event.key === "Enter") {
                if (multiline && event.shiftKey) {
                    return;
                }
                event.preventDefault();
                event.stopImmediatePropagation();
                finishEditor(cell, editor, success, cancel, true, "down", state);
                return;
            }
            if (event.key === "Tab") {
                event.preventDefault();
                event.stopImmediatePropagation();
                finishEditor(
                    cell,
                    editor,
                    success,
                    cancel,
                    true,
                    event.shiftKey ? "previous" : "next",
                    state,
                );
            }
        }, true);
        editor.addEventListener("blur", () => {
            finishEditor(cell, editor, success, cancel, true, null, state);
        });

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
            const data = cell.getRow().getData();
            const alignment = alignmentFor(data, cell.getField());
            element.dataset.horizontal = alignment.horizontal;
            element.dataset.vertical = alignment.vertical;
            const fill = fillForCell(cell);
            cell.getElement().style.backgroundColor = fill;
            element.style.color = fill ? contrastingTextColor(fill) : "";
        });
        return element;
    }

    function rangeMatrix() {
        const range = table?.getRanges?.().at(-1);
        if (!range) {
            return activeCell ? [[activeCell]] : [];
        }
        const cells = range.getCells?.() || [];
        return cells.length && !Array.isArray(cells[0]) ? [cells] : cells;
    }

    function selectedCells({editableOnly = false} = {}) {
        const cells = [...new Set(rangeMatrix().flat())];
        return editableOnly
            ? cells.filter((cell) => editableFields.includes(cell.getField()))
            : cells;
    }

    function applyAlignment(axis, value) {
        const cells = selectedCells();
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
        saveJson(alignmentStorageKey, alignmentStore);
        rows.forEach((row) => row.reformat());
        setSaveState("saved", "Выравнивание сохранено");
    }

    function applyManualFill(color) {
        const rows = new Set();
        selectedCells().forEach((cell) => {
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
        saveJson(fillStorageKey, fillStore);
        rows.forEach((row) => row.reformat());
    }

    function clearSelectedCells() {
        const rows = new Set();
        normalizingCell = true;
        selectedCells({editableOnly: true}).forEach((cell) => {
            cell.setValue("", true);
            rows.add(cell.getRow());
        });
        normalizingCell = false;
        rows.forEach((row) => scheduleSave(row, 80));
    }

    function copyValueFromAbove(cell) {
        normalizingCell = true;
        cell.setValue(previousRowValue(cell.getRow(), cell.getField()), true);
        normalizingCell = false;
        scheduleSave(cell.getRow(), 80);
    }

    function fillRange(direction) {
        const matrix = rangeMatrix();
        if (!matrix.length || !matrix[0]?.length) {
            return;
        }
        const rows = new Set();
        normalizingCell = true;
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
        normalizingCell = false;
        rows.forEach((row) => scheduleSave(row, 80));
    }

    function clearRanges() {
        (table?.getRanges?.() || []).forEach((range) => range.remove());
    }

    function selectRowRange(row) {
        clearRanges();
        const first = row.getCell(editableFields[0]);
        const last = row.getCell(editableFields.at(-1));
        if (first && last) {
            table.addRange(first, last);
            activeCell = first;
        }
    }

    async function pasteTextAtCell(startCell, text) {
        if (!startCell || !text) {
            return;
        }
        const rows = table.getRows("active");
        const startRowIndex = rows.indexOf(startCell.getRow());
        const startFieldIndex = editableFields.indexOf(startCell.getField());
        if (startRowIndex < 0 || startFieldIndex < 0) {
            return;
        }
        const matrix = text.replace(/\r/g, "").split("\n").map((line) => line.split("\t"));
        const changedRows = new Set();
        normalizingCell = true;
        matrix.forEach((values, rowOffset) => {
            const row = rows[startRowIndex + rowOffset];
            if (!row) {
                return;
            }
            values.forEach((value, columnOffset) => {
                const field = editableFields[startFieldIndex + columnOffset];
                const cell = field ? row.getCell(field) : null;
                if (cell) {
                    cell.setValue(value, true);
                    changedRows.add(row);
                }
            });
        });
        normalizingCell = false;
        changedRows.forEach((row) => scheduleSave(row, 80));
    }

    async function pasteFromClipboard(startCell) {
        try {
            const text = await navigator.clipboard.readText();
            await pasteTextAtCell(startCell, text);
        } catch (_error) {
            setSaveState("error", "Браузер не дал доступ к буферу. Используйте Ctrl+V.");
        }
    }

    const cellContextMenu = [
        {
            label: "Копировать",
            action: () => table.copyToClipboard("range"),
        },
        {
            label: "Вставить",
            action: (_event, cell) => void pasteFromClipboard(cell),
        },
        {separator: true},
        {
            label: "Значение из строки выше",
            action: (_event, cell) => copyValueFromAbove(cell),
        },
        {
            label: "Заполнить вниз",
            action: () => fillRange("down"),
        },
        {
            label: "Заполнить вправо",
            action: () => fillRange("right"),
        },
        {separator: true},
        {
            label: "Очистить выделенные ячейки",
            action: () => clearSelectedCells(),
        },
    ];

    const rowContextMenu = [
        {
            label: "Копировать строку",
            action: (_event, row) => {
                selectRowRange(row);
                table.copyToClipboard("range");
            },
        },
        {
            label: "Вставить строку",
            action: (_event, row) => {
                selectRowRange(row);
                void pasteFromClipboard(row.getCell(editableFields[0]));
            },
        },
        {separator: true},
        {
            label: "Очистить черновую строку",
            disabled: (row) => !row.getData()._draft,
            action: (_event, row) => {
                selectRowRange(row);
                clearSelectedCells();
            },
        },
    ];

    function column({title, field, width, minWidth, multiline = false, currency = false}) {
        return {
            title,
            field,
            width,
            minWidth,
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
            contextMenu: cellContextMenu,
        };
    }

    const columns = [
        {...column({title: "Дата останова", field: "start_date", width: 112, minWidth: 96}), frozen: true},
        {...column({title: "Время", field: "start_time", width: 78, minWidth: 68}), frozen: true},
        {...column({title: "№ ВЭУ / оборудование", field: "asset_label", width: 158, minWidth: 120}), frozen: true},
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
    }

    table = new window.Tabulator(root, {
        data: initialData(),
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
        selectableRangeClearCells: true,
        selectableRangeClearCellsValue: "",
        selectableRangeAutoFocus: true,
        selectableRangeBlurEditOnNavigate: true,
        clipboard: true,
        clipboardCopyStyled: false,
        clipboardCopyRowRange: "range",
        clipboardCopyConfig: {
            rowHeaders: false,
            columnHeaders: false,
        },
        clipboardPasteParser: "range",
        clipboardPasteAction: "range",
        persistence: {
            columns: true,
            sort: true,
            headerFilter: true,
        },
        persistenceID: persistenceId,
        persistenceMode: "local",
        headerFilterLiveFilterDelay: 180,
        rowHeight: 34,
        rowHeader: {
            formatter: "rownum",
            field: "rownum",
            accessorClipboard: "rownum",
            headerSort: false,
            frozen: true,
            width: 46,
            minWidth: 46,
            resizable: false,
            hozAlign: "center",
            cssClass: "journal-row-number",
            editor: false,
        },
        rowContextMenu,
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
        return fields
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
        activeCell = cell;
    });

    table.on("rangeChanged", (range) => {
        const bounds = range.getBounds?.();
        activeCell = bounds?.end || bounds?.bottomRight || activeCell;
    });

    table.on("cellEdited", (cell) => {
        activeCell = cell;
        if (normalizingCell) {
            return;
        }
        const normalized = normalizeCellValue(cell);
        if (normalized !== String(cell.getValue() ?? "")) {
            normalizingCell = true;
            cell.setValue(normalized, true);
            normalizingCell = false;
        }
        const row = cell.getRow();
        const data = row.getData();
        if (
            data._draft
            && operationalFields.includes(cell.getField())
            && isMeaningfulDraft(data)
            && (!String(data.start_date ?? "").trim() || !String(data.start_time ?? "").trim())
        ) {
            const timestamp = {};
            if (!String(data.start_date ?? "").trim()) {
                timestamp.start_date = localDateValue();
            }
            if (!String(data.start_time ?? "").trim()) {
                timestamp.start_time = localTimeValue();
            }
            void row.update(timestamp);
        }
        scheduleSave(row);
    });

    table.on("clipboardPasted", (_clipboard, _rowData, rows) => {
        (rows || []).forEach((row) => scheduleSave(row, 100));
    });

    table.on("clipboardPasteError", () => {
        setSaveState("error", "Не удалось вставить данные из буфера обмена.");
    });

    table.on("dataFiltered", updateRecordCount);

    root.addEventListener("keydown", (event) => {
        const target = event.target;
        const editing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
        if (editing) {
            return;
        }
        const modifier = event.ctrlKey || event.metaKey;
        const key = event.key.toLocaleLowerCase("ru");
        if (modifier && key === "f") {
            event.preventDefault();
            searchInput?.focus();
            searchInput?.select();
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
        if (
            !modifier
            && !event.altKey
            && event.key.length === 1
            && activeCell
            && editableFields.includes(activeCell.getField())
        ) {
            event.preventDefault();
            event.stopImmediatePropagation();
            pendingTypedSeed = {
                rowKey: activeCell.getRow().getData()._rowKey,
                field: activeCell.getField(),
                text: event.key,
            };
            activeCell.edit();
        }
    }, true);

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
        saveJson(headerFilterStorageKey, headerFiltersVisible);
        table.redraw(true);
    });

    document.querySelectorAll("[data-align-horizontal]").forEach((button) => {
        button.addEventListener("click", () => {
            applyAlignment("horizontal", button.dataset.alignHorizontal);
        });
    });

    document.querySelectorAll("[data-align-vertical]").forEach((button) => {
        button.addEventListener("click", () => {
            applyAlignment("vertical", button.dataset.alignVertical);
        });
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
                    saveJson(rulesStorageKey, formatRules);
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
        saveJson(alignmentStorageKey, alignmentStore);
        saveJson(fillStorageKey, fillStore);
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
