"use strict";

(() => {
    const root = document.getElementById("event-journal");
    if (!root) {
        return;
    }

    function canvasContext(editor) {
        const style = getComputedStyle(editor);
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        context.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
        return {context, style};
    }

    function nearestCharacter(context, text, horizontalPosition) {
        if (horizontalPosition <= 0 || !text) {
            return 0;
        }
        for (let index = 0; index < text.length; index += 1) {
            const before = context.measureText(text.slice(0, index)).width;
            const after = context.measureText(text.slice(0, index + 1)).width;
            if (horizontalPosition < before + ((after - before) / 2)) {
                return index;
            }
        }
        return text.length;
    }

    function wrappedSegments(context, value, availableWidth) {
        const segments = [];
        let start = 0;
        let text = "";
        for (let index = 0; index < value.length; index += 1) {
            const character = value[index];
            if (character === "\n") {
                segments.push({start, text});
                start = index + 1;
                text = "";
                continue;
            }
            const candidate = text + character;
            if (
                text
                && availableWidth > 0
                && context.measureText(candidate).width > availableWidth
            ) {
                segments.push({start, text});
                start = index;
                text = character;
            } else {
                text = candidate;
            }
        }
        segments.push({start, text});
        return segments;
    }

    function caretOffset(editor, clientX, clientY) {
        const {context, style} = canvasContext(editor);
        const rect = editor.getBoundingClientRect();
        const paddingLeft = Number.parseFloat(style.paddingLeft) || 0;
        const paddingRight = Number.parseFloat(style.paddingRight) || 0;
        const paddingTop = Number.parseFloat(style.paddingTop) || 0;
        const fontSize = Number.parseFloat(style.fontSize) || 13;
        const parsedLineHeight = Number.parseFloat(style.lineHeight);
        const lineHeight = Number.isFinite(parsedLineHeight)
            ? parsedLineHeight
            : fontSize * 1.35;
        const x = clientX - rect.left - paddingLeft + editor.scrollLeft;
        const y = clientY - rect.top - paddingTop + editor.scrollTop;

        if (editor instanceof HTMLInputElement) {
            return nearestCharacter(context, editor.value, x);
        }

        const availableWidth = Math.max(1, editor.clientWidth - paddingLeft - paddingRight);
        const segments = wrappedSegments(context, editor.value, availableWidth);
        const lineIndex = Math.min(
            segments.length - 1,
            Math.max(0, Math.floor(y / Math.max(1, lineHeight))),
        );
        const segment = segments[lineIndex];
        return segment.start + nearestCharacter(context, segment.text, x);
    }

    function bind(editor) {
        if (editor.dataset.preciseCaretBound === "true") {
            return;
        }
        editor.dataset.preciseCaretBound = "true";
        let pointerStart = null;

        editor.addEventListener("pointerdown", (event) => {
            if (event.button !== 0) {
                return;
            }
            pointerStart = {x: event.clientX, y: event.clientY};
            event.stopPropagation();
        });
        editor.addEventListener("pointermove", (event) => {
            event.stopPropagation();
        });
        editor.addEventListener("pointerup", (event) => {
            event.stopPropagation();
            if (!pointerStart) {
                return;
            }
            const movement = Math.hypot(
                event.clientX - pointerStart.x,
                event.clientY - pointerStart.y,
            );
            pointerStart = null;
            if (movement > 4) {
                return;
            }
            const offset = caretOffset(editor, event.clientX, event.clientY);
            window.requestAnimationFrame(() => {
                if (!editor.isConnected) {
                    return;
                }
                editor.focus({preventScroll: true});
                editor.setSelectionRange(offset, offset);
            });
        });
        editor.addEventListener("click", (event) => {
            event.stopPropagation();
        });
    }

    function bindEditors() {
        root.querySelectorAll(".journal-stable-editor").forEach(bind);
    }

    new MutationObserver(bindEditors).observe(root, {childList: true, subtree: true});
    bindEditors();
})();

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const select = document.getElementById("journal-frozen-through");

    if (
        !root
        || !table
        || !select
        || root.dataset.frozenColumnsController === "ready"
        || typeof table.getColumnDefinitions !== "function"
        || typeof table.setColumns !== "function"
    ) {
        return;
    }

    const preferenceKey = "shift-helper-ui-preferences-v1";
    const defaultBoundary = "asset_label";
    let applying = false;
    let queuedBoundary = null;
    root.dataset.frozenColumnsController = "ready";

    function readPreferences() {
        try {
            return JSON.parse(window.localStorage.getItem(preferenceKey) || "{}");
        } catch (_error) {
            return {};
        }
    }

    function saveBoundary(boundary) {
        const preferences = readPreferences();
        preferences.frozenThrough = boundary;
        window.localStorage.setItem(preferenceKey, JSON.stringify(preferences));
    }

    function expectedFields(boundary, fields) {
        if (boundary === "none") {
            return new Set();
        }
        const index = fields.indexOf(boundary);
        if (index < 0) {
            const fallbackIndex = fields.indexOf(defaultBoundary);
            return new Set(fields.slice(0, fallbackIndex + 1));
        }
        if (index === fields.length - 1) {
            return new Set(fields.slice(0, -1));
        }
        return new Set(fields.slice(0, index + 1));
    }

    function clearTransientState() {
        window.shiftHelperClearTransientGridState?.();
        for (const range of table.getRanges?.() || []) {
            try {
                range.remove();
            } catch (_error) {
                // A stale selection must not block a view-setting change.
            }
        }
        document.querySelectorAll(".journal-fill-handle").forEach((handle) => {
            handle.hidden = true;
        });
    }

    async function applyBoundary(boundary) {
        if (applying) {
            queuedBoundary = boundary;
            return;
        }
        applying = true;
        root.dataset.frozenColumnsApplying = boundary;
        delete root.dataset.frozenColumnsApplied;
        clearTransientState();
        try {
            const definitions = table.getColumnDefinitions();
            const fields = definitions.map((definition) => definition.field).filter(Boolean);
            const expected = expectedFields(boundary, fields);
            const nextDefinitions = definitions.map((definition) => ({
                ...definition,
                frozen: expected.has(definition.field),
            }));

            await Promise.resolve(table.setColumns(nextDefinitions));
            saveBoundary(boundary);
            table.redraw(true);
            root.dataset.frozenColumnsApplied = boundary;
        } catch (error) {
            root.dataset.frozenColumnsError = String(error);
            throw error;
        } finally {
            delete root.dataset.frozenColumnsApplying;
            applying = false;
            if (queuedBoundary !== null) {
                const next = queuedBoundary;
                queuedBoundary = null;
                await applyBoundary(next);
            }
        }
    }

    select.addEventListener("change", (event) => {
        event.stopImmediatePropagation();
        void applyBoundary(event.target.value);
    }, true);

    document.getElementById("reset-view-settings")?.addEventListener("click", () => {
        window.setTimeout(() => {
            select.value = defaultBoundary;
            void applyBoundary(defaultBoundary);
        }, 0);
    }, true);

    function applyStoredBoundary() {
        const boundary = readPreferences().frozenThrough || defaultBoundary;
        select.value = boundary;
        void applyBoundary(boundary);
    }

    table.on("tableBuilt", applyStoredBoundary);
    if (root.querySelector(".tabulator-tableholder")) {
        window.requestAnimationFrame(applyStoredBoundary);
    }
})();
