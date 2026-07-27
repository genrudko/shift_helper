"use strict";

(() => {
    const migrationKey = "shift-helper-grid-persistence-migration-v4";
    if (window.localStorage.getItem(migrationKey) !== "done") {
        const legacyFragments = [
            "shift-helper-event-grid-v3",
            "tabulator-shift-helper-event-grid-v3",
        ];
        const keysToRemove = [];
        for (let index = 0; index < window.localStorage.length; index += 1) {
            const key = window.localStorage.key(index);
            if (key && legacyFragments.some((fragment) => key.includes(fragment))) {
                keysToRemove.push(key);
            }
        }
        keysToRemove.forEach((key) => window.localStorage.removeItem(key));
        window.localStorage.setItem(migrationKey, "done");
    }
})();

(() => {
    const stylesheetId = "event-journal-operator-repair-v1-css";
    if (!document.getElementById(stylesheetId)) {
        const stylesheet = document.createElement("link");
        stylesheet.id = stylesheetId;
        stylesheet.rel = "stylesheet";
        stylesheet.href = "/static/event_journal_operator_repair_v1.css";
        document.head.appendChild(stylesheet);
    }

    const loadRepair = () => {
        if (document.getElementById("event-journal-operator-repair-v1-js")) {
            return;
        }
        const script = document.createElement("script");
        script.id = "event-journal-operator-repair-v1-js";
        script.src = "/static/event_journal_operator_repair_v1.js";
        script.defer = true;
        document.body.appendChild(script);
    };

    if (document.readyState === "complete") {
        window.setTimeout(loadRepair, 0);
    } else {
        window.addEventListener("load", loadRepair, {once: true});
    }
})();
