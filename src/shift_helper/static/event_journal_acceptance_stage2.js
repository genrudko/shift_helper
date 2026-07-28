"use strict";

/*
 * Operator acceptance stage 2.
 * Preserves complete cell text formatting across alignment reformatting and
 * gives all color palettes a predictable outside-click / Escape lifecycle.
 */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table || root.dataset.acceptanceStage2 === "ready") return;

    const textStyleKey = "shift-helper-event-cell-text-style-v1";
    let applyFrame = 0;

    function loadTextStyles() {
        try {
            return JSON.parse(localStorage.getItem(textStyleKey) || "{}");
        } catch (_error) {
            return {};
        }
    }

    function applyTextStyle(cell, store) {
        const element = cell?.getElement?.();
        const value = element?.querySelector(".journal-cell-value");
        if (!element || !value) return;
        const rowKey = cell.getRow().getData()._rowKey;
        const style = store[rowKey]?.[cell.getField()] || {};

        value.style.fontFamily = style.fontFamily || "";
        value.style.fontSize = style.fontSize ? `${style.fontSize}px` : "";
        value.style.fontWeight = style.bold ? "700" : "";
        value.style.fontStyle = style.italic ? "italic" : "";
        value.style.textDecoration = style.underline ? "underline" : "";
        if (style.color) value.style.color = style.color;
        value.style.whiteSpace = style.wrap ? "pre-wrap" : "";
        value.style.overflowWrap = style.wrap ? "anywhere" : "";
        const rotation = Number(style.rotation || 0);
        value.style.transform = rotation ? `rotate(${rotation}deg)` : "";
        value.style.transformOrigin = "center";
    }

    function applyAllTextStyles() {
        const store = loadTextStyles();
        table.getRows("active").forEach((row) => {
            row.getCells().forEach((cell) => applyTextStyle(cell, store));
        });
    }

    function scheduleTextRestore() {
        cancelAnimationFrame(applyFrame);
        applyFrame = requestAnimationFrame(() => {
            requestAnimationFrame(applyAllTextStyles);
        });
    }

    function palettes() {
        return [...document.querySelectorAll(".operator-color-palette")];
    }

    function closePalettes() {
        palettes().forEach((palette) => palette.remove());
        document.querySelectorAll("[aria-expanded='true'].operator-fill-arrow").forEach((button) => {
            button.setAttribute("aria-expanded", "false");
        });
    }

    function paletteControlFor(target) {
        if (!(target instanceof Element)) return null;
        return target.closest(
            ".operator-color-palette, #operator-fill-control, #operator-text-color-control",
        );
    }

    window.addEventListener("pointerdown", (event) => {
        if (!palettes().length || paletteControlFor(event.target)) return;
        closePalettes();
    }, true);

    window.addEventListener("keydown", (event) => {
        if (event.key !== "Escape" || !palettes().length) return;
        closePalettes();
    }, true);

    new MutationObserver((records) => {
        const added = records.flatMap((record) => [...record.addedNodes])
            .filter((node) => node instanceof Element)
            .flatMap((node) => [
                ...(node.matches?.(".operator-color-palette") ? [node] : []),
                ...node.querySelectorAll?.(".operator-color-palette") || [],
            ]);
        if (!added.length) return;
        const newest = added.at(-1);
        palettes().forEach((palette) => {
            if (palette !== newest) palette.remove();
        });
        const owner = newest.dataset.owner === "text"
            ? document.querySelector("#operator-text-color-control .operator-fill-arrow")
            : document.querySelector("#operator-fill-control .operator-fill-arrow");
        owner?.setAttribute("aria-expanded", "true");
    }).observe(document.body, {childList: true, subtree: true});

    document.querySelectorAll("[data-align-horizontal], [data-align-vertical]").forEach((button) => {
        button.addEventListener("click", scheduleTextRestore);
    });

    table.on("renderComplete", scheduleTextRestore);
    table.on("rowUpdated", scheduleTextRestore);
    new MutationObserver(scheduleTextRestore).observe(root, {childList: true, subtree: true});

    window.shiftHelperAcceptanceStage2 = {
        applyAllTextStyles,
        closePalettes,
    };
    scheduleTextRestore();
    root.dataset.acceptanceStage2 = "ready";
})();
