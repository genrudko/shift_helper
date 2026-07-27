"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const undoButton = document.getElementById("journal-undo");
    const redoButton = document.getElementById("journal-redo");
    const saveState = document.getElementById("journal-save-state");
    const saveText = saveState?.querySelector(".save-state__text");

    if (!root || !table || !undoButton || !redoButton || !saveState || !saveText) {
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
    const selectedRowKeys = new Set();
    const valueCache = new Map();
    const suppressedValues = new Map();
    const undoStack = [];
    const redoStack = [];
    const pendingChanges = new Map();
    const knownRowKeys = new WeakMap();
    let rowAnchorKey = null;
    let flushTimer = null;
    let applying = false;
    let rowClipboard = "";
    let menu = null;

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

    function rows() {
        return table.getRows();
    }

    function rowByKey(key) {
        return rows().find((row) => row.getData()._rowKey === key) || null;
    }

    function rowFromElement(element) {
        const rowElement = element?.closest?.(".tabulator-row");
        return rowElement
            ? rows().find((row) => row.getElement() === rowElement) || null
            : null;
    }

    function cacheKey(rowKey, field) {
        return `${rowKey}\u0000${field}`;
    }

    function rememberRow(row) {
        const data = row.getData();
        knownRowKeys.set(row, data._rowKey);
        for (const field of editableFields) {
            valueCache.set(cacheKey(data._rowKey, field), String(data[field] ?? ""));
        }
    }

    function rebuildValueCache() {
        valueCache.clear();
        rows().forEach(rememberRow);
    }

    function updateButtons() {
        undoButton.disabled = undoStack.length === 0;
        redoButton.disabled = redoStack.length === 0;
        undoButton.title = undoStack.length
            ? `Отменить: ${undoStack.at(-1).label}`
            : "Нечего отменять";
        redoButton.title = redoStack.length
            ? `Повторить: ${redoStack.at(-1).label}`
            : "Нечего повторять";
    }

    function pushCommand(command) {
        if (!command) {
            return;
        }
        undoStack.push(command);
        if (undoStack.length > 100) {
            undoStack.shift();
        }
        redoStack.length = 0;
        updateButtons();
    }

    function flushCellChanges() {
        window.clearTimeout(flushTimer);
        flushTimer = null;
        if (!pendingChanges.size) {
            return;
        }
        const changes = [...pendingChanges.values()]
            .filter((change) => change.before !== change.after);
        pendingChanges.clear();
        if (changes.length) {
            pushCommand({
                type: "cells",
                label: changes.length > 1 ? "изменение диапазона" : "редактирование ячейки",
                changes,
            });
        }
    }

    function queueCellChange(cell) {
        const data = cell.getRow().getData();
        const key = cacheKey(data._rowKey, cell.getField());
        const after = String(cell.getValue() ?? "");
        if (applying || suppressedValues.get(key) === after) {
            suppressedValues.delete(key);
            valueCache.set(key, after);
            return;
        }
        const oldValue = typeof cell.getOldValue === "function"
            ? String(cell.getOldValue() ?? "")
            : "";
        const before = valueCache.has(key) ? valueCache.get(key) : oldValue;
        valueCache.set(key, after);
        const existing = pendingChanges.get(key);
        pendingChanges.set(key, {
            rowKey: data._rowKey,
            field: cell.getField(),
            before: existing?.before ?? before,
            after,
        });
        window.clearTimeout(flushTimer);
        flushTimer = window.setTimeout(flushCellChanges, 90);
    }

    function remapKey(oldKey, newKey) {
        if (!oldKey || oldKey === newKey) {
            return;
        }
        for (const stack of [undoStack, redoStack]) {
            for (const command of stack) {
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
        for (const change of pendingChanges.values()) {
            if (change.rowKey === oldKey) {
                change.rowKey = newKey;
            }
        }
        for (const field of editableFields) {
            const oldCacheKey = cacheKey(oldKey, field);
            if (valueCache.has(oldCacheKey)) {
                valueCache.set(cacheKey(newKey, field), valueCache.get(oldCacheKey));
                valueCache.delete(oldCacheKey);
            }
            if (suppressedValues.has(oldCacheKey)) {
                suppressedValues.set(cacheKey(newKey, field), suppressedValues.get(oldCacheKey));
                suppressedValues.delete(oldCacheKey);
            }
        }
        if (selectedRowKeys.delete(oldKey)) {
            selectedRowKeys.add(newKey);
        }
        if (rowAnchorKey === oldKey) {
            rowAnchorKey = newKey;
        }
    }

    function applyCellChanges(changes, side) {
        applying = true;
        try {
            for (const change of changes) {
                const row = rowByKey(change.rowKey);
                const cell = row?.getCell(change.field);
                if (!cell) {
                    continue;
                }
                const value = String(change[side] ?? "");
                const key = cacheKey(change.rowKey, change.field);
                suppressedValues.set(key, value);
                valueCache.set(key, value);
                cell.setValue(value, true);
            }
        } finally {
            applying = false;
        }
    }

    function escapeTsv(value) {
        const text = String(value ?? "");
        return /[\t\r\n"]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    }

    function parseTsv(text) {
        const result = [[]];
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
            } else if (character === '"' && value === "") {
                quoted = true;
            } else if (character === "\t") {
                result.at(-1).push(value);
                value = "";
            } else if (character === "\n" || character === "\r") {
                if (character === "\r" && text[index + 1] === "\n") {
                    index += 1;
                }
                result.at(-1).push(value);
                value = "";
                if (index < text.length - 1) {
                    result.push([]);
                }
            } else {
                value += character;
            }
        }
        result.at(-1).push(value);
        return result;
    }

    function selectedRows() {
        return rows().filter((row) => selectedRowKeys.has(row.getData()._rowKey));
    }

    function clearRowSelection() {
        selectedRowKeys.clear();
        rowAnchorKey = null;
        window.shiftHelperSelectedRowKeys = [];
        rows().forEach((row) => {
            row.getElement()?.classList.remove("journal-row--multi-selected");
        });
    }

    function renderRowSelection() {
        window.shiftHelperSelectedRowKeys = [...selectedRowKeys];
        rows().forEach((row) => {
            row.getElement()?.classList.toggle(
                "journal-row--multi-selected",
                selectedRowKeys.has(row.getData()._rowKey),
            );
        });
    }

    function selectRows(row, event) {
        const all = rows();
        const key = row.getData()._rowKey;
        if (event.shiftKey && rowAnchorKey) {
            const anchor = all.findIndex((candidate) => candidate.getData()._rowKey === rowAnchorKey);
            const target = all.indexOf(row);
            if (!event.ctrlKey && !event.metaKey) {
                selectedRowKeys.clear();
            }
            all.slice(Math.min(anchor, target), Math.max(anchor, target) + 1).forEach(
                (candidate) => selectedRowKeys.add(candidate.getData()._rowKey),
            );
        } else if (event.ctrlKey || event.metaKey) {
            if (selectedRowKeys.has(key)) {
                selectedRowKeys.delete(key);
            } else {
                selectedRowKeys.add(key);
            }
            rowAnchorKey = key;
        } else {
            selectedRowKeys.clear();
            selectedRowKeys.add(key);
            rowAnchorKey = key;
        }
        renderRowSelection();
    }

    function serializeRows(selected) {
        return selected.map((row) => editableFields
            .map((field) => escapeTsv(row.getData()[field] ?? ""))
            .join("\t")).join("\r\n");
    }

    async function writeClipboard(text, event = null) {
        rowClipboard = text;
        if (event?.clipboardData) {
            event.clipboardData.setData("text/plain", text);
            return;
        }
        try {
            await navigator.clipboard.writeText(text);
        } catch (_error) {
            // The internal clipboard remains available.
        }
    }

    async function readClipboard(event = null) {
        const fromEvent = event?.clipboardData?.getData("text/plain") || "";
        if (fromEvent) {
            rowClipboard = fromEvent;
            return fromEvent;
        }
        try {
            const system = await navigator.clipboard.readText();
            if (system) {
                rowClipboard = system;
                return system;
            }
        } catch (_error) {
            // Use the application clipboard.
        }
        return rowClipboard;
    }

    async function deletePersisted(row) {
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

    async function deleteRows(selected, record = true) {
        flushCellChanges();
        window.shiftHelperClearTransientGridState?.();
        const all = rows();
        const items = selected.map((row) => ({
            rowKey: row.getData()._rowKey,
            index: all.indexOf(row),
            data: structuredClone(row.getData()),
        }));
        for (const row of selected) {
            await deletePersisted(row);
            await row.delete();
        }
        clearRowSelection();
        table.redraw(true);
        if (record && items.length) {
            pushCommand({
                type: "delete-rows",
                label: items.length > 1 ? "удаление строк" : "удаление строки",
                items,
            });
        }
        setStatus("saved", items.length > 1 ? "Строки удалены" : "Строка удалена");
    }

    async function restoreRows(command) {
        window.shiftHelperClearTransientGridState?.();
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
            const current = rows();
            const reference = current[item.index] || false;
            const row = await table.addRow(data, false, reference);
            restored.push(row);
        }
        command.items.forEach((item, index) => {
            const row = restored[index];
            if (row) {
                item.rowKey = row.getData()._rowKey;
                item.data = structuredClone(row.getData());
            }
        });
        rebuildValueCache();
        table.redraw(true);
    }

    async function pasteRows(selected, text) {
        const matrix = parseTsv(text);
        applying = true;
        try {
            selected.forEach((row, rowIndex) => {
                editableFields.forEach((field, fieldIndex) => {
                    const value = String(matrix[rowIndex % matrix.length]?.[
                        fieldIndex % matrix[0].length
                    ] ?? "");
                    const key = cacheKey(row.getData()._rowKey, field);
                    suppressedValues.set(key, value);
                    valueCache.set(key, value);
                    row.getCell(field).setValue(value, true);
                });
            });
        } finally {
            applying = false;
        }
    }

    async function undo() {
        flushCellChanges();
        const command = undoStack.pop();
        if (!command) {
            return;
        }
        try {
            if (command.type === "cells") {
                applyCellChanges(command.changes, "before");
            } else if (command.type === "delete-rows") {
                await restoreRows(command);
            }
            redoStack.push(command);
            setStatus("dirty", `Отменено: ${command.label}`);
        } catch (error) {
            undoStack.push(command);
            setStatus("error", error.message || "Не удалось отменить операцию.");
        }
        updateButtons();
    }

    async function redo() {
        flushCellChanges();
        const command = redoStack.pop();
        if (!command) {
            return;
        }
        try {
            if (command.type === "cells") {
                applyCellChanges(command.changes, "after");
            } else if (command.type === "delete-rows") {
                const current = command.items.map((item) => rowByKey(item.rowKey)).filter(Boolean);
                await deleteRows(current, false);
            }
            undoStack.push(command);
            setStatus("dirty", `Повторено: ${command.label}`);
        } catch (error) {
            redoStack.push(command);
            setStatus("error", error.message || "Не удалось повторить операцию.");
        }
        updateButtons();
    }

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

    function showMenu(event) {
        closeMenu();
        menu = document.createElement("div");
        menu.className = "journal-workspace-menu";
        menu.style.left = `${event.clientX}px`;
        menu.style.top = `${event.clientY}px`;
        menu.append(
            menuButton("Копировать строку", async () => {
                await writeClipboard(serializeRows(selectedRows()));
            }),
            menuButton("Вырезать строку", async () => {
                const selected = selectedRows();
                await writeClipboard(serializeRows(selected));
                await deleteRows(selected);
            }),
            menuButton("Вставить строку", async () => {
                await pasteRows(selectedRows(), await readClipboard());
            }),
            menuButton(
                selectedRows().length > 1 ? "Удалить строки" : "Удалить строку",
                () => deleteRows(selectedRows()),
                true,
            ),
        );
        document.body.appendChild(menu);
    }

    table.on("tableBuilt", rebuildValueCache);
    table.on("renderComplete", () => {
        renderRowSelection();
        rows().forEach((row) => {
            if (!knownRowKeys.has(row)) {
                rememberRow(row);
            }
        });
    });
    table.on("cellEdited", queueCellChange);
    table.on("rowUpdated", (row) => {
        const oldKey = knownRowKeys.get(row);
        const newKey = row.getData()._rowKey;
        if (oldKey && oldKey !== newKey) {
            remapKey(oldKey, newKey);
        }
        rememberRow(row);
    });
    table.on("rowAdded", rememberRow);

    document.addEventListener("pointerdown", (event) => {
        if (!(event.target instanceof Element) || !root.contains(event.target)) {
            return;
        }
        const header = event.target.closest(".journal-row-number");
        if (header) {
            const row = rowFromElement(header);
            if (row) {
                event.preventDefault();
                event.stopImmediatePropagation();
                selectRows(row, event);
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

    document.addEventListener("contextmenu", (event) => {
        if (!(event.target instanceof Element) || !root.contains(event.target)) {
            return;
        }
        const header = event.target.closest(".journal-row-number");
        if (!header) {
            return;
        }
        const row = rowFromElement(header);
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
        showMenu(event);
    }, true);

    document.addEventListener("copy", (event) => {
        if (isTextControl(event.target) || !event.clipboardData || !selectedRows().length) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        void writeClipboard(serializeRows(selectedRows()), event);
    }, true);

    document.addEventListener("cut", (event) => {
        if (isTextControl(event.target) || !event.clipboardData || !selectedRows().length) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        const selected = selectedRows();
        void writeClipboard(serializeRows(selected), event).then(() => deleteRows(selected));
    }, true);

    document.addEventListener("paste", (event) => {
        if (isTextControl(event.target) || !event.clipboardData || !selectedRows().length) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        void pasteRows(selectedRows(), event.clipboardData.getData("text/plain"));
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
        if ((event.key === "Delete" || event.key === "Backspace") && selectedRows().length) {
            event.preventDefault();
            event.stopImmediatePropagation();
            void deleteRows(selectedRows());
        }
    }, true);

    undoButton.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        void undo();
    }, true);
    redoButton.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        void redo();
    }, true);

    document.addEventListener("pointerdown", (event) => {
        if (menu && event.target instanceof Element && !menu.contains(event.target)) {
            closeMenu();
        }
    });

    window.shiftHelperSelectedRowKeys = [];
    rebuildValueCache();
    updateButtons();
})();
