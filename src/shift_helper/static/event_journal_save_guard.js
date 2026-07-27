"use strict";

(() => {
    const table = window.shiftHelperEventGrid;
    const originalFetch = window.fetch.bind(window);

    if (!table) {
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
    const localDerivedFields = ["downtime", "downtime_losses_rub", "status"];

    function requestBody(options) {
        if (!options?.body || typeof options.body !== "string") {
            return null;
        }
        try {
            const parsed = JSON.parse(options.body);
            return parsed && typeof parsed === "object" ? parsed : null;
        } catch (_error) {
            return null;
        }
    }

    function requestEventId(url) {
        const match = /\/events\/(\d+)\/row(?:\?|$)/.exec(String(url));
        return match ? Number(match[1]) : null;
    }

    function valuesMatch(data, payload) {
        return editableFields.every(
            (field) => String(data[field] ?? "") === String(payload[field] ?? ""),
        );
    }

    function findRequestRow(url, options, payload) {
        const eventId = requestEventId(url);
        if (eventId !== null) {
            return table.getRows().find((row) => Number(row.getData().id) === eventId) || null;
        }
        if (String(url).endsWith("/events/rows") && options?.method === "POST") {
            return table.getRows().find((row) => {
                const data = row.getData();
                return data._draft && valuesMatch(data, payload);
            }) || null;
        }
        return null;
    }

    function isJournalSave(url, options) {
        const method = String(options?.method || "GET").toUpperCase();
        return (
            (method === "PATCH" && /\/events\/\d+\/row(?:\?|$)/.test(String(url)))
            || (method === "POST" && String(url).endsWith("/events/rows"))
        );
    }

    function cloneResponse(response, payload) {
        return new Response(JSON.stringify(payload), {
            status: response.status,
            statusText: response.statusText,
            headers: response.headers,
        });
    }

    window.fetch = async (url, options = {}) => {
        if (!isJournalSave(url, options)) {
            return originalFetch(url, options);
        }

        const payload = requestBody(options);
        const row = payload ? findRequestRow(url, options, payload) : null;
        const response = await originalFetch(url, options);
        if (!response.ok || !payload || !row) {
            return response;
        }

        const current = row.getData();
        if (valuesMatch(current, payload)) {
            return response;
        }

        let responsePayload;
        try {
            responsePayload = await response.clone().json();
        } catch (_error) {
            return response;
        }
        if (!responsePayload?.ok || !responsePayload.row) {
            return response;
        }

        const mergedRow = {...responsePayload.row};
        for (const field of [...editableFields, ...localDerivedFields]) {
            mergedRow[field] = current[field] ?? "";
        }
        responsePayload.row = mergedRow;
        return cloneResponse(response, responsePayload);
    };
})();
