"use strict";

/* Remove stale sticky offsets when Tabulator recycles virtualized row DOM nodes. */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const frozen = window.shiftHelperFrozenColumns;
    if (!root || !table || !frozen || root.dataset.stage3Virtualization === "ready") return;

    let frame = 0;

    function fieldOf(element) {
        return element.getAttribute("tabulator-field") || element.dataset.field || "";
    }

    function clearStaleSticky(element) {
        element.classList.remove("operator-stable-frozen");
        element.style.removeProperty("left");
        element.style.removeProperty("right");
        element.style.removeProperty("z-index");
        element.style.removeProperty("box-shadow");
        if (element.classList.contains("tabulator-cell")) {
            element.style.position = "relative";
        } else {
            element.style.removeProperty("position");
        }
    }

    function sanitize() {
        frame = 0;
        const frozenFields = new Set(frozen.getFields?.() || []);
        root.querySelectorAll(
            ".tabulator-col[tabulator-field], .tabulator-col[data-field], "
            + ".tabulator-cell[tabulator-field], .tabulator-cell[data-field]",
        ).forEach((element) => {
            if (!frozenFields.has(fieldOf(element))) clearStaleSticky(element);
        });
        frozen.reapply?.();
        root.dataset.stage3VirtualizationSanitized = "true";
    }

    function schedule() {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(sanitize);
    }

    table.on("renderComplete", schedule);
    table.on("columnResized", schedule);
    root.querySelector(".tabulator-tableholder")?.addEventListener("scroll", schedule, {passive: true});
    new MutationObserver(schedule).observe(root, {childList: true, subtree: true});
    window.addEventListener("resize", schedule);

    root.dataset.stage3Virtualization = "ready";
    schedule();
})();
