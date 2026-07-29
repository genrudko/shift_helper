"use strict";

/* Include entered draft rows in preview/print while ignoring blank placeholders. */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table || root.dataset.printDraftContract === "ready") return;

    const printableFields = [
        "start_date", "start_time", "asset_label", "description", "reason",
        "actions", "performer", "end_date", "end_time", "downtime", "author",
        "downtime_losses_rub",
    ];
    let repairFrame = 0;

    function meaningfulRows() {
        const selected = new Set(window.shiftHelperSelectedRowKeys || []);
        const scope = root.dataset.printScope || "all";
        const all = table.getRows("active").filter((row) => {
            const data = row.getData();
            if (!data._draft) return true;
            return printableFields.some((field) => {
                const value = data[field];
                return value !== null && value !== undefined && String(value).trim() !== "";
            });
        });
        if (scope !== "selection") return all;
        const chosen = all.filter((row) => selected.has(row.getData()._rowKey));
        return chosen.length ? chosen : all;
    }

    function printableColumns() {
        return table.getColumns()
            .filter((column) => column.getField?.() && column.isVisible?.() !== false)
            .map((column) => column.getField());
    }

    function formatValue(value) {
        if (value === null || value === undefined) return "";
        if (typeof value === "number") return new Intl.NumberFormat("ru-RU").format(value);
        return String(value);
    }

    function rowSignature(rows, fields) {
        return JSON.stringify(rows.map((row) => {
            const data = row.getData();
            return [data._rowKey, ...fields.map((field) => data[field] ?? "")];
        }));
    }

    function rebuildDocument(documentRoot) {
        if (!(documentRoot instanceof Element)) return;
        const body = documentRoot.querySelector("tbody");
        const counter = documentRoot.querySelector(".stage6-print-footer span:last-child");
        if (!body || !counter) return;

        const rows = meaningfulRows();
        const fields = printableColumns();
        const signature = rowSignature(rows, fields);
        if (documentRoot.dataset.printRowsSignature === signature) return;

        const fragment = document.createDocumentFragment();
        rows.forEach((row) => {
            const tr = document.createElement("tr");
            const data = row.getData();
            fields.forEach((field) => {
                const td = document.createElement("td");
                td.textContent = formatValue(data[field]);
                tr.appendChild(td);
            });
            fragment.appendChild(tr);
        });
        if (!rows.length) {
            const tr = document.createElement("tr");
            const td = document.createElement("td");
            td.colSpan = Math.max(1, fields.length);
            td.textContent = "Нет записей для печати";
            tr.appendChild(td);
            fragment.appendChild(tr);
        }
        body.replaceChildren(fragment);
        counter.textContent = `Записей: ${rows.length}`;
        documentRoot.dataset.printRowsSignature = signature;
    }

    function repairDocuments() {
        cancelAnimationFrame(repairFrame);
        repairFrame = 0;
        document.querySelectorAll(".stage6-print-document").forEach(rebuildDocument);
        root.dataset.printDraftRows = String(meaningfulRows().length);
    }

    function scheduleRepair() {
        cancelAnimationFrame(repairFrame);
        repairFrame = requestAnimationFrame(repairDocuments);
    }

    function install() {
        if (root.dataset.acceptanceStage6 !== "ready" || !window.shiftHelperAcceptanceStage6) {
            requestAnimationFrame(install);
            return;
        }
        const api = window.shiftHelperAcceptanceStage6;
        const originalOpenPreview = api.openPreview.bind(api);
        api.openPreview = (...args) => {
            const result = originalOpenPreview(...args);
            scheduleRepair();
            return result;
        };
        const originalBuild = api.buildPrintDocument.bind(api);
        api.buildPrintDocument = (...args) => {
            const documentRoot = originalBuild(...args);
            rebuildDocument(documentRoot);
            return documentRoot;
        };
        api.meaningfulRows = meaningfulRows;
        api.repairPrintDocuments = repairDocuments;

        const originalPrint = window.print.bind(window);
        window.print = (...args) => {
            repairDocuments();
            return originalPrint(...args);
        };
        document.addEventListener("click", (event) => {
            if (!(event.target instanceof Element)) return;
            if (event.target.closest("#stage6-open-preview, #stage6-preview-print, #stage6-print-now")) {
                scheduleRepair();
            }
        }, true);
        const observer = new MutationObserver(scheduleRepair);
        observer.observe(document.body, {childList: true, subtree: true});
        table.on("cellEdited", scheduleRepair);
        table.on("rowAdded", scheduleRepair);
        table.on("rowDeleted", scheduleRepair);
        table.on("dataFiltered", scheduleRepair);

        root.dataset.printDraftContract = "ready";
        scheduleRepair();
    }

    install();
})();
