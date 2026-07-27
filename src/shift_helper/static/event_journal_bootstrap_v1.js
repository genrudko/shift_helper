"use strict";

(() => {
    const migrationKey = "shift-helper-grid-persistence-migration-v4";
    if (window.localStorage.getItem(migrationKey) === "done") {
        return;
    }

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
})();
