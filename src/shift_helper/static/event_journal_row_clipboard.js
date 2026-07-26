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
    let internalRowClipboard = "";
    let selectedRowKey = null;

    function isTextControl(target) {
        return target instanceof Element && Boolean(
            target.closest(
                ".journal-stable-editor, #journal-search, "
                + ".tabulator-header-filter, .format-rules-dialog",
            ),
        );
    }

    function rowFromElement(element) {
        const rowElement = element?.closest?.(".tabulator-row");
        if (!rowElement) {
            return null;
        }
        return table.getRows().find((row) => row.getElement() === rowElement) || null;
    }

    function selectedRow() {
        if (selectedRowKey) {
            const byKey = table.getRows().find(
                (row) => row.getData()._rowKey === selectedRowKey,
            );
            if (byKey) {
                return byKey;
            }
        }
        const element = root.querySelector(".tabulator-row.journal-row--selected");
        return element ? rowFromElement(element) : null;
    }

    document.addEventListener("pointerdown", (event) => {
        if (!(event.target instanceof Element) || !root.contains(event.target)) {
            return;
        }
        const rowNumber = event.target.closest(".journal-row-number");
        if (rowNumber) {
            const row = rowFromElement(rowNumber);
            selectedRowKey = row?.getData()._rowKey || null;
            window.shiftHelperSelectedRowKey = selectedRowKey;
            return;
        }
        if (event.target.closest(".tabulator-cell")) {
            selectedRowKey = null;
            window.shiftHelperSelectedRowKey = null;
        }
    }, true);

    function escapeTsv(value) {
        const text = String(value ?? "");
        return /[\t\r\n"]/.test(text)
            ? `"${text.replace(/"/g, '""')}"`
            : text;
    }

    function serializeRow(row) {
        const data = row.getData();
        return editableFields.map((field) => escapeTsv(data[field])).join("\t");
    }

    function parseRow(text) {
        const values = [];
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
                values.push(value);
                value = "";
            } else if (character === "\n" || character === "\r") {
                if (character === "\r" && text[index + 1] === "\n") {
                    index += 1;
                }
                break;
            } else {
                value += character;
            }
        }
        values.push(value);
        return values;
    }

    function applyRow(text, row) {
        const values = parseRow(text);
        editableFields.forEach((field, index) => {
            row.getCell(field).setValue(values[index] ?? "", true);
        });
        saveState.dataset.state = "dirty";
        saveText.textContent = "Строка вставлена, выполняется сохранение…";
    }

    async function deleteRow(row) {
        const data = row.getData();
        const question = data._draft
            ? "Вырезать черновую строку?"
            : "Вырезать сохранённую строку? Снимок записи останется в журнале удаления.";
        if (!window.confirm(question)) {
            return;
        }
        if (!data._draft) {
            const response = await fetch(`${root.dataset.deleteBase}/${data.id}/row`, {
                method: "DELETE",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({revision: data.revision}),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !payload.ok) {
                saveState.dataset.state = "error";
                saveText.textContent = payload.error || "Не удалось вырезать строку.";
                return;
            }
        }
        selectedRowKey = null;
        window.shiftHelperSelectedRowKey = null;
        await row.delete();
        saveState.dataset.state = "saved";
        saveText.textContent = "Строка вырезана";
    }

    document.addEventListener("copy", (event) => {
        if (isTextControl(event.target) || !event.clipboardData) {
            return;
        }
        const row = selectedRow();
        if (!row) {
            return;
        }
        const text = serializeRow(row);
        event.preventDefault();
        event.stopImmediatePropagation();
        event.clipboardData.setData("text/plain", text);
        internalRowClipboard = text;
        saveState.dataset.state = "saved";
        saveText.textContent = "Строка скопирована";
    }, true);

    document.addEventListener("paste", (event) => {
        if (isTextControl(event.target) || !event.clipboardData) {
            return;
        }
        const row = selectedRow();
        if (!row) {
            return;
        }
        const text = event.clipboardData.getData("text/plain") || internalRowClipboard;
        if (!text) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        internalRowClipboard = text;
        applyRow(text, row);
    }, true);

    document.addEventListener("cut", (event) => {
        if (isTextControl(event.target) || !event.clipboardData) {
            return;
        }
        const row = selectedRow();
        if (!row) {
            return;
        }
        const text = serializeRow(row);
        event.preventDefault();
        event.stopImmediatePropagation();
        event.clipboardData.setData("text/plain", text);
        internalRowClipboard = text;
        void deleteRow(row);
    }, true);
})();
