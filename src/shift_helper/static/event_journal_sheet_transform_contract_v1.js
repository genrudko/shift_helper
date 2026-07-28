"use strict";

/*
 * Sheet rendering contract.
 * Bootstrap owns zoom state, controls and persistence; this module owns only
 * the visual mapping of that state onto the isolated sheet layer.
 */
(() => {
    const root = document.getElementById("event-journal");
    const layer = document.getElementById("journal-sheet-layer");
    const controller = window.shiftHelperZoom;
    const table = window.shiftHelperEventGrid;
    if (
        !root
        || !layer
        || !table
        || typeof controller?.apply !== "function"
        || root.dataset.sheetTransformContract === "ready"
    ) return;

    const clampZoom = (value) => Math.min(400, Math.max(10, Number(value) || 100));
    const originalApply = controller.apply.bind(controller);
    let redrawFrame = 0;
    let pendingAnchor = null;

    function currentScale() {
        return clampZoom(root.dataset.sheetTransformZoom || root.dataset.sheetZoom) / 100;
    }

    function captureAnchor() {
        const holder = root.querySelector(".tabulator-tableholder");
        const holderRect = holder?.getBoundingClientRect();
        const rows = table.getRows?.("active") || [];
        if (!holder || !holderRect || !rows.length) return null;

        const visible = rows.map((row) => {
            const element = row.getElement?.();
            const rect = element?.getBoundingClientRect();
            return {row, rect};
        }).filter(({rect}) => (
            rect
            && rect.bottom > holderRect.top + 1
            && rect.top < holderRect.bottom - 1
        ));
        const candidate = visible.find(({row}) => !row.getData()?._draft)
            || visible[0]
            || rows.find((row) => !row.getData()?._draft)
            || rows[0];
        const key = candidate?.row?.getData()?._rowKey ?? candidate?.getData?.()?._rowKey;
        if (!key) return null;

        const rect = candidate.rect || candidate.getElement?.()?.getBoundingClientRect?.();
        return {
            key,
            offset: rect ? (rect.top - holderRect.top) / currentScale() : 0,
        };
    }

    function restoreFallback(scrollTop, scrollLeft) {
        const holder = root.querySelector(".tabulator-tableholder");
        if (!holder) return;
        holder.scrollTop = Math.min(
            scrollTop,
            Math.max(0, holder.scrollHeight - holder.clientHeight),
        );
        holder.scrollLeft = Math.min(
            scrollLeft,
            Math.max(0, holder.scrollWidth - holder.clientWidth),
        );
    }

    function scheduleGeometry(value) {
        cancelAnimationFrame(redrawFrame);
        redrawFrame = requestAnimationFrame(() => {
            const holder = root.querySelector(".tabulator-tableholder");
            const scrollTop = holder?.scrollTop || 0;
            const scrollLeft = holder?.scrollLeft || 0;
            const anchor = pendingAnchor || captureAnchor();
            pendingAnchor = null;
            table.redraw?.(true);

            const row = anchor?.key ? table.getRow?.(anchor.key) : null;
            let restoration = null;
            try {
                restoration = row && typeof table.scrollToRow === "function"
                    ? table.scrollToRow(row, "top", false)
                    : null;
            } catch (_error) {
                restoration = null;
            }
            Promise.resolve(restoration).catch(() => null).finally(() => {
                requestAnimationFrame(() => {
                    const refreshed = root.querySelector(".tabulator-tableholder");
                    if (refreshed && row && anchor) {
                        const rowHeight = row.getElement?.()?.offsetHeight || 34;
                        const maximumOffset = Math.max(0, refreshed.clientHeight - rowHeight);
                        const offset = Math.min(maximumOffset, Math.max(0, anchor.offset));
                        refreshed.scrollTop = Math.max(0, refreshed.scrollTop + offset);
                        refreshed.scrollLeft = Math.min(
                            scrollLeft,
                            Math.max(0, refreshed.scrollWidth - refreshed.clientWidth),
                        );
                    } else {
                        restoreFallback(scrollTop, scrollLeft);
                    }
                    root.dataset.sheetTransformGeometry = String(value);
                    root.dataset.sheetTransformAnchor = anchor?.key || "fallback";
                });
            });
        });
    }

    function render(rawValue) {
        const value = clampZoom(rawValue ?? root.dataset.sheetZoom);
        const scale = value / 100;
        layer.style.removeProperty("zoom");
        layer.style.transformOrigin = "top left";
        layer.style.transform = `scale(${scale})`;
        layer.style.width = `${100 / scale}%`;
        layer.style.height = `${100 / scale}%`;
        root.dataset.sheetTransformZoom = String(value);
        scheduleGeometry(value);
    }

    controller.apply = (rawValue, shouldPersist = true) => {
        pendingAnchor = captureAnchor();
        const result = originalApply(rawValue, shouldPersist);
        render(rawValue);
        return result;
    };

    new MutationObserver(() => render()).observe(layer, {
        attributes: true,
        attributeFilter: ["data-sheet-zoom"],
    });
    window.addEventListener("shifthelper:zoom", (event) => {
        render(event.detail?.value);
    }, true);

    pendingAnchor = captureAnchor();
    render();
    root.dataset.sheetTransformContract = "ready";
})();
