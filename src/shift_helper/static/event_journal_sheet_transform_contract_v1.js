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
    if (
        !root
        || !layer
        || typeof controller?.apply !== "function"
        || root.dataset.sheetTransformContract === "ready"
    ) return;

    const clampZoom = (value) => Math.min(400, Math.max(10, Number(value) || 100));
    const originalApply = controller.apply.bind(controller);

    function render(rawValue) {
        const value = clampZoom(rawValue ?? root.dataset.sheetZoom);
        const scale = value / 100;
        layer.style.removeProperty("zoom");
        layer.style.transformOrigin = "top left";
        layer.style.transform = `scale(${scale})`;
        layer.style.width = `${100 / scale}%`;
        layer.style.height = `${100 / scale}%`;
        root.dataset.sheetTransformZoom = String(value);
    }

    controller.apply = (rawValue, shouldPersist = true) => {
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

    render();
    root.dataset.sheetTransformContract = "ready";
})();
