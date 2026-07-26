"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const body = document.getElementById("event-journal-body");
    const draftTemplate = document.getElementById("event-draft-row-template");
    const saveState = document.getElementById("journal-save-state");
    const saveStateText = saveState?.querySelector(".save-state__text");
    const recordCount = document.querySelector(".journal-record-count");

    if (!root || !body || !draftTemplate || !saveState || !saveStateText) {
        return;
    }

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
        "author",
        "losses_mwh",
    ];
    const requiredFields = ["start_date", "start_time", "asset_label", "description"];
    const savePromises = new WeakMap();

    const pad = (value) => String(value).padStart(2, "0");

    function localDateValue(now = new Date()) {
        return `${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${now.getFullYear()}`;
    }

    function localTimeValue(now = new Date()) {
        return `${pad(now.getHours())}:${pad(now.getMinutes())}`;
    }

    function setSaveState(state, message) {
        saveState.dataset.state = state;
        saveStateText.textContent = message;
    }

    function rowInputs(row) {
        return Array.from(row.querySelectorAll("[data-field]"));
    }

    function fieldInput(row, fieldName) {
        return row.querySelector(`[data-field="${fieldName}"]`);
    }

    function autoGrow(textarea) {
        if (!(textarea instanceof HTMLTextAreaElement)) {
            return;
        }
        textarea.style.height = "33px";
        textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 33), 132)}px`;
    }

    function normalizeDate(value) {
        const cleaned = value.trim();
        if (cleaned === "!") {
            return localDateValue();
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

    function normalizeTime(value) {
        const cleaned = value.trim();
        if (cleaned === "!") {
            return localTimeValue();
        }
        const digits = cleaned.replace(/\D/g, "");
        if (/^\d{3,4}$/.test(cleaned)) {
            const padded = digits.padStart(4, "0");
            return `${padded.slice(0, 2)}:${padded.slice(2, 4)}`;
        }
        return cleaned;
    }

    function previousValue(input) {
        const row = input.closest("tr");
        const previousRow = row?.previousElementSibling;
        if (!previousRow) {
            return "";
        }
        return fieldInput(previousRow, input.dataset.field)?.value ?? "";
    }

    function normalizeInput(input) {
        let value = input.value;
        if (value.trim() === ".") {
            value = previousValue(input);
        }
        if (input.dataset.kind === "date") {
            value = normalizeDate(value);
        } else if (input.dataset.kind === "time") {
            value = normalizeTime(value);
        } else if (input.dataset.kind === "decimal") {
            value = value.trim().replace(".", ",");
        }
        input.value = value;
        autoGrow(input);
    }

    function markDirty(row) {
        row.dataset.dirty = "true";
        row.dataset.error = "false";
        setSaveState("dirty", "Есть несохранённые изменения");
    }

    function payloadForRow(row) {
        const payload = {revision: Number(row.dataset.revision || 0)};
        for (const input of rowInputs(row)) {
            payload[input.dataset.field] = input.value;
        }
        return payload;
    }

    function requiredFieldsComplete(row) {
        return requiredFields.every((fieldName) => fieldInput(row, fieldName)?.value.trim());
    }

    function updateRecordCount(delta) {
        if (!recordCount) {
            return;
        }
        const current = Number(recordCount.textContent.replace(/\D/g, "")) || 0;
        recordCount.textContent = `Записей: ${current + delta}`;
    }

    function applyServerRow(row, data) {
        for (const fieldName of fieldOrder) {
            const input = fieldInput(row, fieldName);
            if (input && Object.hasOwn(data, fieldName)) {
                input.value = data[fieldName] ?? "";
                autoGrow(input);
            }
        }
        const downtime = row.querySelector("[data-output=\"downtime\"]");
        if (downtime) {
            downtime.textContent = data.downtime ?? "";
        }
        row.dataset.eventId = String(data.id);
        row.dataset.revision = String(data.revision);
        row.dataset.status = data.status;
        row.classList.toggle("journal-row--closed", data.status === "closed");
        row.classList.remove("journal-row--draft");
        delete row.dataset.draftRow;
    }

    function prepareDraftRow(row) {
        row.className = "journal-row journal-row--draft";
        row.dataset.draftRow = "true";
        row.dataset.revision = "0";
        delete row.dataset.eventId;
        delete row.dataset.status;
        delete row.dataset.dirty;
        delete row.dataset.saving;
        delete row.dataset.error;

        for (const input of rowInputs(row)) {
            input.value = "";
            autoGrow(input);
        }
        fieldInput(row, "start_date").value = localDateValue();
        fieldInput(row, "start_time").value = localTimeValue();
        const downtime = row.querySelector("[data-output=\"downtime\"]");
        if (downtime) {
            downtime.textContent = "";
        }
        return row;
    }

    function appendDraftRow() {
        const fragment = draftTemplate.content.cloneNode(true);
        const row = fragment.querySelector("tr");
        prepareDraftRow(row);
        body.appendChild(fragment);
        return row;
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

    async function saveRow(row, {force = false} = {}) {
        const existingPromise = savePromises.get(row);
        if (existingPromise) {
            return existingPromise;
        }

        const isDraft = row.dataset.draftRow === "true";
        if (isDraft && !requiredFieldsComplete(row)) {
            if (force) {
                row.dataset.error = "true";
                setSaveState(
                    "error",
                    "Для записи заполните дату, время, оборудование и описание",
                );
            }
            return false;
        }
        if (!isDraft && row.dataset.dirty !== "true") {
            return true;
        }

        const promise = (async () => {
            row.dataset.saving = "true";
            setSaveState("saving", "Сохранение…");

            try {
                const eventId = row.dataset.eventId;
                const response = await fetch(
                    isDraft ? root.dataset.createUrl : `${root.dataset.updateBase}/${eventId}/row`,
                    {
                        method: isDraft ? "POST" : "PATCH",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(payloadForRow(row)),
                    },
                );
                const payload = await readResponse(response);
                applyServerRow(row, payload.row);
                delete row.dataset.dirty;
                delete row.dataset.error;
                if (isDraft) {
                    updateRecordCount(1);
                    appendDraftRow();
                }
                setSaveState("saved", "Все изменения сохранены");
                return true;
            } catch (error) {
                row.dataset.error = "true";
                setSaveState("error", error.message);
                return false;
            } finally {
                delete row.dataset.saving;
                savePromises.delete(row);
            }
        })();

        savePromises.set(row, promise);
        return promise;
    }

    function focusField(row, fieldName) {
        const input = fieldInput(row, fieldName);
        if (!input) {
            return false;
        }
        input.focus();
        if (input instanceof HTMLInputElement) {
            input.select();
        } else {
            input.setSelectionRange(input.value.length, input.value.length);
        }
        return true;
    }

    function moveVertical(input, direction) {
        const rows = Array.from(body.querySelectorAll("tr"));
        const currentRow = input.closest("tr");
        const currentIndex = rows.indexOf(currentRow);
        let targetRow = rows[currentIndex + direction];
        if (!targetRow && direction > 0) {
            targetRow = appendDraftRow();
        }
        if (targetRow) {
            focusField(targetRow, input.dataset.field);
        }
    }

    async function commitAndMove(input, direction = 1) {
        normalizeInput(input);
        const row = input.closest("tr");
        markDirty(row);
        const saved = await saveRow(row, {force: row.dataset.draftRow === "true"});
        if (saved) {
            moveVertical(input, direction);
        }
    }

    function ensureRows(count) {
        const rows = Array.from(body.querySelectorAll("tr"));
        while (rows.length < count) {
            rows.push(appendDraftRow());
        }
        return rows;
    }

    async function pasteTable(input, text) {
        const pastedRows = text
            .replace(/\r/g, "")
            .split("\n")
            .filter((line, index, lines) => line.length || index < lines.length - 1)
            .map((line) => line.split("\t"));
        const row = input.closest("tr");
        const allRows = Array.from(body.querySelectorAll("tr"));
        const rowIndex = allRows.indexOf(row);
        const fieldIndex = fieldOrder.indexOf(input.dataset.field);
        const rows = ensureRows(rowIndex + pastedRows.length);
        const changedRows = [];

        pastedRows.forEach((values, rowOffset) => {
            const targetRow = rows[rowIndex + rowOffset];
            values.forEach((value, columnOffset) => {
                const fieldName = fieldOrder[fieldIndex + columnOffset];
                const target = fieldName ? fieldInput(targetRow, fieldName) : null;
                if (target) {
                    target.value = value;
                    normalizeInput(target);
                }
            });
            markDirty(targetRow);
            changedRows.push(targetRow);
        });

        for (const changedRow of changedRows) {
            await saveRow(changedRow);
        }
    }

    body.addEventListener("input", (event) => {
        const input = event.target.closest("[data-field]");
        if (!input) {
            return;
        }
        autoGrow(input);
        markDirty(input.closest("tr"));
    });

    body.addEventListener("change", (event) => {
        const input = event.target.closest("[data-field]");
        if (!input) {
            return;
        }
        normalizeInput(input);
        const row = input.closest("tr");
        markDirty(row);
        if (row.dataset.draftRow !== "true" || requiredFieldsComplete(row)) {
            void saveRow(row);
        }
    });

    body.addEventListener("keydown", (event) => {
        const input = event.target.closest("[data-field]");
        if (!input) {
            return;
        }

        if (event.key === "Enter" && event.altKey && input instanceof HTMLTextAreaElement) {
            return;
        }

        if (event.key === "Enter") {
            event.preventDefault();
            if (event.ctrlKey) {
                void commitAndMove(input, 1);
            } else {
                void commitAndMove(input, event.shiftKey ? -1 : 1);
            }
            return;
        }

        if (event.key === "Tab" && !event.shiftKey) {
            const inputs = rowInputs(input.closest("tr"));
            if (inputs.indexOf(input) === inputs.length - 1) {
                event.preventDefault();
                const row = input.closest("tr");
                normalizeInput(input);
                markDirty(row);
                void saveRow(row, {force: row.dataset.draftRow === "true"}).then((saved) => {
                    if (!saved) {
                        return;
                    }
                    const rows = Array.from(body.querySelectorAll("tr"));
                    const nextRow = rows[rows.indexOf(row) + 1] || appendDraftRow();
                    focusField(nextRow, "start_date");
                });
            }
        }
    });

    body.addEventListener("paste", (event) => {
        const input = event.target.closest("[data-field]");
        if (!input) {
            return;
        }
        const text = event.clipboardData?.getData("text/plain") || "";
        if (!text.includes("\t") && !text.includes("\n")) {
            return;
        }
        event.preventDefault();
        void pasteTable(input, text);
    });

    body.addEventListener("click", (event) => {
        if (event.target.matches("input, textarea")) {
            return;
        }
        const cell = event.target.closest("td");
        const input = cell?.querySelector("[data-field]");
        input?.focus();
    });

    window.addEventListener("beforeunload", (event) => {
        if (!body.querySelector('tr[data-dirty="true"]')) {
            return;
        }
        event.preventDefault();
        event.returnValue = "";
    });

    for (const textarea of body.querySelectorAll("textarea")) {
        autoGrow(textarea);
    }

    const initialDraft = body.querySelector('tr[data-draft-row="true"]');
    if (initialDraft) {
        fieldInput(initialDraft, "asset_label")?.focus();
    }
})();
