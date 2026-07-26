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
        "losses_mwh",
    ];
    const editableFields = fieldOrder.filter((field) => field !== "downtime");
    const searchableFields = [...fieldOrder];
    const requiredFields = ["start_date", "start_time", "asset_label", "description"];
    const draftBatchSize = 80;
    const alignmentStorageKey = "shift-helper-event-cell-alignment-v1";
    const headerFilterStorageKey = "shift-helper-event-header-filter-visible-v1";
    const persistenceId = "shift-helper-event-grid-v1";
    const saveTimers = new Map();
    const saveQueues = new Map();
    const alignmentStore = loadJson(alignmentStorageKey, {});
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
        losses_mwh: {horizontal: "right", vertical: "middle"},
    };

    let draftSequence = 0;
    let currentStatus = root.dataset.selectedStatus || "all";
    let currentSearch = "";
    let activeCell = null;
    let table = null;
    let defaultColumnLayout = null;
    let normalizingCell = false;
    let addingDraftRows = false;
    let headerFiltersVisible = loadJson(headerFilterStorageKey, true) !== false;

    const initialData = initialRows.map((row) => ({
        ...row,
        _draft: false,
        _rowKey: `event-${row.id}`,
        _saveError: false,
        _saving: false,
    }));
    initialData.push(...makeDraftRows(draftBatchSize, true));

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
            // The grid remains usable even when localStorage is unavailable.
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

    function makeDraftRow(seedDateTime = false) {
        draftSequence += 1;
        return {
            _draft: true,
            _rowKey: `draft-${Date.now()}-${draftSequence}`,
            _saveError: false,
            _saving: false,
            revision: 0,
            status: "draft",
            start_date: seedDateTime ? localDateValue() : "",
            start_time: seedDateTime ? localTimeValue() : "",
            asset_label: "",
            description: "",
            reason: "",
            actions: "",
            performer: "",
            end_date: "",
            end_time: "",
            downtime: "",
            author: "",
            losses_mwh: "",
        };
    }

    function makeDraftRows(count, seedFirst = false) {
        return Array.from({length: count}, (_unused, index) => makeDraftRow(seedFirst && index === 0));
    }

    function isMeaningfulDraft(data) {
        return editableFields.some((field) => String(data[field] ?? "").trim() !== "");
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
        const allRows = table.getData().filter((row) => !row._draft).length;
        const visibleRows = table.getRows("active").filter((row) => !row.getData()._draft).length;
        recordCount.textContent = visibleRows === allRows
            ? `Записей: ${allRows}`
            : `Записей: ${allRows} · показано: ${visibleRows}`;
    }

    function previousRowValue(row, field) {
        if (!table) {
            return "";
        }
        const rows = table.getRows("active");
        const index = rows.indexOf(row);
        if (index <= 0) {
            return "";
        }
        return rows[index - 1].getData()[field] ?? "";
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
        if (field === "start_date" || field === "end_date") {
            return normalizeDate(value, row);
        }
        if (field === "start_time" || field === "end_time") {
            return normalizeTime(value, row, field);
        }
        if (field === "losses_mwh") {
            return value.trim().replace(".", ",");
        }
        return value;
    }

    function payloadForRow(data) {
        const payload = {revision: Number(data.revision || 0)};
        for (const field of editableFields) {
            payload[field] = data[field] ?? "";
        }
        if (!String(payload.start_date).trim()) {
            payload.start_date = localDateValue();
        }
        if (!String(payload.start_time).trim()) {
            payload.start_time = localTimeValue();
        }
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

    function addSuggestion(field, value) {
        const cleaned = String(value ?? "").trim();
        const values = suggestionValues[field];
        if (!cleaned || !Array.isArray(values) || values.includes(cleaned)) {
            return;
        }
        values.push(cleaned);
        values.sort((left, right) => left.localeCompare(right, "ru"));
    }

    function migrateAlignment(oldKey, newKey) {
        if (oldKey === newKey || !alignmentStore[oldKey]) {
            return;
        }
        alignmentStore[newKey] = {
            ...(alignmentStore[newKey] || {}),
            ...alignmentStore[oldKey],
        };
        delete alignmentStore[oldKey];
        saveJson(alignmentStorageKey, alignmentStore);
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
            const eventId = data.id;
            const response = await fetch(
                isDraft ? root.dataset.createUrl : `${root.dataset.updateBase}/${eventId}/row`,
                {
                    method: isDraft ? "POST" : "PATCH",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(payloadForRow(row.getData())),
                },
            );
            const payload = await readResponse(response);
            const oldKey = data._rowKey;
            const newKey = `event-${payload.row.id}`;
            migrateAlignment(oldKey, newKey);
            await row.update({
                ...payload.row,
                _draft: false,
                _rowKey: newKey,
                _saving: false,
                _saveError: false,
            });
            for (const field of ["asset_label", "performer", "author", "reason", "actions"]) {
                addSuggestion(field, payload.row[field]);
            }
            row.reformat();
            ensureDraftRows();
            seedFirstDraft();
            applyCombinedFilter();
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
        if (!table) {
            return;
        }
        const draftCount = table.getData().filter((row) => row._draft).length;
        if (draftCount >= draftBatchSize) {
            return;
        }
        void table.addData(makeDraftRows(draftBatchSize - draftCount), false);
    }

    function seedFirstDraft() {
        if (!table) {
            return;
        }
        const firstBlank = table.getRows().find((row) => {
            const data = row.getData();
            return data._draft && !isMeaningfulDraft(data);
        });
        if (!firstBlank) {
            return;
        }
        const data = firstBlank.getData();
        if (!data.start_date && !data.start_time) {
            void firstBlank.update({start_date: localDateValue(), start_time: localTimeValue()});
        }
    }

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
        const haystack = searchableFields
            .map((field) => String(data[field] ?? ""))
            .join("\n")
            .toLocaleLowerCase("ru");
        return haystack.includes(currentSearch);
    }

    function applyCombinedFilter() {
        if (!table) {
            return;
        }
        table.setFilter(combinedFilter);
        updateRecordCount();
    }

    function alignmentFor(data, field) {
        return {
            ...defaultAlignment[field],
            ...(alignmentStore[data._rowKey]?.[field] || {}),
        };
    }

    function applyAlignmentToRenderedCell(cell, element) {
        const field = cell.getField();
        const valueElement = element.querySelector(".journal-cell-value");
        if (!valueElement || !field) {
            return;
        }
        const alignment = alignmentFor(cell.getRow().getData(), field);
        valueElement.dataset.horizontal = alignment.horizontal;
        valueElement.dataset.vertical = alignment.vertical;
    }

    function journalFormatter(cell, formatterParams, onRendered) {
        const value = cell.getValue();
        const element = document.createElement("div");
        element.className = "journal-cell-value";
        if (formatterParams?.multiline) {
            element.classList.add("journal-cell-value--multiline");
        }
        element.textContent = value === null || value === undefined ? "" : String(value);
        onRendered(() => applyAlignmentToRenderedCell(cell, cell.getElement()));
        return element;
    }

    function autocompleteParams(field) {
        return {
            values: () => suggestionValues[field] || [],
            autocomplete: true,
            listOnEmpty: true,
            freetext: true,
            allowEmpty: true,
            filterDelay: 80,
            placeholderEmpty: "Нет сохранённых вариантов",
        };
    }

    function rowFormatter(row) {
        const element = row.getElement();
        const data = row.getData();
        element.classList.toggle("journal-row--draft", Boolean(data._draft));
        element.classList.toggle("journal-row--closed", data.status === "closed");
        element.classList.toggle("journal-row--saving", Boolean(data._saving));
        element.classList.toggle("journal-row--error", Boolean(data._saveError));
    }

    function rangeCellMatrix(range) {
        const cells = range?.getCells?.() || [];
        if (!Array.isArray(cells)) {
            return [];
        }
        if (cells.length && !Array.isArray(cells[0])) {
            return [cells];
        }
        return cells;
    }

    function selectedCells() {
        if (!table) {
            return activeCell ? [activeCell] : [];
        }
        const cells = [];
        for (const range of table.getRanges?.() || []) {
            for (const row of rangeCellMatrix(range)) {
                cells.push(...row);
            }
        }
        if (!cells.length && activeCell) {
            cells.push(activeCell);
        }
        return [...new Set(cells)].filter((cell) => editableFields.includes(cell.getField()));
    }

    function applyAlignment(axis, value) {
        const cells = selectedCells();
        if (!cells.length) {
            setSaveState("error", "Сначала выделите ячейку или диапазон.");
            return;
        }
        const rows = new Set();
        for (const cell of cells) {
            const data = cell.getRow().getData();
            alignmentStore[data._rowKey] ||= {};
            alignmentStore[data._rowKey][cell.getField()] ||= {};
            alignmentStore[data._rowKey][cell.getField()][axis] = value;
            rows.add(cell.getRow());
        }
        saveJson(alignmentStorageKey, alignmentStore);
        rows.forEach((row) => row.reformat());
        setSaveState("saved", "Выравнивание сохранено");
    }

    function copyValueFromAbove(cell) {
        const value = previousRowValue(cell.getRow(), cell.getField());
        normalizingCell = true;
        cell.setValue(value, true);
        normalizingCell = false;
        scheduleSave(cell.getRow(), 40);
    }

    function clearSelectedCells() {
        const cells = selectedCells();
        const rows = new Set();
        normalizingCell = true;
        cells.forEach((cell) => {
            cell.setValue("", true);
            rows.add(cell.getRow());
        });
        normalizingCell = false;
        rows.forEach((row) => scheduleSave(row, 40));
    }

    function fillRange(direction) {
        if (!table) {
            return;
        }
        const range = table.getRanges?.()[0];
        const matrix = rangeCellMatrix(range);
        if (!matrix.length || !matrix[0]?.length) {
            return;
        }
        const rowsToSave = new Set();
        normalizingCell = true;
        if (direction === "down") {
            const source = matrix[0].map((cell) => cell.getValue());
            matrix.forEach((row, rowIndex) => {
                if (rowIndex === 0) {
                    return;
                }
                row.forEach((cell, columnIndex) => {
                    if (editableFields.includes(cell.getField())) {
                        cell.setValue(source[columnIndex] ?? "", true);
                        rowsToSave.add(cell.getRow());
                    }
                });
            });
        } else {
            matrix.forEach((row) => {
                const source = row[0]?.getValue() ?? "";
                row.forEach((cell, columnIndex) => {
                    if (columnIndex > 0 && editableFields.includes(cell.getField())) {
                        cell.setValue(source, true);
                        rowsToSave.add(cell.getRow());
                    }
                });
            });
        }
        normalizingCell = false;
        rowsToSave.forEach((row) => scheduleSave(row, 80));
    }

    const cellMenu = [
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
            label: "По верхнему краю",
            action: (_event, cell) => {
                activeCell = cell;
                applyAlignment("vertical", "top");
            },
        },
        {
            label: "По середине",
            action: (_event, cell) => {
                activeCell = cell;
                applyAlignment("vertical", "middle");
            },
        },
        {
            label: "По нижнему краю",
            action: (_event, cell) => {
                activeCell = cell;
                applyAlignment("vertical", "bottom");
            },
        },
        {separator: true},
        {
            label: "Значение из строки выше",
            action: (_event, cell) => copyValueFromAbove(cell),
        },
        {
            label: "Очистить выделенные ячейки",
            action: (_event, cell) => {
                activeCell = cell;
                clearSelectedCells();
            },
        },
    ];

    const columns = [
        {
            title: "Дата останова",
            field: "start_date",
            width: 112,
            minWidth: 96,
            frozen: true,
            editor: "input",
            headerFilter: "input",
            headerFilterPlaceholder: "Дата",
            formatter: journalFormatter,
            cellContextMenu: cellMenu,
        },
        {
            title: "Время",
            field: "start_time",
            width: 78,
            minWidth: 68,
            frozen: true,
            editor: "input",
            headerFilter: "input",
            headerFilterPlaceholder: "Время",
            formatter: journalFormatter,
            cellContextMenu: cellMenu,
        },
        {
            title: "№ ВЭУ / оборудование",
            field: "asset_label",
            width: 158,
            minWidth: 120,
            frozen: true,
            editor: "list",
            editorParams: () => autocompleteParams("asset_label"),
            headerFilter: "input",
            headerFilterPlaceholder: "Оборудование",
            formatter: journalFormatter,
            cellContextMenu: cellMenu,
        },
        {
            title: "Описание события",
            field: "description",
            width: 330,
            minWidth: 180,
            editor: "textarea",
            headerFilter: "input",
            headerFilterPlaceholder: "Текст",
            formatter: journalFormatter,
            formatterParams: {multiline: true},
            variableHeight: true,
            cellContextMenu: cellMenu,
        },
        {
            title: "Причина",
            field: "reason",
            width: 270,
            minWidth: 160,
            editor: "textarea",
            headerFilter: "input",
            headerFilterPlaceholder: "Причина",
            formatter: journalFormatter,
            formatterParams: {multiline: true},
            variableHeight: true,
            cellContextMenu: cellMenu,
        },
        {
            title: "Действия персонала",
            field: "actions",
            width: 300,
            minWidth: 180,
            editor: "textarea",
            headerFilter: "input",
            headerFilterPlaceholder: "Действия",
            formatter: journalFormatter,
            formatterParams: {multiline: true},
            variableHeight: true,
            cellContextMenu: cellMenu,
        },
        {
            title: "Исполнитель",
            field: "performer",
            width: 170,
            minWidth: 120,
            editor: "list",
            editorParams: () => autocompleteParams("performer"),
            headerFilter: "input",
            headerFilterPlaceholder: "Исполнитель",
            formatter: journalFormatter,
            cellContextMenu: cellMenu,
        },
        {
            title: "Дата пуска",
            field: "end_date",
            width: 112,
            minWidth: 96,
            editor: "input",
            headerFilter: "input",
            headerFilterPlaceholder: "Дата",
            formatter: journalFormatter,
            cellContextMenu: cellMenu,
        },
        {
            title: "Время",
            field: "end_time",
            width: 78,
            minWidth: 68,
            editor: "input",
            headerFilter: "input",
            headerFilterPlaceholder: "Время",
            formatter: journalFormatter,
            cellContextMenu: cellMenu,
        },
        {
            title: "Простой",
            field: "downtime",
            width: 118,
            minWidth: 90,
            editor: false,
            headerFilter: "input",
            headerFilterPlaceholder: "Простой",
            formatter: journalFormatter,
            cellContextMenu: cellMenu,
        },
        {
            title: "Кто внёс запись",
            field: "author",
            width: 170,
            minWidth: 120,
            editor: "list",
            editorParams: () => autocompleteParams("author"),
            headerFilter: "input",
            headerFilterPlaceholder: "Автор",
            formatter: journalFormatter,
            cellContextMenu: cellMenu,
        },
        {
            title: "Потери",
            field: "losses_mwh",
            width: 105,
            minWidth: 80,
            editor: "input",
            headerFilter: "input",
            headerFilterPlaceholder: "Потери",
            formatter: journalFormatter,
            cellContextMenu: cellMenu,
        },
    ];

    table = new window.Tabulator(root, {
        data: initialData,
        index: "_rowKey",
        height: "100%",
        layout: "fitDataFill",
        renderHorizontal: "virtual",
        movableColumns: true,
        resizableRows: true,
        resizableColumnFit: true,
        history: true,
        editTriggerEvent: "dblclick",
        selectableRows: false,
        selectableRange: 1,
        selectableRangeColumns: true,
        selectableRangeRows: true,
        selectableRangeClearCells: true,
        selectableRangeAutoFocus: true,
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
            headerSort: false,
            frozen: true,
            width: 46,
            minWidth: 46,
            resizable: false,
            hozAlign: "center",
            cssClass: "journal-row-number",
        },
        columnDefaults: {
            resizable: true,
            headerSort: true,
            vertAlign: "middle",
        },
        rowFormatter,
        columns,
    });

    table.on("tableBuilt", () => {
        defaultColumnLayout = columns.map((column) => ({
            title: column.title,
            field: column.field,
            width: column.width,
            visible: true,
            frozen: Boolean(column.frozen),
        }));
        root.classList.toggle("header-filters-hidden", !headerFiltersVisible);
        if (filterToggle) {
            filterToggle.setAttribute("aria-pressed", String(headerFiltersVisible));
        }
        applyCombinedFilter();
        updateStatusButtons();
        seedFirstDraft();
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

    table.on("cellEditing", (cell) => {
        activeCell = cell;
        const data = cell.getRow().getData();
        if (data._draft && !data.start_date && !data.start_time) {
            void cell.getRow().update({
                start_date: localDateValue(),
                start_time: localTimeValue(),
            });
        }
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
        scheduleSave(cell.getRow());
    });

    table.on("clipboardPasted", (_clipboard, _rowData, rows) => {
        for (const row of rows || []) {
            scheduleSave(row, 100);
        }
    });

    table.on("dataFiltered", updateRecordCount);

    function updateStatusButtons() {
        document.querySelectorAll("[data-status-filter]").forEach((button) => {
            button.setAttribute("aria-pressed", String(button.dataset.statusFilter === currentStatus));
        });
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
        saveJson(headerFilterStorageKey, headerFiltersVisible);
        table.redraw(true);
    });

    document.querySelectorAll("[data-align-horizontal]").forEach((button) => {
        button.addEventListener("click", () => applyAlignment("horizontal", button.dataset.alignHorizontal));
    });

    document.querySelectorAll("[data-align-vertical]").forEach((button) => {
        button.addEventListener("click", () => applyAlignment("vertical", button.dataset.alignVertical));
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
        for (const key of Object.keys(alignmentStore)) {
            delete alignmentStore[key];
        }
        saveJson(alignmentStorageKey, alignmentStore);
        updateStatusButtons();
        applyCombinedFilter();
        table.getRows().forEach((row) => row.reformat());
        setSaveState("saved", "Стандартный вид восстановлен");
    });

    document.addEventListener("keydown", (event) => {
        const target = event.target;
        const editing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
        if (event.ctrlKey && event.key.toLocaleLowerCase("ru") === "f" && !editing) {
            event.preventDefault();
            searchInput?.focus();
            searchInput?.select();
            return;
        }
        if (!event.ctrlKey || editing) {
            return;
        }
        const key = event.key.toLocaleLowerCase("ru");
        if (key === "d") {
            event.preventDefault();
            fillRange("down");
        } else if (key === "r") {
            event.preventDefault();
            fillRange("right");
        }
    });

    window.addEventListener("beforeunload", (event) => {
        if (saveTimers.size || saveQueues.size) {
            event.preventDefault();
            event.returnValue = "";
        }
    });
})();
