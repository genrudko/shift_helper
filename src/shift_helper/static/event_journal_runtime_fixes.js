"use strict";

(() => {
    const table = window.shiftHelperEventGrid;
    if (!table) {
        return;
    }

    function pad(value) {
        return String(value).padStart(2, "0");
    }

    function currentDate(now = new Date()) {
        return `${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${now.getFullYear()}`;
    }

    function currentTime(now = new Date()) {
        return `${pad(now.getHours())}:${pad(now.getMinutes())}`;
    }

    function hasOperationalInput(data) {
        return [
            "asset_label",
            "description",
            "reason",
            "actions",
            "performer",
            "end_date",
            "end_time",
            "author",
        ].some((field) => String(data[field] ?? "").trim() !== "");
    }

    table.on("cellEdited", (cell) => {
        const row = cell.getRow();
        const data = row.getData();
        if (!data._draft || !hasOperationalInput(data)) {
            return;
        }
        const timestamp = {};
        if (!String(data.start_date ?? "").trim()) {
            timestamp.start_date = currentDate();
        }
        if (!String(data.start_time ?? "").trim()) {
            timestamp.start_time = currentTime();
        }
        if (Object.keys(timestamp).length) {
            void row.update(timestamp);
        }
    });
})();
