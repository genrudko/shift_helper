"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const saveState = document.getElementById("journal-save-state");
    const saveText = saveState?.querySelector(".save-state__text");

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
    let internalClipboard = "";
    let contextRow = null;

    function setStatus(state, message) {
        saveState.dataset.state = state;
        saveText.textContent = message;
    }

    function isTextControl(target) {
        return target instanceof Element && Boolean(
            target.closest(
                ".journal-stable-editor, #journal-search, "
                + ".tabulator-header-filter, .format-rules-dialog",
            ),
        );
    }

    function isCellComponent(value) {
        return Boolean(
            value
            && typeof value.getField === "function"
            && typeof value.getRow === "function",
        );
    }

    function rowKey(cell) {
        return cell.getRow()?.getData?._rowKey
            || cell.getRow()?.getData?.()?._rowKey
            || "";
    }

    function canonicalMatrix(cells) {
        if (!Array.isArray(cells) || !cells.length) {
            return [];
        }
        const flat = (Array.isArray(cells[0]) ? cells.flat() : cells)
            .filter(isCellComponent);
        const tableRows = table.getRows();
        const rowOrder = new Map(
            tableRows.map((row, index) => [row.getData()._rowKey, index]),
        );
        const grouped = new Map();
        flat.forEach((cell) => {
            const key = rowKey(cell);
            if (!grouped.has(key)) {
                grouped.set(key, []);
            }
            grouped.get(key).push(cell);
        });
        return [...grouped.entries()]
            .sort(([left], [right]) => (rowOrder.get(left) ?? 0) - (rowOrder.get(right) ?? 0))
            .map(([_key, rowCells]) => rowCells.sort(
                (left, right) => editableFields.indexOf(left.getField())
                    - editableFields.indexOf(right.getField()),
            ));
    }

    function selectedMatrix() {
        const range = table.getRanges?.().at(-1);
        return canonicalMatrix(range?.getCells?.() || []);
    }

    function selectedWholeRow() {
        const matrix = selectedMatrix();
        if (matrix.length !== 1 || matrix[0].length < editableFields.length) {
            return null;
        }
        const cells = matrix[0];
        const key = rowKey(cells[0]);
        if (!key || cells.some((cell) => rowKey(cell) !== key)) {
            return null;
        }
        const fields = new Set(cells.map((cell) => cell.getField?.()));
        if (!editableFields.every((field) => fields.has(field))) {
            return null;
        }
        return table.getRows().find((row) => row.getData()._rowKey === key) || null;
    }

    function escapeTsv(value) {
        const text = String(value ?? "");
        if (!/[\t\r\n"]/.test(text)) {
            return text;
        }
        return `"${text.replace(/"/g, '""')}"`;
    }

    function serializeMatrix(matrix) {
        return matrix
            .map((row) => row.map((cell) => escapeTsv(cell?.getValue?.() ?? cell)).join("\t"))
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

            if (character === '"' && value === "") {
                quoted = true;
            } else if (character === "\t") {
                row.push(value);
                value = "";
            } else if (character === "\n") {
                row.push(value);
                rows.push(row);
                row = [];
                value = "";
            } else if (character !== "\r") {
                value += character;
            }
        }

        row.push(value);
        if (row.length > 1 || row[0] !== "" || !rows.length) {
            rows.push(row);
        }
        return rows;
    }

    function rowMatrix(row) {
        return [editableFields.map((field) => row.getCell(field))];
    }

    function expandTarget(startCell, rowCount, columnCount) {
        const rows = table.getRows();
        const startRow = rows.findIndex(
            (row) => row.getData()._rowKey === rowKey(startCell),
        );
        const startColumn = editableFields.indexOf(startCell.getField());
        if (startRow < 0 || startColumn < 0) {
            return [];
        }
        return Array.from({length: rowCount}, (_unused, rowOffset) => {
            const row = rows[startRow + rowOffset];
            return Array.from({length: columnCount}, (_unusedColumn, columnOffset) => {
                const field = editableFields[startColumn + columnOffset];
                return row && field ? row.getCell(field) : null;
            }).filter(Boolean);
        }).filter((row) => row.length);
    }

    function targetMatrixFor(source) {
        const selected = selectedMatrix();
        if (!selected.length || !selected[0]?.length) {
            return [];
        }
        const selectedSize = selected.reduce((total, row) => total + row.length, 0);
        if (selectedSize > 1 || (source.length === 1 && source[0].length === 1)) {
            return selected;
        }
        return expandTarget(selected[0][0], source.length, source[0].length);
    }

    function applySource(source, target) {
        if (!source.length || !source[0]?.length || !target.length || !target[0]?.length) {
            return;
        }
        target.forEach((row, rowIndex) => {
            row.forEach((cell, columnIndex) => {
                if (!cell || !editableFields.includes(cell.getField())) {
                    return;
                }
                cell.setValue(
                    source[rowIndex % source.length][columnIndex % source[0].length] ?? "",
                    true,
                );
            });
        });
        setStatus("dirty", "Вставлено, выполняется сохранение…");
    }

    async function deleteRow(row, cut) {
        const data = row.getData();
        const question = data._draft
            ? `${cut ? "Вырезать" : "Удалить"} черновую строку?`
            : `${cut ? "Вырезать" : "Удалить"} сохранённую строку? Снимок записи останется в журнале удаления.`;
        if (!window.confirm(question)) {
            return;
        }
        if (!data._draft) {
            setStatus("saving", "Удаление строки…");
            const response = await fetch(`${root.dataset.deleteBase}/${data.id}/row`, {
                method: "DELETE",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({revision: data.revision}),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !payload.ok) {
                setStatus("error", payload.error || "Не удалось удалить строку.");
                return;
            }
        }
        await row.delete();
        setStatus("saved", cut ? "Строка вырезана" : "Строка удалена");
    }

    async function writeClipboard(text) {
        internalClipboard = text;
        try {
            await navigator.clipboard.writeText(text);
        } catch (_error) {
            // The application clipboard remains available.
        }
    }

    async function readClipboard() {
        try {
            return await navigator.clipboard.readText() || internalClipboard;
        } catch (_error) {
            return internalClipboard;
        }
    }

    document.addEventListener("copy", (event) => {
        if (isTextControl(event.target) || !event.clipboardData) {
            return;
        }
        const matrix = selectedMatrix();
        if (!matrix.length) {
            return;
        }
        const text = serializeMatrix(matrix);
        event.preventDefault();
        event.stopImmediatePropagation();
        event.clipboardData.setData("text/plain", text);
        internalClipboard = text;
        setStatus("saved", selectedWholeRow() ? "Строка скопирована" : "Выделение скопировано");
    }, true);

    document.addEventListener("cut", (event) => {
        if (isTextControl(event.target) || !event.clipboardData) {
            return;
        }
        const row = selectedWholeRow();
        if (!row) {
            return;
        }
        const text = serializeMatrix(rowMatrix(row));
        event.preventDefault();
        event.stopImmediatePropagation();
        event.clipboardData.setData("text/plain", text);
        internalClipboard = text;
        void deleteRow(row, true);
    }, true);

    document.addEventListener("paste", (event) => {
        if (isTextControl(event.target) || !event.clipboardData) {
            return;
        }
        const text = event.clipboardData.getData("text/plain");
        if (!text || !selectedMatrix().length) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        internalClipboard = text;
        const source = parseTsv(text);
        applySource(source, targetMatrixFor(source));
    }, true);

    document.addEventListener("contextmenu", (event) => {
        if (!(event.target instanceof Element)) {
            return;
        }
        const rowNumber = event.target.closest(".journal-row-number");
        contextRow = rowNumber
            ? table.getRows().find((row) => row.getElement() === rowNumber.closest(".tabulator-row"))
                || null
            : null;
    }, true);

    document.addEventListener("click", (event) => {
        if (!(event.target instanceof HTMLButtonElement) || !contextRow) {
            return;
        }
        const label = event.target.textContent?.trim();
        if (!["Копировать строку", "Вырезать строку", "Вставить строку"].includes(label)) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        const row = contextRow;
        contextRow = null;

        if (label === "Копировать строку") {
            const text = serializeMatrix(rowMatrix(row));
            void writeClipboard(text).then(() => setStatus("saved", "Строка скопирована"));
        } else if (label === "Вырезать строку") {
            const text = serializeMatrix(rowMatrix(row));
            void writeClipboard(text).then(() => deleteRow(row, true));
        } else {
            void readClipboard().then((text) => {
                const source = parseTsv(text);
                applySource(source, [editableFields.map((field) => row.getCell(field))]);
            });
        }
    }, true);

    window.shiftHelperTsv = {parse: parseTsv, serialize: serializeMatrix};
})();
