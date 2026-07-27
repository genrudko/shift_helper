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
