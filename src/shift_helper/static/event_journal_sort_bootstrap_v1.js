"use strict";

(() => {
    const TabulatorClass = window.Tabulator;
    if (!TabulatorClass || window.shiftHelperDraftSortBootstrap === "ready") {
        return;
    }

    const dateFields = new Set(["start_date", "end_date"]);
    const timeFields = new Set(["start_time", "end_time"]);
    const collator = new Intl.Collator("ru", {numeric: true, sensitivity: "base"});

    const parseDate = (value) => {
        const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(String(value || "").trim());
        return match ? new Date(+match[3], +match[2] - 1, +match[1]).getTime() : null;
    };
    const parseTime = (value) => {
        const match = /^(\d{1,2}):(\d{2})$/.exec(String(value || "").trim());
        return match ? (+match[1] * 60) + +match[2] : null;
    };
    const compare = (field, leftValue, rightValue, direction) => {
        const leftBlank = String(leftValue ?? "").trim() === "";
        const rightBlank = String(rightValue ?? "").trim() === "";
        if (leftBlank !== rightBlank) {
            const result = leftBlank ? 1 : -1;
            return direction === "desc" ? -result : result;
        }
        if (dateFields.has(field)) {
            const left = parseDate(leftValue);
            const right = parseDate(rightValue);
            if (left !== null && right !== null) {
                return left - right;
            }
        }
        if (timeFields.has(field)) {
            const left = parseTime(leftValue);
            const right = parseTime(rightValue);
            if (left !== null && right !== null) {
                return left - right;
            }
        }
        const left = Number(String(leftValue ?? "").replace(/\s/g, "").replace(",", "."));
        const right = Number(String(rightValue ?? "").replace(/\s/g, "").replace(",", "."));
        if (Number.isFinite(left) && Number.isFinite(right)) {
            return left - right;
        }
        return collator.compare(String(leftValue ?? ""), String(rightValue ?? ""));
    };

    TabulatorClass.extendModule("sort", "sorters", {
        shiftHelperDraft(left, right, leftRow, rightRow, _column, direction, params) {
            const leftData = leftRow.getData();
            const rightData = rightRow.getData();
            const leftDraft = Boolean(leftData._draft);
            const rightDraft = Boolean(rightData._draft);
            if (leftDraft !== rightDraft) {
                const result = leftDraft ? 1 : -1;
                return direction === "desc" ? -result : result;
            }
            if (leftDraft) {
                return 0;
            }
            const result = compare(params.field, left, right, direction);
            return result || (Number(leftData.id || 0) - Number(rightData.id || 0));
        },
    });

    function ShiftHelperTabulator(element, options = {}) {
        const target = typeof element === "string" ? document.querySelector(element) : element;
        if (target?.id === "event-journal") {
            options.headerSortClickElement = "icon";
            options.columns = (options.columns || []).map((column) => column.field ? {
                ...column,
                sorter: "shiftHelperDraft",
                sorterParams: {field: column.field},
            } : column);
        }
        return new TabulatorClass(element, options);
    }

    Object.setPrototypeOf(ShiftHelperTabulator, TabulatorClass);
    ShiftHelperTabulator.prototype = TabulatorClass.prototype;
    window.Tabulator = ShiftHelperTabulator;
    window.shiftHelperDraftSortBootstrap = "ready";
})();
