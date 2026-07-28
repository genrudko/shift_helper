"use strict";

/* Operator acceptance stage 6: Page Layout, print preview and semantic print sheet. */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const ribbon = document.getElementById("journal-ribbon");
    if (!root || !table || !ribbon || root.dataset.acceptanceStage6 === "ready") return;

    const iconUrl = "/static/shift_helper_icons_v1.svg";
    const settingsKey = "shift-helper-page-layout-v1";
    const defaults = {
        paper: "A4",
        orientation: "landscape",
        margins: "normal",
        fit: "width",
        gridlines: true,
        repeatHeaders: true,
        scope: "all",
        title: "Журнал событий",
        footer: "Кочубеевская ВЭС",
    };
    const papers = {
        A4: {label: "A4", css: "A4"},
        A3: {label: "A3", css: "A3"},
        Letter: {label: "Letter", css: "Letter"},
    };
    const margins = {
        narrow: {label: "Узкие", css: "7mm"},
        normal: {label: "Обычные", css: "12mm"},
        wide: {label: "Широкие", css: "20mm"},
    };
    let settings = loadSettings();
    let setupDialog = null;
    let previewDialog = null;
    let printSheet = null;

    function svg(name) {
        return `<svg class="ribbon-icon" aria-hidden="true"><use href="${iconUrl}#${name}"></use></svg>`;
    }

    function loadSettings() {
        try {
            return {...defaults, ...JSON.parse(localStorage.getItem(settingsKey) || "{}")};
        } catch (_error) {
            return {...defaults};
        }
    }

    function saveSettings() {
        try { localStorage.setItem(settingsKey, JSON.stringify(settings)); } catch (_error) { /* optional */ }
    }

    function normalizeSettings(next) {
        return {
            paper: Object.hasOwn(papers, next.paper) ? next.paper : defaults.paper,
            orientation: ["portrait", "landscape"].includes(next.orientation)
                ? next.orientation
                : defaults.orientation,
            margins: Object.hasOwn(margins, next.margins) ? next.margins : defaults.margins,
            fit: ["actual", "width"].includes(next.fit) ? next.fit : defaults.fit,
            gridlines: next.gridlines !== false,
            repeatHeaders: next.repeatHeaders !== false,
            scope: ["all", "selection"].includes(next.scope) ? next.scope : defaults.scope,
            title: String(next.title || defaults.title),
            footer: String(next.footer || defaults.footer),
        };
    }

    function pageStyleText() {
        return `@page { size: ${papers[settings.paper].css} ${settings.orientation}; margin: ${
            margins[settings.margins].css
        }; }`;
    }

    function applySettings({persist = true} = {}) {
        settings = normalizeSettings(settings);
        if (persist) saveSettings();
        root.dataset.printPaper = settings.paper;
        root.dataset.printOrientation = settings.orientation;
        root.dataset.printMargins = settings.margins;
        root.dataset.printFit = settings.fit;
        root.dataset.printGridlines = String(settings.gridlines);
        root.dataset.printRepeatHeaders = String(settings.repeatHeaders);
        root.dataset.printScope = settings.scope;

        let pageStyle = document.getElementById("stage6-page-style");
        if (!pageStyle) {
            pageStyle = document.createElement("style");
            pageStyle.id = "stage6-page-style";
            document.head.appendChild(pageStyle);
        }
        pageStyle.textContent = pageStyleText();
        syncControls();
    }

    function syncControls() {
        const values = {
            "stage6-paper": settings.paper,
            "stage6-orientation": settings.orientation,
            "stage6-margins": settings.margins,
            "stage6-fit": settings.fit,
        };
        Object.entries(values).forEach(([id, value]) => {
            const control = document.getElementById(id);
            if (control && control.value !== value) control.value = value;
        });
        const setupValues = {
            "stage6-setup-paper": settings.paper,
            "stage6-setup-orientation": settings.orientation,
            "stage6-setup-margins": settings.margins,
            "stage6-setup-fit": settings.fit,
            "stage6-setup-scope": settings.scope,
            "stage6-setup-title": settings.title,
            "stage6-setup-footer": settings.footer,
        };
        Object.entries(setupValues).forEach(([id, value]) => {
            const control = document.getElementById(id);
            if (control && control.value !== value) control.value = value;
        });
        const gridlines = document.getElementById("stage6-setup-gridlines");
        if (gridlines) gridlines.checked = settings.gridlines;
        const repeat = document.getElementById("stage6-setup-repeat");
        if (repeat) repeat.checked = settings.repeatHeaders;
    }

    function activateLayoutTab() {
        document.querySelectorAll("[data-ribbon-tab]").forEach((button) => {
            button.setAttribute("aria-selected", String(button.dataset.ribbonTab === "layout"));
        });
        document.querySelectorAll("[data-ribbon-panel]").forEach((panel) => {
            panel.hidden = panel.dataset.ribbonPanel !== "layout";
        });
        if (ribbon.dataset.ribbonState === "collapsed") ribbon.dataset.ribbonState = "temporary";
    }

    function option(value, label) {
        return `<option value="${value}">${label}</option>`;
    }

    function ribbonSelect(id, label, options) {
        return `<label class="stage6-layout-control"><span>${label}</span><select id="${id}">${options}</select></label>`;
    }

    function buildLayoutTab() {
        if (document.querySelector('[data-ribbon-tab="layout"]')) return;
        const tabs = ribbon.querySelector(".journal-ribbon__tabs");
        const viewTab = tabs?.querySelector('[data-ribbon-tab="view"]');
        const panels = ribbon.querySelector(".journal-ribbon__panels");
        const viewPanel = panels?.querySelector('[data-ribbon-panel="view"]');
        if (!tabs || !panels) return;

        const tab = document.createElement("button");
        tab.className = "ribbon-tab";
        tab.type = "button";
        tab.role = "tab";
        tab.dataset.ribbonTab = "layout";
        tab.setAttribute("aria-selected", "false");
        tab.textContent = "Разметка";
        tab.addEventListener("click", activateLayoutTab);
        tabs.insertBefore(tab, viewTab || tabs.querySelector("#ribbon-collapse"));

        const panel = document.createElement("div");
        panel.className = "ribbon-panel";
        panel.dataset.ribbonPanel = "layout";
        panel.role = "tabpanel";
        panel.hidden = true;
        panel.innerHTML = `
            <section class="ribbon-group stage6-layout-group" aria-label="Параметры страницы">
                <div class="stage6-layout-controls">
                    ${ribbonSelect("stage6-paper", "Размер", Object.entries(papers)
                        .map(([value, item]) => option(value, item.label)).join(""))}
                    ${ribbonSelect("stage6-orientation", "Ориентация", option("portrait", "Книжная") + option("landscape", "Альбомная"))}
                    ${ribbonSelect("stage6-margins", "Поля", Object.entries(margins)
                        .map(([value, item]) => option(value, item.label)).join(""))}
                </div>
                <span class="ribbon-group__label">Параметры страницы</span>
            </section>
            <section class="ribbon-group" aria-label="Масштаб печати">
                <div class="stage6-layout-controls">
                    ${ribbonSelect("stage6-fit", "Вписать", option("width", "По ширине") + option("actual", "100%"))}
                    <button class="ribbon-command" id="stage6-open-setup" type="button">${svg("view-settings")}<span>Все параметры</span></button>
                </div>
                <span class="ribbon-group__label">Масштаб</span>
            </section>
            <section class="ribbon-group stage6-print-group" aria-label="Печать">
                <div class="stage6-print-actions">
                    <button id="stage6-open-preview" type="button">${svg("search")}<span>Предпросмотр</span></button>
                    <button id="stage6-print-now" type="button">${svg("export")}<span>Печать</span></button>
                </div>
                <span class="ribbon-group__label">Печать</span>
            </section>
        `;
        panels.insertBefore(panel, viewPanel || null);

        ["stage6-paper", "stage6-orientation", "stage6-margins", "stage6-fit"].forEach((id) => {
            panel.querySelector(`#${id}`)?.addEventListener("change", (event) => {
                const property = id.replace("stage6-", "");
                settings[property] = event.target.value;
                applySettings();
            });
        });
        panel.querySelector("#stage6-open-setup")?.addEventListener("click", openSetup);
        panel.querySelector("#stage6-open-preview")?.addEventListener("click", openPreview);
        panel.querySelector("#stage6-print-now")?.addEventListener("click", printNow);
    }

    function buildSetupDialog() {
        if (setupDialog) return setupDialog;
        setupDialog = document.createElement("dialog");
        setupDialog.id = "stage6-page-setup-dialog";
        setupDialog.className = "stage6-page-setup-dialog";
        setupDialog.innerHTML = `
            <form method="dialog" class="stage6-dialog-panel">
                <header class="stage6-dialog-header"><div><h2>Параметры страницы</h2><p>Настройки применяются к предварительному просмотру и системной печати.</p></div><button class="stage6-dialog-close" value="cancel" aria-label="Закрыть">×</button></header>
                <div class="stage6-setup-grid">
                    <label>Формат бумаги<select id="stage6-setup-paper">${Object.entries(papers).map(([value, item]) => option(value, item.label)).join("")}</select></label>
                    <label>Ориентация<select id="stage6-setup-orientation">${option("portrait", "Книжная")}${option("landscape", "Альбомная")}</select></label>
                    <label>Поля<select id="stage6-setup-margins">${Object.entries(margins).map(([value, item]) => option(value, item.label)).join("")}</select></label>
                    <label>Масштаб<select id="stage6-setup-fit">${option("width", "Вписать по ширине")}${option("actual", "Фактический размер 100%")}</select></label>
                    <label>Область печати<select id="stage6-setup-scope">${option("all", "Весь журнал")}${option("selection", "Выбранные строки")}</select></label>
                    <label>Заголовок<input id="stage6-setup-title" type="text"></label>
                    <label>Нижний колонтитул<input id="stage6-setup-footer" type="text"></label>
                </div>
                <div class="stage6-checks">
                    <label><input id="stage6-setup-gridlines" type="checkbox">Печатать сетку</label>
                    <label><input id="stage6-setup-repeat" type="checkbox">Повторять шапку на каждой странице</label>
                </div>
                <div class="stage6-dialog-actions"><button value="cancel">Отмена</button><button id="stage6-save-setup" type="button">Применить</button></div>
            </form>
        `;
        document.body.appendChild(setupDialog);
        setupDialog.querySelector("#stage6-save-setup")?.addEventListener("click", saveSetup);
        setupDialog.addEventListener("click", (event) => {
            if (event.target === setupDialog) setupDialog.close("cancel");
        });
        return setupDialog;
    }

    function openSetup() {
        const target = buildSetupDialog();
        syncControls();
        if (!target.open) target.showModal();
    }

    function saveSetup() {
        settings = normalizeSettings({
            ...settings,
            paper: document.getElementById("stage6-setup-paper")?.value,
            orientation: document.getElementById("stage6-setup-orientation")?.value,
            margins: document.getElementById("stage6-setup-margins")?.value,
            fit: document.getElementById("stage6-setup-fit")?.value,
            scope: document.getElementById("stage6-setup-scope")?.value,
            title: document.getElementById("stage6-setup-title")?.value,
            footer: document.getElementById("stage6-setup-footer")?.value,
            gridlines: Boolean(document.getElementById("stage6-setup-gridlines")?.checked),
            repeatHeaders: Boolean(document.getElementById("stage6-setup-repeat")?.checked),
        });
        applySettings();
        setupDialog?.close("saved");
    }

    function plainTitle(column) {
        const definition = column.getDefinition?.() || {};
        const container = document.createElement("div");
        container.innerHTML = String(definition.title || column.getField() || "");
        return container.textContent.trim() || column.getField();
    }

    function printableColumns() {
        return table.getColumns()
            .filter((column) => column.getField?.() && column.isVisible?.() !== false)
            .map((column) => ({field: column.getField(), title: plainTitle(column)}));
    }

    function printableRows() {
        const selected = new Set(window.shiftHelperSelectedRowKeys || []);
        const rows = table.getRows("active").filter((row) => {
            const data = row.getData();
            if (data._draft) return false;
            return settings.scope !== "selection" || selected.has(data._rowKey);
        });
        if (settings.scope === "selection" && !rows.length) {
            return table.getRows("active").filter((row) => !row.getData()._draft);
        }
        return rows;
    }

    function formatPrintValue(value) {
        if (value === null || value === undefined) return "";
        if (typeof value === "number") return new Intl.NumberFormat("ru-RU").format(value);
        return String(value);
    }

    function buildPrintDocument() {
        const documentRoot = document.createElement("section");
        documentRoot.className = "stage6-print-document";
        const heading = document.createElement("header");
        heading.className = "stage6-print-heading";
        const title = document.createElement("h1");
        title.textContent = settings.title;
        const date = document.createElement("small");
        date.textContent = new Intl.DateTimeFormat("ru-RU", {dateStyle: "medium", timeStyle: "short"})
            .format(new Date());
        heading.append(title, date);

        const columns = printableColumns();
        const rows = printableRows();
        const printTable = document.createElement("table");
        printTable.className = `stage6-print-table${settings.gridlines ? "" : " stage6-print-table--no-grid"}`;
        const head = document.createElement("thead");
        const headerRow = document.createElement("tr");
        columns.forEach((column) => {
            const cell = document.createElement("th");
            cell.textContent = column.title;
            headerRow.appendChild(cell);
        });
        head.appendChild(headerRow);
        if (!settings.repeatHeaders) head.style.display = "table-row-group";
        const body = document.createElement("tbody");
        rows.forEach((row) => {
            const tr = document.createElement("tr");
            const data = row.getData();
            columns.forEach((column) => {
                const td = document.createElement("td");
                td.textContent = formatPrintValue(data[column.field]);
                tr.appendChild(td);
            });
            body.appendChild(tr);
        });
        if (!rows.length) {
            const tr = document.createElement("tr");
            const td = document.createElement("td");
            td.colSpan = Math.max(1, columns.length);
            td.textContent = "Нет записей для печати";
            tr.appendChild(td);
            body.appendChild(tr);
        }
        printTable.append(head, body);

        const footer = document.createElement("footer");
        footer.className = "stage6-print-footer";
        const footerText = document.createElement("span");
        footerText.textContent = settings.footer;
        const counter = document.createElement("span");
        counter.textContent = `Записей: ${rows.length}`;
        footer.append(footerText, counter);
        documentRoot.append(heading, printTable, footer);
        return documentRoot;
    }

    function ensurePrintSheet() {
        if (!printSheet) {
            printSheet = document.createElement("div");
            printSheet.id = "stage6-print-sheet";
            document.body.appendChild(printSheet);
        }
        printSheet.classList.toggle("stage6-fit-width", settings.fit === "width");
        printSheet.replaceChildren(buildPrintDocument());
        return printSheet;
    }

    function buildPreviewDialog() {
        if (previewDialog) return previewDialog;
        previewDialog = document.createElement("dialog");
        previewDialog.id = "stage6-preview-dialog";
        previewDialog.className = "stage6-preview-dialog";
        previewDialog.innerHTML = `
            <section class="stage6-preview-panel">
                <header class="stage6-dialog-header"><div><h2>Предварительный просмотр</h2><p>Отображается печатная HTML-таблица с повторяемой шапкой.</p></div><button class="stage6-dialog-close" id="stage6-preview-close" type="button" aria-label="Закрыть">×</button></header>
                <div class="stage6-preview-toolbar"><span class="stage6-preview-summary" id="stage6-preview-summary"></span><div class="stage6-print-actions"><button id="stage6-preview-setup" type="button">Параметры</button><button id="stage6-preview-print" type="button">Печать</button></div></div>
                <div class="stage6-preview-viewport"><div class="stage6-preview-page" id="stage6-preview-page"></div></div>
                <footer class="stage6-preview-summary">Для системного диалога печати также работает Ctrl+P — сначала открывается этот просмотр.</footer>
            </section>
        `;
        document.body.appendChild(previewDialog);
        previewDialog.querySelector("#stage6-preview-close")?.addEventListener("click", () => previewDialog.close());
        previewDialog.querySelector("#stage6-preview-setup")?.addEventListener("click", () => {
            previewDialog.close();
            openSetup();
        });
        previewDialog.querySelector("#stage6-preview-print")?.addEventListener("click", printNow);
        previewDialog.addEventListener("click", (event) => {
            if (event.target === previewDialog) previewDialog.close();
        });
        return previewDialog;
    }

    function updatePreview() {
        const target = buildPreviewDialog();
        const page = target.querySelector("#stage6-preview-page");
        const summary = target.querySelector("#stage6-preview-summary");
        if (page) {
            page.dataset.orientation = settings.orientation;
            page.replaceChildren(buildPrintDocument());
        }
        if (summary) {
            summary.textContent = `${papers[settings.paper].label} · ${
                settings.orientation === "landscape" ? "альбомная" : "книжная"
            } · поля: ${margins[settings.margins].label.toLocaleLowerCase("ru")} · ${
                settings.fit === "width" ? "по ширине" : "100%"
            }`;
        }
    }

    function openPreview() {
        updatePreview();
        if (!previewDialog.open) previewDialog.showModal();
    }

    function printNow() {
        ensurePrintSheet();
        root.dataset.printInvoked = "true";
        window.print();
    }

    window.addEventListener("keydown", (event) => {
        if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
        if (event.key.toLocaleLowerCase("ru") !== "p") return;
        event.preventDefault();
        event.stopImmediatePropagation();
        openPreview();
    }, true);

    buildLayoutTab();
    buildSetupDialog();
    buildPreviewDialog();
    applySettings({persist: false});
    ensurePrintSheet();
    window.shiftHelperAcceptanceStage6 = {
        openPreview,
        openSetup,
        printNow,
        applySettings,
        getSettings: () => ({...settings}),
        buildPrintDocument,
    };
    root.dataset.acceptanceStage6 = "ready";
})();
