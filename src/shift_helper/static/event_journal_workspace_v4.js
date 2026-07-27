"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const saveState = document.getElementById("journal-save-state");
    const saveText = saveState?.querySelector(".save-state__text");
    const undoButton = document.getElementById("journal-undo");
    const redoButton = document.getElementById("journal-redo");
    const settingsDialog = document.getElementById("journal-view-settings");

    if (!root || !table || !saveState || !saveText) {
        return;
    }

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
    const multilineFields = new Set(["description", "reason", "actions"]);
    const historyLimit = 100;
    const preferenceKey = "shift-helper-ui-preferences-v1";
    const defaultPreferences = {
        theme: "dark",
        zoom: 100,
        fontSize: 13,
        fontFamily: "Segoe UI",
    };

    let activeCell = null;
    let rowAnchorKey = null;
    let internalClipboard = "";
    let historyApplying = false;
    let groupedOperation = false;
    let pendingCaret = null;
    let menu = null;
    let fillState = null;
    let preferences = loadJson(preferenceKey, defaultPreferences);

    const selectedRowKeys = new Set();
    const editBefore = new WeakMap();
    const rowLastKey = new WeakMap();
    const undoStack = [];
    const redoStack = [];

    function loadJson(key, fallback) {
        try {
            const value = window.localStorage.getItem(key);
            return value === null ? {...fallback} : {...fallback, ...JSON.parse(value)};
        } catch (_error) {
            return {...fallback};
        }
    }

    function saveJson(key, value) {
        try {
            window.localStorage.setItem(key, JSON.stringify(value));
        } catch (_error) {
            // Workstation preferences are optional and must never block the journal.
        }
    }

    function setStatus(state, message) {
        saveState.dataset.state = state;
        saveText.textContent = message;
    }

    function isTextControl(target) {
        return target instanceof Element && Boolean(
            target.closest(
                ".journal-stable-editor, #journal-search, .tabulator-header-filter, "
                + ".format-rules-dialog, .journal-settings-dialog",
            ),
        );
    }

    function isCell(candidate) {
        return Boolean(
            candidate
            && typeof candidate.getField === "function"
            && typeof candidate.getRow === "function"
            && typeof candidate.setValue === "function",
        );
    }

    function allRows() {
        return table.getRows();
    }

    function rowByKey(key) {
        if (!key) {
            return null;
        }
        return allRows().find((row) => row.getData()._rowKey === key) || null;
    }

    function rowFromElement(element) {
        const rowElement = element?.closest?.(".tabulator-row");
        return rowElement
            ? allRows().find((row) => row.getElement() === rowElement) || null
            : null;
    }

    function cellFromElement(element) {
        const cellElement = element?.closest?.(".tabulator-cell");
        if (!cellElement) {
            return null;
        }
        for (const row of table.getRows("active")) {
            const found = row.getCells().find((cell) => cell.getElement() === cellElement);
            if (found) {
                return found;
            }
        }
        return null;
    }

    function normalizeRangeMatrix() {
        const range = table.getRanges?.().at(-1);
        const raw = range?.getCells?.() || [];
        const flat = raw.length && Array.isArray(raw[0]) ? raw.flat() : raw;
        const cells = flat.filter(isCell);
        if (!cells.length) {
            return activeCell ? [[activeCell]] : [];
        }

        const rowOrder = new Map(allRows().map((row, index) => [row.getData()._rowKey, index]));
        const grouped = new Map();
        for (const cell of cells) {
            const key = cell.getRow().getData()._rowKey;
            grouped.set(key, [...(grouped.get(key) || []), cell]);
        }
        return [...grouped.entries()]
            .sort(([left], [right]) => (rowOrder.get(left) ?? 0) - (rowOrder.get(right) ?? 0))
            .map(([_key, rowCells]) => rowCells.sort(
                (left, right) => editableFields.indexOf(left.getField())
                    - editableFields.indexOf(right.getField()),
            ));
    }

    function selectedCells() {
        return [...new Set(normalizeRangeMatrix().flat())]
            .filter((cell) => editableFields.includes(cell.getField()));
    }

    function selectedRows() {
        return allRows().filter((row) => selectedRowKeys.has(row.getData()._rowKey));
    }

    function clearRowSelection() {
        selectedRowKeys.clear();
        rowAnchorKey = null;
        window.shiftHelperSelectedRowKeys = [];
        allRows().forEach((row) => {
            row.getElement()?.classList.remove("journal-row--multi-selected");
        });
    }

    function renderRowSelection() {
        window.shiftHelperSelectedRowKeys = [...selectedRowKeys];
        allRows().forEach((row) => {
            row.getElement()?.classList.toggle(
                "journal-row--multi-selected",
                selectedRowKeys.has(row.getData()._rowKey),
            );
        });
    }

    function selectRowsThrough(clickedRow, event) {
        const rows = allRows();
        const clickedKey = clickedRow.getData()._rowKey;
        if (event.shiftKey && rowAnchorKey) {
            const anchorIndex = rows.findIndex((row) => row.getData()._rowKey === rowAnchorKey);
            const clickedIndex = rows.indexOf(clickedRow);
            if (anchorIndex >= 0 && clickedIndex >= 0) {
                if (!event.ctrlKey && !event.metaKey) {
                    selectedRowKeys.clear();
                }
                const start = Math.min(anchorIndex, clickedIndex);
                const end = Math.max(anchorIndex, clickedIndex);
                rows.slice(start, end + 1).forEach((row) => {
                    selectedRowKeys.add(row.getData()._rowKey);
                });
            }
        } else if (event.ctrlKey || event.metaKey) {
            if (selectedRowKeys.has(clickedKey)) {
                selectedRowKeys.delete(clickedKey);
            } else {
                selectedRowKeys.add(clickedKey);
            }
            rowAnchorKey = clickedKey;
        } else {
            selectedRowKeys.clear();
            selectedRowKeys.add(clickedKey);
            rowAnchorKey = clickedKey;
        }
        (table.getRanges?.() || []).forEach((range) => range.remove());
        activeCell = clickedRow.getCell(editableFields[0]);
        renderRowSelection();
    }

    function updateHistoryButtons() {
        if (undoButton) {
            undoButton.disabled = undoStack.length === 0;
            undoButton.title = undoStack.length
                ? `Отменить: ${undoStack.at(-1).label}`
                : "Нечего отменять";
        }
        if (redoButton) {
            redoButton.disabled = redoStack.length === 0;
            redoButton.title = redoStack.length
                ? `Повторить: ${redoStack.at(-1).label}`
                : "Нечего повторять";
        }
    }

    function remapHistoryKey(oldKey, newKey) {
        if (!oldKey || oldKey === newKey) {
            return;
        }
        for (const command of [...undoStack, ...redoStack]) {
            for (const change of command.changes || []) {
                if (change.rowKey === oldKey) {
                    change.rowKey = newKey;
                }
            }
            for (const item of command.items || []) {
                if (item.rowKey === oldKey) {
                    item.rowKey = newKey;
                    item.data._rowKey = newKey;
                }
            }
        }
    }

    function pushHistory(command) {
        if (historyApplying || groupedOperation || !command) {
            return;
        }
        undoStack.push(command);
        if (undoStack.length > historyLimit) {
            undoStack.shift();
        }
        redoStack.length = 0;
        updateHistoryButtons();
    }

    function captureChanges(cells, nextValues) {
        return cells.map((cell, index) => ({
            rowKey: cell.getRow().getData()._rowKey,
            field: cell.getField(),
            before: String(cell.getValue() ?? ""),
            after: String(nextValues[index] ?? ""),
        })).filter((change) => change.before !== change.after);
    }

    function applyChanges(changes, side) {
        historyApplying = true;
        try {
            for (const change of changes) {
                const row = rowByKey(change.rowKey);
                const cell = row?.getCell(change.field);
                if (cell) {
                    cell.setValue(change[side], true);
                }
            }
        } finally {
            historyApplying = false;
        }
        normalizeVisibleRows();
    }

    async function undo() {
        const command = undoStack.pop();
        if (!command) {
            return;
        }
        historyApplying = true;
        try {
            if (command.type === "cells") {
                applyChanges(command.changes, "before");
            } else if (command.type === "delete-rows") {
                await restoreDeletedRows(command);
            }
            redoStack.push(command);
            setStatus("dirty", `Отменено: ${command.label}`);
        } catch (error) {
            undoStack.push(command);
            setStatus("error", error.message || "Не удалось отменить операцию.");
        } finally {
            historyApplying = false;
            updateHistoryButtons();
        }
    }

    async function redo() {
        const command = redoStack.pop();
        if (!command) {
            return;
        }
        historyApplying = true;
        try {
            if (command.type === "cells") {
                applyChanges(command.changes, "after");
            } else if (command.type === "delete-rows") {
                await deleteRowsByItems(command.items, false);
            }
            undoStack.push(command);
            setStatus("dirty", `Повторено: ${command.label}`);
        } catch (error) {
            redoStack.push(command);
            setStatus("error", error.message || "Не удалось повторить операцию.");
        } finally {
            historyApplying = false;
            updateHistoryButtons();
        }
    }

    function escapeTsv(value) {
        const text = String(value ?? "");
        return /[\t\r\n"]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    }

    function serializeMatrix(matrix) {
        return matrix
            .map((row) => row.map((cell) => escapeTsv(cell?.getValue?.() ?? "")).join("\t"))
            .join("\r\n");
    }

    function serializeRows(rows) {
        return rows.map((row) => editableFields
            .map((field) => escapeTsv(row.getData()[field] ?? ""))
            .join("\t")).join("\r\n");
    }

    function parseTsv(text) {
        const rows = [[]];
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
            if (character === '"' && value === "") {
                quoted = true;
            } else if (character === "\t") {
                rows.at(-1).push(value);
                value = "";
            } else if (character === "\n" || character === "\r") {
                if (character === "\r" && text[index + 1] === "\n") {
                    index += 1;
                }
                rows.at(-1).push(value);
                value = "";
                if (index < text.length - 1) {
                    rows.push([]);
                }
            } else {
                value += character;
            }
        }
        rows.at(-1).push(value);
        return rows.filter((row, index) => index < rows.length - 1 || row.some(Boolean));
    }

    async function writeClipboard(text) {
        internalClipboard = text;
        try {
            await navigator.clipboard.writeText(text);
        } catch (_error) {
            // The internal clipboard remains available when browser access is denied.
        }
    }

    async function readClipboard(event = null) {
        const eventText = event?.clipboardData?.getData("text/plain") || "";
        if (eventText) {
            internalClipboard = eventText;
            return eventText;
        }
        try {
            const system = await navigator.clipboard.readText();
            if (system) {
                internalClipboard = system;
                return system;
            }
        } catch (_error) {
            // Fall back to the application clipboard.
        }
        return internalClipboard;
    }

    function ensureTargetRows(startRow, count) {
        const rows = allRows();
        const startIndex = rows.indexOf(startRow);
        const missing = startIndex + count - rows.length;
        if (missing <= 0) {
            return Promise.resolve(rows);
        }
        return table.addData(Array.from({length: missing}, () => ({
            _draft: true,
            _rowKey: `draft-workspace-${Date.now()}-${Math.random()}`,
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
        })), false).then(() => allRows());
    }

    function applyCellMatrix(targetCells, sourceMatrix, label) {
        const flatTargets = targetCells.flat().filter(isCell);
        if (!flatTargets.length || !sourceMatrix.length || !sourceMatrix[0]?.length) {
            return;
        }
        const targetMatrix = targetCells;
        const nextValues = [];
        for (let rowIndex = 0; rowIndex < targetMatrix.length; rowIndex += 1) {
            for (let columnIndex = 0; columnIndex < targetMatrix[rowIndex].length; columnIndex += 1) {
                nextValues.push(sourceMatrix[rowIndex % sourceMatrix.length][
                    columnIndex % sourceMatrix[0].length
                ] ?? "");
            }
        }
        const changes = captureChanges(flatTargets, nextValues);
        if (!changes.length) {
            return;
        }
        groupedOperation = true;
        try {
            changes.forEach((change) => {
                rowByKey(change.rowKey)?.getCell(change.field)?.setValue(change.after, true);
            });
        } finally {
            groupedOperation = false;
        }
        pushHistory({type: "cells", label, changes});
        normalizeVisibleRows();
    }

    async function pasteText(text) {
        if (!text) {
            return;
        }
        const source = parseTsv(text);
        const rows = selectedRows();
        if (rows.length) {
            const changes = [];
            rows.forEach((row, rowIndex) => {
                editableFields.forEach((field, columnIndex) => {
                    const cell = row.getCell(field);
                    const next = source[rowIndex % source.length]?.[
                        columnIndex % source[0].length
                    ] ?? "";
                    changes.push(...captureChanges([cell], [next]));
                });
            });
            groupedOperation = true;
            try {
                changes.forEach((change) => {
                    rowByKey(change.rowKey)?.getCell(change.field)?.setValue(change.after, true);
                });
            } finally {
                groupedOperation = false;
            }
            pushHistory({type: "cells", label: "вставка строк", changes});
            return;
        }

        const matrix = normalizeRangeMatrix();
        if (!matrix.length) {
            return;
        }
        const targetSize = matrix.reduce((count, row) => count + row.length, 0);
        if (targetSize > 1) {
            applyCellMatrix(matrix, source, "вставка в диапазон");
            return;
        }

        const startCell = matrix[0][0];
        const startRow = startCell.getRow();
        const startColumn = editableFields.indexOf(startCell.getField());
        const rowsForPaste = await ensureTargetRows(startRow, source.length);
        const startIndex = rowsForPaste.indexOf(startRow);
        const target = source.map((_row, rowOffset) => source[rowOffset].map(
            (_value, columnOffset) => rowsForPaste[startIndex + rowOffset]
                ?.getCell(editableFields[startColumn + columnOffset]),
        ).filter(Boolean));
        applyCellMatrix(target, source, "вставка диапазона");
    }

    function clearSelectedCells() {
        const cells = selectedCells();
        if (!cells.length) {
            return;
        }
        const changes = captureChanges(cells, cells.map(() => ""));
        if (!changes.length) {
            return;
        }
        groupedOperation = true;
        try {
            changes.forEach((change) => {
                rowByKey(change.rowKey)?.getCell(change.field)?.setValue("", true);
            });
        } finally {
            groupedOperation = false;
        }
        pushHistory({type: "cells", label: "очистка диапазона", changes});
        normalizeVisibleRows();
    }

    async function deletePersistedRow(row) {
        const data = row.getData();
        if (data._draft) {
            return;
        }
        const response = await fetch(`${root.dataset.deleteBase}/${data.id}/row`, {
            method: "DELETE",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({revision: data.revision}),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || "Не удалось удалить строку.");
        }
    }

    async function deleteRowsByItems(items, recordHistory = true) {
        const removed = [];
        for (const item of items) {
            const row = rowByKey(item.rowKey);
            if (!row) {
                continue;
            }
            await deletePersistedRow(row);
            removed.push(item);
            await row.delete();
        }
        clearRowSelection();
        if (recordHistory && removed.length) {
            pushHistory({
                type: "delete-rows",
                label: removed.length > 1 ? "удаление строк" : "удаление строки",
                items: removed,
            });
        }
        setStatus("saved", removed.length > 1 ? "Строки удалены" : "Строка удалена");
    }

    async function deleteSelectedRows() {
        const rows = selectedRows();
        if (!rows.length) {
            return;
        }
        const all = allRows();
        const items = rows.map((row) => ({
            rowKey: row.getData()._rowKey,
            index: all.indexOf(row),
            data: structuredClone(row.getData()),
        }));
        await deleteRowsByItems(items, true);
    }

    async function restoreDeletedRows(command) {
        const restored = [];
        for (const item of [...command.items].sort((left, right) => left.index - right.index)) {
            let data = structuredClone(item.data);
            if (!data._draft) {
                const response = await fetch(root.dataset.createUrl, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(data),
                });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok || !payload.ok) {
                    throw new Error(payload.error || "Не удалось восстановить строку.");
                }
                data = {
                    ...payload.row,
                    _draft: false,
                    _rowKey: item.rowKey,
                    _saving: false,
                    _saveError: false,
                };
            }
            const currentRows = allRows();
            const reference = currentRows[item.index] || false;
            const row = await table.addRow(data, false, reference);
            item.data = structuredClone(row.getData());
            restored.push(row);
        }
        command.items = command.items.map((item, index) => ({
            ...item,
            rowKey: restored[index]?.getData()._rowKey || item.rowKey,
            data: structuredClone(restored[index]?.getData() || item.data),
        }));
        normalizeVisibleRows();
    }

    function copySelection(event = null) {
        const rows = selectedRows();
        const text = rows.length ? serializeRows(rows) : serializeMatrix(normalizeRangeMatrix());
        if (!text) {
            return;
        }
        if (event?.clipboardData) {
            event.clipboardData.setData("text/plain", text);
            internalClipboard = text;
        } else {
            void writeClipboard(text);
        }
        setStatus("saved", rows.length ? "Строки скопированы" : "Выделение скопировано");
    }

    async function cutSelection(event = null) {
        copySelection(event);
        if (selectedRows().length) {
            await deleteSelectedRows();
        } else {
            clearSelectedCells();
        }
    }

    function measureRowHeight(row) {
        const element = row.getElement();
        if (!element?.isConnected) {
            return;
        }
        let height = 34;
        for (const field of multilineFields) {
            const value = row.getCell(field)?.getElement()
                ?.querySelector(".journal-cell-value--multiline");
            if (value) {
                height = Math.max(height, value.scrollHeight + 2);
            }
        }
        element.style.height = `${height}px`;
        row.getCells().forEach((cell) => {
            cell.getElement().style.height = `${height}px`;
        });
    }

    function normalizeVisibleRows() {
        window.requestAnimationFrame(() => {
            table.getRows("visible").forEach(measureRowHeight);
        });
    }

    function trailingNumber(value) {
        const match = /^(.*?)(-?\d+)(\D*)$/.exec(String(value ?? ""));
        return match
            ? {prefix: match[1], number: Number(match[2]), suffix: match[3]}
            : null;
    }

    function fillSeries(values, offset) {
        const numbers = values.map((value) => Number(String(value).replace(",", ".")));
        if (numbers.every(Number.isFinite)) {
            const step = numbers.length > 1 ? numbers.at(-1) - numbers.at(-2) : 0;
            return String(numbers.at(-1) + (step * offset)).replace(".", ",");
        }
        const numbered = values.map(trailingNumber);
        if (
            numbered.every(Boolean)
            && numbered.every((value) => value.prefix === numbered[0].prefix
                && value.suffix === numbered[0].suffix)
        ) {
            const step = numbered.length > 1
                ? numbered.at(-1).number - numbered.at(-2).number
                : 1;
            return `${numbered.at(-1).prefix}${
                numbered.at(-1).number + (step * offset)
            }${numbered.at(-1).suffix}`;
        }
        return values[(values.length + offset - 1) % values.length];
    }

    function createFillHandle() {
        const handle = document.createElement("div");
        handle.className = "journal-fill-handle";
        handle.hidden = true;
        handle.title = "Протянуть автозаполнение";
        document.body.appendChild(handle);
        return handle;
    }

    const fillHandle = createFillHandle();

    function updateFillHandle() {
        const matrix = normalizeRangeMatrix();
        const last = matrix.at(-1)?.at(-1);
        if (!isCell(last) || selectedRows().length) {
            fillHandle.hidden = true;
            return;
        }
        const rect = last.getElement().getBoundingClientRect();
        fillHandle.style.left = `${rect.right - 5}px`;
        fillHandle.style.top = `${rect.bottom - 5}px`;
        fillHandle.hidden = false;
    }

    fillHandle.addEventListener("pointerdown", (event) => {
        const matrix = normalizeRangeMatrix();
        if (!matrix.length) {
            return;
        }
        event.preventDefault();
        fillState = {matrix, target: matrix.at(-1).at(-1)};
        fillHandle.setPointerCapture(event.pointerId);
    });

    fillHandle.addEventListener("pointermove", (event) => {
        if (!fillState) {
            return;
        }
        const target = cellFromElement(document.elementFromPoint(event.clientX, event.clientY));
        if (target && editableFields.includes(target.getField())) {
            fillState.target = target;
        }
    });

    fillHandle.addEventListener("pointerup", (event) => {
        if (!fillState) {
            return;
        }
        fillHandle.releasePointerCapture(event.pointerId);
        const source = fillState.matrix;
        const first = source[0][0];
        const target = fillState.target;
        fillState = null;
        const rows = allRows();
        const sourceTop = rows.indexOf(first.getRow());
        const sourceBottom = rows.indexOf(source.at(-1).at(-1).getRow());
        const targetRow = rows.indexOf(target.getRow());
        const sourceLeft = editableFields.indexOf(first.getField());
        const sourceRight = editableFields.indexOf(source[0].at(-1).getField());
        const targetColumn = editableFields.indexOf(target.getField());
        if (targetRow < sourceBottom || targetColumn < sourceRight) {
            setStatus("error", "Автозаполнение выполняется вниз или вправо.");
            return;
        }
        const cells = [];
        const values = [];
        for (let rowIndex = sourceTop; rowIndex <= targetRow; rowIndex += 1) {
            for (let columnIndex = sourceLeft; columnIndex <= targetColumn; columnIndex += 1) {
                if (rowIndex <= sourceBottom && columnIndex <= sourceRight) {
                    continue;
                }
                const cell = rows[rowIndex]?.getCell(editableFields[columnIndex]);
                if (!cell) {
                    continue;
                }
                cells.push(cell);
                if (sourceLeft === sourceRight) {
                    const sequence = source.map((row) => String(row[0].getValue() ?? ""));
                    values.push(fillSeries(sequence, rowIndex - sourceBottom));
                } else if (sourceTop === sourceBottom) {
                    const sequence = source[0].map((item) => String(item.getValue() ?? ""));
                    values.push(fillSeries(sequence, columnIndex - sourceRight));
                } else {
                    values.push(source[(rowIndex - sourceTop) % source.length][
                        (columnIndex - sourceLeft) % source[0].length
                    ].getValue());
                }
            }
        }
        const changes = captureChanges(cells, values);
        groupedOperation = true;
        try {
            changes.forEach((change) => {
                rowByKey(change.rowKey)?.getCell(change.field)?.setValue(change.after, true);
            });
        } finally {
            groupedOperation = false;
        }
        pushHistory({type: "cells", label: "автозаполнение", changes});
        normalizeVisibleRows();
        updateFillHandle();
    });

    function closeMenu() {
        menu?.remove();
        menu = null;
    }

    function menuButton(label, action, danger = false) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        button.className = danger ? "journal-workspace-menu__danger" : "";
        button.addEventListener("click", () => {
            closeMenu();
            void action();
        });
        return button;
    }

    function showRowMenu(event) {
        closeMenu();
        menu = document.createElement("div");
        menu.className = "journal-workspace-menu";
        menu.style.left = `${event.clientX}px`;
        menu.style.top = `${event.clientY}px`;
        menu.append(
            menuButton("Копировать строку", () => copySelection()),
            menuButton("Вырезать строку", () => cutSelection()),
            menuButton("Вставить строку", async () => pasteText(await readClipboard())),
            menuButton(
                selectedRows().length > 1 ? "Удалить строки" : "Удалить строку",
                () => deleteSelectedRows(),
                true,
            ),
        );
        document.body.appendChild(menu);
    }

    function effectiveTheme(value = preferences.theme) {
        if (value !== "system") {
            return value;
        }
        return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    }

    function applyPreferences() {
        preferences.zoom = Math.min(140, Math.max(75, Number(preferences.zoom) || 100));
        preferences.fontSize = Math.min(18, Math.max(10, Number(preferences.fontSize) || 13));
        document.documentElement.dataset.theme = effectiveTheme();
        document.documentElement.style.setProperty(
            "--ui-font-family",
            `"${preferences.fontFamily}", "Segoe UI", system-ui, sans-serif`,
        );
        document.documentElement.style.setProperty("--journal-font-size", `${preferences.fontSize}px`);
        const zoom = preferences.zoom / 100;
        document.body.style.zoom = String(zoom);
        document.body.style.width = `${100 / zoom}%`;
        document.documentElement.style.setProperty(
            "--ui-viewport-height",
            `${window.innerHeight / zoom}px`,
        );
        saveJson(preferenceKey, preferences);
        table.redraw(true);
        normalizeVisibleRows();
    }

    function bindSettings() {
        document.getElementById("open-view-settings")?.addEventListener("click", () => {
            document.getElementById("journal-theme").value = preferences.theme;
            document.getElementById("journal-zoom").value = String(preferences.zoom);
            document.getElementById("journal-zoom-value").textContent = `${preferences.zoom}%`;
            document.getElementById("journal-font-size").value = String(preferences.fontSize);
            document.getElementById("journal-font-size-value").textContent = `${preferences.fontSize}px`;
            document.getElementById("journal-font-family").value = preferences.fontFamily;
            settingsDialog?.showModal();
        });
        document.getElementById("journal-theme")?.addEventListener("change", (event) => {
            preferences.theme = event.target.value;
            applyPreferences();
        });
        document.getElementById("journal-zoom")?.addEventListener("input", (event) => {
            preferences.zoom = Number(event.target.value);
            document.getElementById("journal-zoom-value").textContent = `${preferences.zoom}%`;
            applyPreferences();
        });
        document.getElementById("journal-font-size")?.addEventListener("input", (event) => {
            preferences.fontSize = Number(event.target.value);
            document.getElementById("journal-font-size-value").textContent = `${preferences.fontSize}px`;
            applyPreferences();
        });
        document.getElementById("journal-font-family")?.addEventListener("change", (event) => {
            preferences.fontFamily = event.target.value;
            applyPreferences();
        });
        document.getElementById("reset-view-settings")?.addEventListener("click", () => {
            preferences = {...defaultPreferences};
            applyPreferences();
            settingsDialog?.close();
        });
    }

    function caretOffsetFromPoint(event) {
        const position = document.caretPositionFromPoint?.(event.clientX, event.clientY);
        if (position?.offsetNode?.parentElement?.closest(".journal-cell-value")) {
            return position.offset;
        }
        const range = document.caretRangeFromPoint?.(event.clientX, event.clientY);
        return range?.startContainer?.parentElement?.closest(".journal-cell-value")
            ? range.startOffset
            : null;
    }

    const editorObserver = new MutationObserver(() => {
        if (!pendingCaret) {
            return;
        }
        const editor = root.querySelector(".journal-stable-editor");
        if (!(editor instanceof HTMLInputElement || editor instanceof HTMLTextAreaElement)) {
            return;
        }
        const cell = cellFromElement(editor);
        if (!cell) {
            return;
        }
        const data = cell.getRow().getData();
        if (data._rowKey !== pendingCaret.rowKey || cell.getField() !== pendingCaret.field) {
            return;
        }
        const offset = Math.min(editor.value.length, Math.max(0, pendingCaret.offset));
        editor.setSelectionRange(offset, offset);
        pendingCaret = null;
    });
    editorObserver.observe(root, {childList: true, subtree: true});

    table.on("cellClick", (_event, cell) => {
        activeCell = cell;
        clearRowSelection();
        updateFillHandle();
    });
    table.on("rangeChanged", (range) => {
        const flat = range?.getCells?.() || [];
        const cells = flat.length && Array.isArray(flat[0]) ? flat.flat() : flat;
        activeCell = [...cells].reverse().find(isCell) || activeCell;
        clearRowSelection();
        updateFillHandle();
    });
    table.on("cellEditing", (cell) => {
        editBefore.set(cell, String(cell.getValue() ?? ""));
    });
    table.on("cellEdited", (cell) => {
        if (!historyApplying && !groupedOperation) {
            const before = editBefore.get(cell);
            const after = String(cell.getValue() ?? "");
            if (before !== undefined && before !== after) {
                pushHistory({
                    type: "cells",
                    label: "редактирование ячейки",
                    changes: [{
                        rowKey: cell.getRow().getData()._rowKey,
                        field: cell.getField(),
                        before,
                        after,
                    }],
                });
            }
        }
        normalizeVisibleRows();
    });
    table.on("rowUpdated", (row) => {
        const newKey = row.getData()._rowKey;
        const oldKey = rowLastKey.get(row);
        if (oldKey && oldKey !== newKey) {
            remapHistoryKey(oldKey, newKey);
        }
        rowLastKey.set(row, newKey);
        renderRowSelection();
        normalizeVisibleRows();
    });
    table.on("renderComplete", () => {
        allRows().forEach((row) => rowLastKey.set(row, row.getData()._rowKey));
        renderRowSelection();
        normalizeVisibleRows();
        updateFillHandle();
    });
    table.on("columnResized", normalizeVisibleRows);

    document.addEventListener("pointerdown", (event) => {
        if (!(event.target instanceof Element) || !root.contains(event.target)) {
            return;
        }
        const rowNumber = event.target.closest(".journal-row-number");
        if (rowNumber) {
            const row = rowFromElement(rowNumber);
            if (row) {
                event.preventDefault();
                event.stopImmediatePropagation();
                selectRowsThrough(row, event);
            }
        } else if (event.target.closest(".tabulator-cell")) {
            clearRowSelection();
        }
    }, true);

    document.addEventListener("click", (event) => {
        if (event.target instanceof Element && event.target.closest(".journal-row-number")) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);

    document.addEventListener("dblclick", (event) => {
        if (!(event.target instanceof Element) || !root.contains(event.target)) {
            return;
        }
        const cell = cellFromElement(event.target);
        if (!cell || !editableFields.includes(cell.getField())) {
            return;
        }
        pendingCaret = {
            rowKey: cell.getRow().getData()._rowKey,
            field: cell.getField(),
            offset: caretOffsetFromPoint(event) ?? String(cell.getValue() ?? "").length,
        };
    }, true);

    document.addEventListener("contextmenu", (event) => {
        if (!(event.target instanceof Element) || !root.contains(event.target)) {
            return;
        }
        const rowNumber = event.target.closest(".journal-row-number");
        if (!rowNumber) {
            return;
        }
        const row = rowFromElement(rowNumber);
        if (!row) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        if (!selectedRowKeys.has(row.getData()._rowKey)) {
            selectedRowKeys.clear();
            selectedRowKeys.add(row.getData()._rowKey);
            rowAnchorKey = row.getData()._rowKey;
            renderRowSelection();
        }
        showRowMenu(event);
    }, true);

    document.addEventListener("pointerdown", (event) => {
        if (menu && event.target instanceof Element && !menu.contains(event.target)) {
            closeMenu();
        }
    });

    document.addEventListener("copy", (event) => {
        if (isTextControl(event.target) || !event.clipboardData) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        copySelection(event);
    }, true);

    document.addEventListener("cut", (event) => {
        if (isTextControl(event.target) || !event.clipboardData) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        void cutSelection(event);
    }, true);

    document.addEventListener("paste", (event) => {
        if (isTextControl(event.target) || !event.clipboardData) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        void pasteText(event.clipboardData.getData("text/plain"));
    }, true);

    document.addEventListener("keydown", (event) => {
        if (isTextControl(event.target)) {
            return;
        }
        const modifier = event.ctrlKey || event.metaKey;
        const key = event.key.toLowerCase();
        if (modifier && key === "z" && !event.shiftKey) {
            event.preventDefault();
            event.stopImmediatePropagation();
            void undo();
            return;
        }
        if ((modifier && key === "y") || (modifier && event.shiftKey && key === "z")) {
            event.preventDefault();
            event.stopImmediatePropagation();
            void redo();
            return;
        }
        if (event.key === "Delete" || event.key === "Backspace") {
            event.preventDefault();
            event.stopImmediatePropagation();
            if (selectedRows().length) {
                void deleteSelectedRows();
            } else {
                clearSelectedCells();
            }
        }
    }, true);

    undoButton?.addEventListener("click", () => void undo());
    redoButton?.addEventListener("click", () => void redo());
    window.addEventListener("resize", () => {
        applyPreferences();
        updateFillHandle();
    });
    window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
        if (preferences.theme === "system") {
            applyPreferences();
        }
    });

    bindSettings();
    applyPreferences();
    updateHistoryButtons();
    normalizeVisibleRows();
})();
