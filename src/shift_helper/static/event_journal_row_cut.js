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
    let highlightedRow = null;

    function normalizeMatrix(cells) {
        if (!Array.isArray(cells) || !cells.length) {
            return [];
        }
        return Array.isArray(cells[0]) ? cells : [cells];
    }

    function selectedWholeRow() {
        const range = table.getRanges?.().at(-1);
        const matrix = normalizeMatrix(range?.getCells?.() || []);
        if (matrix.length !== 1 || matrix[0].length < editableFields.length) {
            return null;
        }
        const cells = matrix[0];
        const row = cells[0]?.getRow?.();
        if (!row || cells.some((cell) => cell.getRow?.() !== row)) {
            return null;
        }
        const fields = new Set(cells.map((cell) => cell.getField?.()));
        return editableFields.every((field) => fields.has(field)) ? row : null;
    }

    function refreshRowHighlight() {
        highlightedRow?.getElement().classList.remove("journal-row--selected");
        highlightedRow = selectedWholeRow();
        highlightedRow?.getElement().classList.add("journal-row--selected");
    }

    table.on("rangeChanged", refreshRowHighlight);
    table.on("renderComplete", refreshRowHighlight);

    function isTextControl(target) {
        return target instanceof Element && Boolean(
            target.closest(
                ".journal-stable-editor, #journal-search, "
                + ".tabulator-header-filter, .format-rules-dialog",
            ),
        );
    }

    function rowText(row) {
        return editableFields
            .map((field) => String(row.getData()[field] ?? ""))
            .join("\t");
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
            saveState.dataset.state = "saving";
            saveText.textContent = "Удаление строки…";
            const response = await fetch(`${root.dataset.deleteBase}/${data.id}/row`, {
                method: "DELETE",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({revision: data.revision}),
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !payload.ok) {
                saveState.dataset.state = "error";
                saveText.textContent = payload.error || "Не удалось удалить строку.";
                return;
            }
        }

        highlightedRow = null;
        await row.delete();
        saveState.dataset.state = "saved";
        saveText.textContent = cut ? "Строка вырезана" : "Строка удалена";
    }

    document.addEventListener("cut", (event) => {
        if (isTextControl(event.target) || !event.clipboardData) {
            return;
        }
        const row = selectedWholeRow();
        if (!row) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        event.clipboardData.setData("text/plain", rowText(row));
        void deleteRow(row, true);
    }, true);

    document.addEventListener("keydown", (event) => {
        if (isTextControl(event.target)) {
            return;
        }
        const row = selectedWholeRow();
        if (!row) {
            return;
        }
        if (event.key === "Delete" || ((event.ctrlKey || event.metaKey) && event.key === "-")) {
            event.preventDefault();
            event.stopImmediatePropagation();
            void deleteRow(row, false);
        }
    }, true);
})();
