"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const saveState = document.getElementById("journal-save-state");
    const saveText = saveState?.querySelector(".save-state__text");
    const recordCount = document.getElementById("journal-record-count");

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
    let rowClipboard = "";
    let menu = null;
    let fillSource = null;

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
            && typeof value.getRow === "function"
            && typeof value.setValue === "function",
        );
    }

    function normalizeMatrix(cells) {
        if (!Array.isArray(cells) || !cells.length) {
            return [];
        }
        return Array.isArray(cells[0]) ? cells : [cells];
    }

    function selectedMatrix() {
        const range = table.getRanges?.().at(-1);
        return normalizeMatrix(range?.getCells?.() || []);
    }

    function selectedRow() {
        const element = root.querySelector(".tabulator-row.journal-row--selected");
        if (!element) {
            return null;
        }
        return table.getRows().find((row) => row.getElement() === element) || null;
    }

    function rowFromElement(element) {
        const rowElement = element.closest(".tabulator-row");
        if (!rowElement) {
            return null;
        }
        return table.getRows().find((row) => row.getElement() === rowElement) || null;
    }

    function cellFromElement(element) {
        const cellElement = element.closest(".tabulator-cell");
        if (!cellElement) {
            return null;
        }
        for (const row of table.getRows("active")) {
            const cell = row.getCells().find((candidate) => candidate.getElement() === cellElement);
            if (cell) {
                return cell;
            }
        }
        return null;
    }

    function updateRecordCounter() {
        if (!recordCount) {
            return;
        }
        const all = table.getData().filter((row) => !row._draft).length;
        const visible = table.getRows("active").filter((row) => !row.getData()._draft).length;
        recordCount.textContent = all === visible
            ? `Записей: ${all}`
            : `Записей: ${all} · показано: ${visible}`;
    }

    function measureRowHeight(row) {
        const element = row.getElement();
        if (!element?.isConnected) {
            return;
        }
        let height = 34;
        for (const field of multilineFields) {
            const cell = row.getCell(field);
            const valueElement = cell?.getElement().querySelector(".journal-cell-value--multiline");
            if (valueElement) {
                height = Math.max(height, valueElement.scrollHeight + 1);
            }
        }
        element.style.height = `${height}px`;
        row.getCells().forEach((cell) => {
            cell.getElement().style.height = `${height}px`;
        });
        if (typeof row.normalizeHeight === "function") {
            row.normalizeHeight();
        }
    }

    function normalizeRowHeight(row) {
        window.requestAnimationFrame(() => measureRowHeight(row));
    }

    function normalizeVisibleRows() {
        table.getRows("visible").forEach(normalizeRowHeight);
    }

    table.on("tableBuilt", normalizeVisibleRows);
    table.on("renderComplete", normalizeVisibleRows);
    table.on("cellEdited", (cell) => normalizeRowHeight(cell.getRow()));
    table.on("rowUpdated", normalizeRowHeight);
    table.on("columnResized", normalizeVisibleRows);

    function parseClipboard(text) {
        return text
            .replace(/\r/g, "")
            .replace(/\n$/, "")
            .split("\n")
            .map((line) => line.split("\t"));
    }

    function applyMatrixToSelection(source, target) {
        if (!source.length || !source[0]?.length || !target.length || !target[0]?.length) {
            return;
        }
        const touchedRows = new Set();
        target.forEach((row, rowIndex) => {
            row.forEach((cell, columnIndex) => {
                if (!isCellComponent(cell) || !editableFields.includes(cell.getField())) {
                    return;
                }
                const value = source[rowIndex % source.length][
                    columnIndex % source[0].length
                ] ?? "";
                cell.setValue(value, true);
                touchedRows.add(cell.getRow());
            });
        });
        touchedRows.forEach(normalizeRowHeight);
        setStatus("dirty", "Диапазон вставлен, выполняется сохранение…");
    }

    document.addEventListener("paste", (event) => {
        if (isTextControl(event.target) || !event.clipboardData || selectedRow()) {
            return;
        }
        const target = selectedMatrix();
        const targetSize = target.length * (target[0]?.length || 0);
        if (targetSize <= 1) {
            return;
        }
        const text = event.clipboardData.getData("text/plain");
        if (!text) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        applyMatrixToSelection(parseClipboard(text), target);
    }, true);

    function parseNumber(value) {
        const cleaned = String(value ?? "").trim().replace(",", ".");
        if (!/^-?\d+(?:\.\d+)?$/.test(cleaned)) {
            return null;
        }
        return Number(cleaned);
    }

    function parseDate(value) {
        const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(String(value ?? "").trim());
        if (!match) {
            return null;
        }
        const result = new Date(Number(match[3]), Number(match[2]) - 1, Number(match[1]));
        return Number.isNaN(result.getTime()) ? null : result;
    }

    function formatDate(value) {
        return [
            String(value.getDate()).padStart(2, "0"),
            String(value.getMonth() + 1).padStart(2, "0"),
            value.getFullYear(),
        ].join(".");
    }

    function trailingNumber(value) {
        const match = /^(.*?)(-?\d+)(\D*)$/.exec(String(value ?? ""));
        if (!match) {
            return null;
        }
        return {prefix: match[1], number: Number(match[2]), suffix: match[3]};
    }

    function seriesValue(sequence, offset) {
        const numeric = sequence.map(parseNumber);
        if (numeric.every((value) => value !== null)) {
            const step = numeric.length >= 2
                ? numeric.at(-1) - numeric.at(-2)
                : 0;
            const result = numeric.at(-1) + (step * offset);
            return Number.isInteger(result) ? String(result) : String(result).replace(".", ",");
        }

        const dates = sequence.map(parseDate);
        if (dates.every((value) => value !== null)) {
            const day = 24 * 60 * 60 * 1000;
            const step = dates.length >= 2
                ? Math.round((dates.at(-1) - dates.at(-2)) / day)
                : 1;
            const result = new Date(dates.at(-1));
            result.setDate(result.getDate() + (step * offset));
            return formatDate(result);
        }

        const numbered = sequence.map(trailingNumber);
        if (
            numbered.every((value) => value !== null)
            && numbered.every(
                (value) => value.prefix === numbered[0].prefix
                    && value.suffix === numbered[0].suffix,
            )
        ) {
            const step = numbered.length >= 2
                ? numbered.at(-1).number - numbered.at(-2).number
                : 1;
            return `${numbered.at(-1).prefix}${
                numbered.at(-1).number + (step * offset)
            }${numbered.at(-1).suffix}`;
        }

        return sequence[(sequence.length + offset - 1) % sequence.length];
    }

    function tableCellPosition(cell) {
        const rows = table.getRows();
        return {
            row: rows.indexOf(cell.getRow()),
            column: editableFields.indexOf(cell.getField()),
        };
    }

    function createFillHandle() {
        const handle = document.createElement("div");
        handle.className = "journal-fill-handle";
        handle.hidden = true;
        handle.title = "Протянуть автозаполнение";
        document.body.appendChild(handle);

        const preview = document.createElement("div");
        preview.className = "journal-fill-preview";
        preview.hidden = true;
        document.body.appendChild(preview);

        return {handle, preview};
    }

    const {handle: fillHandle, preview: fillPreview} = createFillHandle();

    function updateFillHandle() {
        const matrix = selectedMatrix();
        const lastCell = matrix.at(-1)?.at(-1);
        if (!isCellComponent(lastCell) || selectedRow()) {
            fillHandle.hidden = true;
            return;
        }
        const rect = lastCell.getElement().getBoundingClientRect();
        fillHandle.style.left = `${rect.right - 5}px`;
        fillHandle.style.top = `${rect.bottom - 5}px`;
        fillHandle.hidden = false;
    }

    function previewFillTo(cell) {
        if (!fillSource || !isCellComponent(cell)) {
            return;
        }
        const sourceRect = fillSource.first.getElement().getBoundingClientRect();
        const targetRect = cell.getElement().getBoundingClientRect();
        fillPreview.style.left = `${Math.min(sourceRect.left, targetRect.left)}px`;
        fillPreview.style.top = `${Math.min(sourceRect.top, targetRect.top)}px`;
        fillPreview.style.width = `${Math.max(sourceRect.right, targetRect.right) - Math.min(sourceRect.left, targetRect.left)}px`;
        fillPreview.style.height = `${Math.max(sourceRect.bottom, targetRect.bottom) - Math.min(sourceRect.top, targetRect.top)}px`;
        fillPreview.hidden = false;
    }

    function applyFillTo(cell) {
        if (!fillSource || !isCellComponent(cell)) {
            return;
        }
        const rows = table.getRows();
        const target = tableCellPosition(cell);
        const source = fillSource;
        if (
            target.row < source.bottomRow
            || target.column < source.rightColumn
        ) {
            setStatus("error", "Автозаполнение пока выполняется вниз или вправо.");
            return;
        }

        const touchedRows = new Set();
        for (let rowIndex = source.topRow; rowIndex <= target.row; rowIndex += 1) {
            for (
                let columnIndex = source.leftColumn;
                columnIndex <= target.column;
                columnIndex += 1
            ) {
                if (
                    rowIndex <= source.bottomRow
                    && columnIndex <= source.rightColumn
                ) {
                    continue;
                }
                const targetRow = rows[rowIndex];
                const field = editableFields[columnIndex];
                const targetCell = targetRow?.getCell(field);
                if (!targetCell) {
                    continue;
                }

                let value;
                if (source.leftColumn === source.rightColumn && columnIndex === source.leftColumn) {
                    const sequence = source.matrix.map((row) => String(row[0]?.getValue() ?? ""));
                    value = seriesValue(sequence, rowIndex - source.bottomRow);
                } else if (source.topRow === source.bottomRow && rowIndex === source.topRow) {
                    const sequence = source.matrix[0].map((item) => String(item?.getValue() ?? ""));
                    value = seriesValue(sequence, columnIndex - source.rightColumn);
                } else {
                    const sourceRow = (rowIndex - source.topRow) % source.matrix.length;
                    const sourceColumn = (columnIndex - source.leftColumn) % source.matrix[0].length;
                    value = source.matrix[sourceRow][sourceColumn]?.getValue() ?? "";
                }
                targetCell.setValue(value, true);
                touchedRows.add(targetRow);
            }
        }
        touchedRows.forEach(normalizeRowHeight);
        setStatus("dirty", "Автозаполнение выполнено, сохраняю…");
    }

    fillHandle.addEventListener("pointerdown", (event) => {
        const matrix = selectedMatrix();
        const first = matrix[0]?.[0];
        const last = matrix.at(-1)?.at(-1);
        if (!isCellComponent(first) || !isCellComponent(last)) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        const firstPosition = tableCellPosition(first);
        const lastPosition = tableCellPosition(last);
        fillSource = {
            matrix,
            first,
            topRow: firstPosition.row,
            leftColumn: firstPosition.column,
            bottomRow: lastPosition.row,
            rightColumn: lastPosition.column,
            target: last,
        };
        fillHandle.setPointerCapture(event.pointerId);
    });

    fillHandle.addEventListener("pointermove", (event) => {
        if (!fillSource) {
            return;
        }
        const element = document.elementFromPoint(event.clientX, event.clientY);
        const cell = element ? cellFromElement(element) : null;
        if (cell && editableFields.includes(cell.getField())) {
            fillSource.target = cell;
            previewFillTo(cell);
        }
    });

    fillHandle.addEventListener("pointerup", (event) => {
        if (!fillSource) {
            return;
        }
        fillHandle.releasePointerCapture(event.pointerId);
        applyFillTo(fillSource.target);
        fillSource = null;
        fillPreview.hidden = true;
        updateFillHandle();
    });

    table.on("rangeChanged", updateFillHandle);
    table.on("cellClick", updateFillHandle);
    table.on("renderComplete", updateFillHandle);
    root.querySelector(".tabulator-tableholder")?.addEventListener("scroll", updateFillHandle);
    window.addEventListener("resize", updateFillHandle);

    function rowText(row) {
        return editableFields
            .map((field) => String(row.getData()[field] ?? ""))
            .join("\t");
    }

    async function copyRow(row, clipboardData = null) {
        const text = rowText(row);
        rowClipboard = text;
        if (clipboardData) {
            clipboardData.setData("text/plain", text);
            return;
        }
        try {
            await navigator.clipboard.writeText(text);
        } catch (_error) {
            // The internal row clipboard remains available.
        }
        setStatus("saved", "Строка скопирована");
    }

    async function deleteRow(row, {cut = false} = {}) {
        const data = row.getData();
        const hasData = editableFields.some((field) => String(data[field] ?? "").trim());
        if (!hasData) {
            await row.delete();
            updateRecordCounter();
            return true;
        }
        const question = data._draft
            ? `${cut ? "Вырезать" : "Удалить"} черновую строку?`
            : `${cut ? "Вырезать" : "Удалить"} сохранённую строку? Снимок записи останется в журнале удаления.`;
        if (!window.confirm(question)) {
            return false;
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
                return false;
            }
        }

        await row.delete();
        updateRecordCounter();
        setStatus("saved", cut ? "Строка вырезана" : "Строка удалена");
        return true;
    }

    function closeMenu() {
        menu?.remove();
        menu = null;
    }

    function menuButton(label, action, danger = false) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        button.className = danger ? "journal-row-menu__danger" : "";
        button.addEventListener("click", () => {
            closeMenu();
            void action();
        });
        return button;
    }

    function showRowMenu(event, row) {
        closeMenu();
        menu = document.createElement("div");
        menu.className = "journal-row-menu";
        menu.style.left = `${event.clientX}px`;
        menu.style.top = `${event.clientY}px`;
        menu.append(
            menuButton("Копировать строку", () => copyRow(row)),
            menuButton("Вырезать строку", async () => {
                await copyRow(row);
                await deleteRow(row, {cut: true});
            }),
            menuButton("Вставить строку", async () => {
                let text = rowClipboard;
                try {
                    text = await navigator.clipboard.readText() || text;
                } catch (_error) {
                    // Use the application clipboard.
                }
                if (!text) {
                    return;
                }
                const values = parseClipboard(text)[0] || [];
                const cells = editableFields.map((field) => row.getCell(field));
                applyMatrixToSelection([values], [cells]);
            }),
            menuButton("Удалить строку", () => deleteRow(row), true),
        );
        document.body.appendChild(menu);
        const rect = menu.getBoundingClientRect();
        if (rect.right > window.innerWidth) {
            menu.style.left = `${window.innerWidth - rect.width - 8}px`;
        }
        if (rect.bottom > window.innerHeight) {
            menu.style.top = `${window.innerHeight - rect.height - 8}px`;
        }
    }

    document.addEventListener("contextmenu", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const rowNumber = target.closest(".journal-row-number");
        if (!rowNumber) {
            return;
        }
        const row = rowFromElement(rowNumber);
        if (!row) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        showRowMenu(event, row);
    }, true);

    document.addEventListener("pointerdown", (event) => {
        if (menu && event.target instanceof Element && !menu.contains(event.target)) {
            closeMenu();
        }
    });

    document.addEventListener("cut", (event) => {
        if (isTextControl(event.target) || !event.clipboardData) {
            return;
        }
        const row = selectedRow();
        if (!row) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        void copyRow(row, event.clipboardData).then(() => deleteRow(row, {cut: true}));
    }, true);

    document.addEventListener("keydown", (event) => {
        if (isTextControl(event.target)) {
            return;
        }
        const row = selectedRow();
        if (!row) {
            return;
        }
        if (event.key === "Delete" || ((event.ctrlKey || event.metaKey) && event.key === "-")) {
            event.preventDefault();
            event.stopImmediatePropagation();
            void deleteRow(row);
        }
    }, true);
})();
