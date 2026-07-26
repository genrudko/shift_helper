"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table) {
        return;
    }

    const clipboardFields = [
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
    let openMenu = null;

    function showStatus(state, message) {
        const saveState = document.getElementById("journal-save-state");
        const text = saveState?.querySelector(".save-state__text");
        if (saveState) {
            saveState.dataset.state = state;
        }
        if (text) {
            text.textContent = message;
        }
    }

    function rowFromElement(element) {
        return table.getRows("active").find((row) => row.getElement() === element) || null;
    }

    function selectRow(row) {
        table.getRows().forEach((candidate) => {
            candidate.getElement().classList.toggle(
                "journal-row--selected",
                candidate === row,
            );
        });
    }

    function quoteTsv(value) {
        const text = String(value ?? "");
        if (!/[\t\r\n"]/.test(text)) {
            return text;
        }
        return `"${text.replaceAll('"', '""')}"`;
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
            if (character === '"') {
                quoted = true;
            } else if (character === "\t") {
                row.push(value);
                value = "";
            } else if (character === "\n") {
                row.push(value.replace(/\r$/, ""));
                rows.push(row);
                row = [];
                value = "";
            } else {
                value += character;
            }
        }
        row.push(value.replace(/\r$/, ""));
        rows.push(row);
        return rows.filter((candidate) => candidate.some((cell) => cell !== ""));
    }

    async function copyRow(row) {
        const data = row.getData();
        const text = clipboardFields.map((field) => quoteTsv(data[field] ?? "")).join("\t");
        try {
            await navigator.clipboard.writeText(text);
            showStatus("saved", "Строка скопирована");
        } catch (_error) {
            showStatus("error", "Браузер не разрешил запись в буфер обмена");
        }
    }

    function valuesForEditableFields(values) {
        const result = {};
        if (values.length >= clipboardFields.length) {
            clipboardFields.forEach((field, index) => {
                if (editableFields.includes(field)) {
                    result[field] = values[index] ?? "";
                }
            });
            return result;
        }
        editableFields.forEach((field, index) => {
            result[field] = values[index] ?? "";
        });
        return result;
    }

    async function pasteRow(row) {
        let text;
        try {
            text = await navigator.clipboard.readText();
        } catch (_error) {
            showStatus("error", "Браузер не разрешил чтение буфера обмена");
            return;
        }
        const values = parseTsv(text)[0];
        if (!values) {
            return;
        }
        const normalized = valuesForEditableFields(values);
        editableFields.forEach((field) => {
            row.getCell(field)?.setValue(normalized[field] ?? "", true);
        });
        row.reformat();
        showStatus("dirty", "Строка вставлена; выполняется сохранение");
    }

    function clearDraftRow(row) {
        if (!row.getData()._draft) {
            showStatus("error", "Сохранённую строку нельзя очистить как черновик");
            return;
        }
        editableFields.forEach((field) => row.getCell(field)?.setValue("", true));
        row.reformat();
    }

    function closeMenu() {
        openMenu?.remove();
        openMenu = null;
    }

    function addItem(menu, label, action) {
        const item = document.createElement("div");
        item.className = "tabulator-menu-item";
        item.tabIndex = 0;
        item.textContent = label;
        item.addEventListener("click", () => {
            closeMenu();
            void action();
        });
        item.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                item.click();
            }
        });
        menu.appendChild(item);
    }

    function addSeparator(menu) {
        const separator = document.createElement("div");
        separator.className = "tabulator-menu-separator";
        menu.appendChild(separator);
    }

    function openRowMenu(event, row) {
        closeMenu();
        selectRow(row);

        const menu = document.createElement("div");
        menu.className = "tabulator-menu shift-row-context-menu";
        menu.setAttribute("role", "menu");
        addItem(menu, "Копировать строку", () => copyRow(row));
        addItem(menu, "Вырезать строку", async () => {
            if (!row.getData()._draft) {
                showStatus(
                    "error",
                    "Вырезание сохранённой строки появится вместе с безопасным удалением",
                );
                return;
            }
            await copyRow(row);
            clearDraftRow(row);
        });
        addItem(menu, "Вставить строку", () => pasteRow(row));
        addSeparator(menu);
        addItem(menu, "Очистить черновую строку", () => clearDraftRow(row));

        document.body.appendChild(menu);
        const rect = menu.getBoundingClientRect();
        menu.style.left = `${Math.min(event.clientX, window.innerWidth - rect.width - 8)}px`;
        menu.style.top = `${Math.min(event.clientY, window.innerHeight - rect.height - 8)}px`;
        openMenu = menu;
        menu.querySelector(".tabulator-menu-item")?.focus({preventScroll: true});
    }

    root.addEventListener("contextmenu", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        const header = target.closest(".journal-row-number");
        const rowElement = header?.closest(".tabulator-row");
        const row = rowElement ? rowFromElement(rowElement) : null;
        if (!row) {
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation();
        openRowMenu(event, row);
    }, true);

    document.addEventListener("pointerdown", (event) => {
        if (openMenu && !openMenu.contains(event.target)) {
            closeMenu();
        }
    }, true);
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeMenu();
        }
    });
    window.addEventListener("blur", closeMenu);
})();
