"use strict";

/* Operator acceptance stage 7: configurable dropdown lists per journal column. */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table || root.dataset.acceptanceStage7 === "ready") return;

    const iconUrl = "/static/shift_helper_icons_v1.svg";
    const storeKey = "shift-helper-column-lists-v1";
    const fields = {
        start_date: "Дата остановки",
        start_time: "Время",
        asset_label: "№ ВЭУ / оборудование",
        description: "Описание события",
        reason: "Причина",
        actions: "Действия персонала",
        performer: "Исполнитель",
        end_date: "Дата пуска",
        end_time: "Время пуска",
        author: "Кто внёс запись",
    };
    const beforeValues = new WeakMap();
    const validationGuard = new WeakSet();
    let dialog = null;
    let popup = null;
    let popupState = null;
    let selectedField = "performer";

    function svg(name) {
        return `<svg class="ribbon-icon" aria-hidden="true"><use href="${iconUrl}#${name}"></use></svg>`;
    }

    function loadStore() {
        try {
            const value = JSON.parse(localStorage.getItem(storeKey) || "{}");
            return value && typeof value === "object" ? value : {};
        } catch (_error) {
            return {};
        }
    }

    function saveStore(store) {
        try { localStorage.setItem(storeKey, JSON.stringify(store)); } catch (_error) { /* optional */ }
    }

    function normalizeValues(raw) {
        const seen = new Set();
        const result = [];
        String(raw || "").split(/\r?\n/).forEach((item) => {
            const value = item.trim();
            const key = value.toLocaleLowerCase("ru");
            if (!value || seen.has(key)) return;
            seen.add(key);
            result.push(value);
        });
        return result;
    }

    function configFor(field) {
        const config = loadStore()[field];
        return {
            enabled: Boolean(config?.enabled && Array.isArray(config.values) && config.values.length),
            allowCustom: config?.allowCustom !== false,
            autocomplete: config?.autocomplete !== false,
            values: Array.isArray(config?.values) ? [...config.values] : [],
        };
    }

    function buildRibbonControl() {
        if (document.getElementById("stage7-open-lists")) return;
        const panel = document.querySelector('[data-ribbon-panel="data"]');
        if (!panel) return;
        const group = document.createElement("section");
        group.className = "ribbon-group stage7-list-group";
        group.setAttribute("aria-label", "Выпадающие списки");
        group.innerHTML = `
            <button class="ribbon-command ribbon-command--large stage7-list-command" id="stage7-open-lists" type="button">
                ${svg("conditional")}<span>Выпадающие<br>списки</span>
            </button>
            <span class="ribbon-group__label">Проверка данных</span>
        `;
        const searchGroup = panel.querySelector(".ribbon-group--search");
        panel.insertBefore(group, searchGroup || null);
        group.querySelector("#stage7-open-lists")?.addEventListener("click", openDialog);
    }

    function buildDialog() {
        if (dialog) return dialog;
        dialog = document.createElement("dialog");
        dialog.id = "stage7-list-dialog";
        dialog.className = "stage7-list-dialog";
        dialog.innerHTML = `
            <form method="dialog" class="stage7-list-panel">
                <header class="stage7-list-header">
                    <div><h2>Выпадающие списки</h2><p>Собственные справочники для оборудования, исполнителей и других столбцов.</p></div>
                    <button class="stage7-list-close" value="cancel" aria-label="Закрыть">×</button>
                </header>
                <div class="stage7-list-grid">
                    <section class="stage7-list-settings">
                        <label>Столбец<select id="stage7-list-field"></select></label>
                        <div class="stage7-list-checks">
                            <label><input id="stage7-list-enabled" type="checkbox">Использовать список</label>
                            <label><input id="stage7-list-autocomplete" type="checkbox">Фильтровать по мере ввода</label>
                            <label><input id="stage7-list-custom" type="checkbox">Разрешать значения не из списка</label>
                        </div>
                        <div class="stage7-list-info" id="stage7-list-info"></div>
                    </section>
                    <label class="stage7-list-values-label">Значения — по одному в строке<textarea id="stage7-list-values" spellcheck="false"></textarea></label>
                </div>
                <div class="stage7-list-actions">
                    <div class="stage7-list-actions-left"><button id="stage7-import-values" type="button">Добавить из журнала</button><button id="stage7-sort-values" type="button">Сортировать</button><button id="stage7-clear-values" type="button">Очистить список</button></div>
                    <div class="stage7-list-actions-right"><button value="cancel">Отмена</button><button id="stage7-save-list" type="button">Сохранить</button></div>
                </div>
            </form>
        `;
        document.body.appendChild(dialog);
        const fieldSelect = dialog.querySelector("#stage7-list-field");
        Object.entries(fields).forEach(([value, label]) => fieldSelect?.add(new Option(label, value)));
        fieldSelect?.addEventListener("change", (event) => {
            selectedField = event.target.value;
            loadDialogField();
        });
        dialog.querySelector("#stage7-list-values")?.addEventListener("input", updateDialogInfo);
        dialog.querySelector("#stage7-import-values")?.addEventListener("click", importCurrentValues);
        dialog.querySelector("#stage7-sort-values")?.addEventListener("click", sortDialogValues);
        dialog.querySelector("#stage7-clear-values")?.addEventListener("click", () => {
            const target = dialog.querySelector("#stage7-list-values");
            if (target) target.value = "";
            updateDialogInfo();
        });
        dialog.querySelector("#stage7-save-list")?.addEventListener("click", saveDialogField);
        dialog.addEventListener("click", (event) => {
            if (event.target === dialog) dialog.close("cancel");
        });
        return dialog;
    }

    function openDialog() {
        const target = buildDialog();
        const activeField = window.shiftHelperAcceptanceStage4?.selectedCells?.()[0]?.getField?.();
        selectedField = fields[activeField] ? activeField : selectedField;
        const fieldSelect = target.querySelector("#stage7-list-field");
        if (fieldSelect) fieldSelect.value = selectedField;
        loadDialogField();
        if (!target.open) target.showModal();
    }

    function loadDialogField() {
        if (!dialog) return;
        const config = configFor(selectedField);
        dialog.querySelector("#stage7-list-enabled").checked = config.enabled;
        dialog.querySelector("#stage7-list-autocomplete").checked = config.autocomplete;
        dialog.querySelector("#stage7-list-custom").checked = config.allowCustom;
        dialog.querySelector("#stage7-list-values").value = config.values.join("\n");
        updateDialogInfo();
    }

    function updateDialogInfo() {
        const values = normalizeValues(dialog?.querySelector("#stage7-list-values")?.value || "");
        const info = dialog?.querySelector("#stage7-list-info");
        if (info) {
            info.textContent = values.length
                ? `Уникальных значений: ${values.length}. Список хранится локально на этом рабочем месте.`
                : "Список пуст. Введите значения вручную или добавьте уникальные данные из журнала.";
        }
    }

    function currentColumnValues(field) {
        const seen = new Set();
        const values = [];
        table.getRows("active").forEach((row) => {
            const value = String(row.getData()[field] ?? "").trim();
            const key = value.toLocaleLowerCase("ru");
            if (!value || seen.has(key)) return;
            seen.add(key);
            values.push(value);
        });
        return values;
    }

    function importCurrentValues() {
        const textarea = dialog?.querySelector("#stage7-list-values");
        if (!textarea) return;
        const combined = normalizeValues([
            textarea.value,
            ...currentColumnValues(selectedField),
        ].join("\n"));
        textarea.value = combined.join("\n");
        updateDialogInfo();
    }

    function sortDialogValues() {
        const textarea = dialog?.querySelector("#stage7-list-values");
        if (!textarea) return;
        textarea.value = normalizeValues(textarea.value)
            .sort((left, right) => left.localeCompare(right, "ru", {numeric: true, sensitivity: "base"}))
            .join("\n");
        updateDialogInfo();
    }

    function saveDialogField() {
        const values = normalizeValues(dialog?.querySelector("#stage7-list-values")?.value || "");
        const store = loadStore();
        const enabled = Boolean(dialog?.querySelector("#stage7-list-enabled")?.checked) && values.length > 0;
        store[selectedField] = {
            enabled,
            autocomplete: Boolean(dialog?.querySelector("#stage7-list-autocomplete")?.checked),
            allowCustom: Boolean(dialog?.querySelector("#stage7-list-custom")?.checked),
            values,
        };
        saveStore(store);
        applyIndicators();
        closePopup();
        dialog?.close("saved");
        root.dataset.configuredListField = selectedField;
        root.dataset.configuredListSize = String(values.length);
    }

    function applyIndicators() {
        const store = loadStore();
        table.getRows("active").forEach((row) => row.getCells().forEach((cell) => {
            const field = cell.getField();
            const config = store[field];
            cell.getElement?.()?.classList.toggle(
                "stage7-list-cell",
                Boolean(config?.enabled && Array.isArray(config.values) && config.values.length),
            );
        }));
    }

    function filteredValues(config, query) {
        if (!config.autocomplete) return [...config.values];
        const needle = String(query || "").toLocaleLowerCase("ru");
        if (!needle) return [...config.values];
        return config.values.filter((value) => value.toLocaleLowerCase("ru").includes(needle));
    }

    function closePopup() {
        popup?.remove();
        popup = null;
        popupState = null;
    }

    function placePopup(editor) {
        if (!popup) return;
        const rect = editor.getBoundingClientRect();
        const width = Math.max(180, rect.width);
        popup.style.width = `${Math.min(width, innerWidth - 16)}px`;
        const box = popup.getBoundingClientRect();
        const below = rect.bottom + 3;
        const top = below + box.height <= innerHeight - 8
            ? below
            : Math.max(8, rect.top - box.height - 3);
        popup.style.left = `${Math.max(8, Math.min(rect.left, innerWidth - box.width - 8))}px`;
        popup.style.top = `${top}px`;
    }

    function chooseValue(value) {
        const editor = popupState?.editor;
        if (!(editor instanceof HTMLInputElement || editor instanceof HTMLTextAreaElement)) return;
        editor.value = value;
        editor.dispatchEvent(new Event("input", {bubbles: true}));
        editor.setSelectionRange(value.length, value.length);
        closePopup();
        editor.focus();
    }

    function renderPopup() {
        if (!popupState) return;
        const {editor, config} = popupState;
        const values = filteredValues(config, editor.value);
        if (!popup) {
            popup = document.createElement("div");
            popup.className = "stage7-list-popup";
            popup.id = "stage7-list-popup";
            popup.setAttribute("role", "listbox");
            document.body.appendChild(popup);
        }
        popup.replaceChildren();
        if (!values.length) {
            const empty = document.createElement("div");
            empty.className = "stage7-list-popup-empty";
            empty.textContent = config.allowCustom
                ? "Совпадений нет — можно оставить собственное значение."
                : "Совпадений нет. Выберите значение из списка.";
            popup.appendChild(empty);
            popupState.values = [];
            popupState.index = -1;
            placePopup(editor);
            return;
        }
        popupState.values = values;
        popupState.index = Math.min(Math.max(0, popupState.index), values.length - 1);
        values.forEach((value, index) => {
            const button = document.createElement("button");
            button.type = "button";
            button.role = "option";
            button.dataset.listValue = value;
            button.textContent = value;
            button.setAttribute("aria-selected", String(index === popupState.index));
            button.addEventListener("pointerdown", (event) => event.preventDefault());
            button.addEventListener("click", () => chooseValue(value));
            popup.appendChild(button);
        });
        placePopup(editor);
    }

    function movePopupSelection(step) {
        if (!popupState?.values?.length) return;
        popupState.index = (
            popupState.index + step + popupState.values.length
        ) % popupState.values.length;
        popup.querySelectorAll("button").forEach((button, index) => {
            button.setAttribute("aria-selected", String(index === popupState.index));
        });
        popup.querySelector('button[aria-selected="true"]')?.scrollIntoView({block: "nearest"});
    }

    function attachEditor(cell) {
        const field = cell.getField();
        const config = configFor(field);
        if (!config.enabled) return;
        requestAnimationFrame(() => {
            const editor = cell.getElement?.()?.querySelector(".journal-stable-editor")
                || root.querySelector(".journal-stable-editor");
            if (!(editor instanceof HTMLInputElement || editor instanceof HTMLTextAreaElement)) return;
            closePopup();
            popupState = {cell, editor, config, values: [], index: 0};
            const refresh = () => renderPopup();
            editor.addEventListener("input", refresh);
            editor.addEventListener("focus", refresh);
            editor.addEventListener("keydown", (event) => {
                if (event.key === "ArrowDown" && popupState) {
                    event.preventDefault();
                    movePopupSelection(1);
                } else if (event.key === "ArrowUp" && popupState) {
                    event.preventDefault();
                    movePopupSelection(-1);
                } else if (event.key === "Enter" && popupState?.values?.length) {
                    event.preventDefault();
                    chooseValue(popupState.values[popupState.index]);
                } else if (event.key === "Escape") {
                    closePopup();
                }
            });
            renderPopup();
        });
    }

    function valueAllowed(value, config) {
        if (config.allowCustom || String(value || "").trim() === "") return true;
        const target = String(value).trim().toLocaleLowerCase("ru");
        return config.values.some((candidate) => candidate.toLocaleLowerCase("ru") === target);
    }

    function validateCell(cell) {
        if (validationGuard.has(cell)) return;
        const config = configFor(cell.getField());
        if (!config.enabled || valueAllowed(cell.getValue(), config)) {
            cell.getElement?.()?.classList.remove("stage7-list-invalid");
            return;
        }
        const previous = beforeValues.get(cell) ?? "";
        validationGuard.add(cell);
        try {
            cell.setValue(previous, true);
            cell.getElement?.()?.classList.add("stage7-list-invalid");
            root.dataset.listValidationError = cell.getField();
            const saveState = document.getElementById("journal-save-state");
            const saveText = saveState?.querySelector(".save-state__text");
            if (saveState) saveState.dataset.state = "error";
            if (saveText) saveText.textContent = "Значение не входит в разрешённый список";
        } finally {
            validationGuard.delete(cell);
        }
    }

    function currentCell() {
        return window.shiftHelperAcceptanceStage4?.selectedCells?.()[0] || null;
    }

    table.on("cellEditing", (cell) => {
        beforeValues.set(cell, String(cell.getValue() ?? ""));
        attachEditor(cell);
    });
    table.on("cellEdited", (cell) => {
        closePopup();
        validateCell(cell);
        applyIndicators();
    });
    table.on("renderComplete", applyIndicators);
    table.on("rowUpdated", applyIndicators);

    window.addEventListener("pointerdown", (event) => {
        if (!popup || !(event.target instanceof Element)) return;
        if (popup.contains(event.target) || popupState?.editor?.contains(event.target)) return;
        closePopup();
    }, true);
    window.addEventListener("resize", closePopup);
    root.querySelector(".tabulator-tableholder")?.addEventListener("scroll", closePopup, {passive: true});
    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closePopup();
        if (!event.altKey || event.key !== "ArrowDown") return;
        const cell = currentCell();
        if (!cell || !configFor(cell.getField()).enabled) return;
        event.preventDefault();
        try { cell.edit(); } catch (_error) { /* non-editable cell */ }
    }, true);

    buildRibbonControl();
    buildDialog();
    applyIndicators();
    window.shiftHelperAcceptanceStage7 = {
        openDialog,
        configFor,
        applyIndicators,
        openForCell: attachEditor,
        getStore: loadStore,
    };
    root.dataset.acceptanceStage7 = "ready";
})();
