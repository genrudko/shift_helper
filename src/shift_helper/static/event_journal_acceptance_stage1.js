"use strict";

/*
 * Operator acceptance stage 1.
 * Owns the Excel-like zoom slider and deterministic row-header selection.
 */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    if (!root || !table || root.dataset.acceptanceStage1 === "ready") return;

    const preferenceKey = "shift-helper-ui-preferences-v1";
    const zoomKey = "shift-helper-operator-zoom-v1";
    const controls = ["journal-zoom", "ribbon-zoom"];
    const baseMetrics = new Map();
    const sliders = new Map();
    let currentZoom = 100;
    let applyingZoom = false;
    let pendingZoom = null;
    let drag = null;
    let syntheticRowEvent = false;

    function clampZoom(raw) {
        return Math.min(400, Math.max(10, Number(raw) || 100));
    }

    function roundZoom(raw) {
        return clampZoom(Math.round(clampZoom(raw) / 5) * 5);
    }

    function loadPreferences() {
        try {
            return JSON.parse(localStorage.getItem(preferenceKey) || "{}");
        } catch (_error) {
            return {};
        }
    }

    function persistZoom(value) {
        const preferences = loadPreferences();
        preferences.zoom = value;
        try {
            localStorage.setItem(preferenceKey, JSON.stringify(preferences));
            localStorage.setItem(zoomKey, JSON.stringify(value));
        } catch (_error) {
            // Presentation settings must never block journal work.
        }
    }

    function zoomToPosition(value) {
        const zoom = clampZoom(value);
        if (zoom <= 100) return ((zoom - 10) / 90) * 50;
        return 50 + (((zoom - 100) / 300) * 50);
    }

    function positionToZoom(position) {
        const normalized = Math.min(100, Math.max(0, Number(position) || 0));
        if (normalized <= 50) return roundZoom(10 + ((normalized / 50) * 90));
        return roundZoom(100 + (((normalized - 50) / 50) * 300));
    }

    function addStyles() {
        if (document.getElementById("acceptance-stage1-style")) return;
        const style = document.createElement("style");
        style.id = "acceptance-stage1-style";
        style.textContent = `
            .acceptance-zoom-native { display: none !important; }
            .acceptance-zoom-slider {
                --acceptance-zoom-position: 50%;
                position: relative;
                box-sizing: border-box;
                width: min(220px, 32vw);
                min-width: 132px;
                height: 22px;
                cursor: pointer;
                touch-action: none;
                outline: none;
            }
            .journal-settings-grid .acceptance-zoom-slider {
                width: 100%;
                min-width: 180px;
            }
            .acceptance-zoom-track,
            .acceptance-zoom-progress {
                position: absolute;
                top: 50%;
                left: 0;
                height: 4px;
                border-radius: 999px;
                transform: translateY(-50%);
            }
            .acceptance-zoom-track {
                width: 100%;
                background: color-mix(in srgb, currentColor 22%, transparent);
            }
            .acceptance-zoom-progress {
                width: var(--acceptance-zoom-position);
                background: var(--accent, #2f74d0);
            }
            .acceptance-zoom-thumb {
                position: absolute;
                top: 50%;
                left: var(--acceptance-zoom-position);
                width: 13px;
                height: 13px;
                border: 2px solid var(--accent, #2f74d0);
                border-radius: 50%;
                background: var(--surface, #fff);
                transform: translate(-50%, -50%);
                box-shadow: 0 1px 3px rgb(0 0 0 / 28%);
            }
            .acceptance-zoom-slider:focus-visible .acceptance-zoom-thumb {
                outline: 2px solid color-mix(in srgb, var(--accent, #2f74d0) 45%, transparent);
                outline-offset: 3px;
            }
        `;
        document.head.appendChild(style);
    }

    function captureBaseMetrics() {
        const renderedZoom = clampZoom(root.dataset.sheetZoom || currentZoom);
        const scale = renderedZoom / 100;
        table.getColumns().forEach((column) => {
            const field = column.getField();
            if (!field || baseMetrics.has(field)) return;
            const definition = column.getDefinition?.() || {};
            const width = Number(column.getWidth()) || Number(definition.width) || 100;
            const minWidth = Number(definition.minWidth) || Math.min(width, 40);
            baseMetrics.set(field, {
                width: width / Math.max(0.1, scale),
                minWidth: minWidth / Math.max(0.1, scale),
            });
        });
    }

    function syncZoomUi(value) {
        const position = zoomToPosition(value);
        controls.forEach((id) => {
            const native = document.getElementById(id);
            if (native) native.value = String(value);
            const slider = sliders.get(id);
            if (!slider) return;
            slider.style.setProperty("--acceptance-zoom-position", `${position}%`);
            slider.dataset.zoom = String(value);
            slider.dataset.position = String(position);
            slider.setAttribute("aria-valuenow", String(value));
            slider.setAttribute("aria-valuetext", `${value}%`);
        });
        document.getElementById("ribbon-zoom-value")?.replaceChildren(`${value}%`);
        document.getElementById("journal-zoom-value")?.replaceChildren(`${value}%`);
    }

    function finishZoom(holder, scrollTop, scrollLeft, value) {
        requestAnimationFrame(() => {
            if (holder) {
                holder.scrollTop = scrollTop;
                holder.scrollLeft = scrollLeft;
            }
            currentZoom = value;
            syncZoomUi(value);
            root.dataset.sheetZoom = String(value);
            delete root.dataset.zoomApplying;
            applyingZoom = false;
            if (pendingZoom !== null && pendingZoom !== value) {
                const next = pendingZoom;
                pendingZoom = null;
                applyZoom(next);
            } else {
                pendingZoom = null;
            }
        });
    }

    function applyZoom(raw, persist = true) {
        const value = roundZoom(raw);
        if (applyingZoom) {
            pendingZoom = value;
            if (persist) persistZoom(value);
            return;
        }
        applyingZoom = true;
        root.dataset.zoomApplying = "true";
        if (persist) persistZoom(value);
        captureBaseMetrics();

        const scale = value / 100;
        const holder = root.querySelector(".tabulator-tableholder");
        const scrollTop = holder?.scrollTop || 0;
        const scrollLeft = holder?.scrollLeft || 0;
        const preferences = loadPreferences();
        const fontSize = Number(preferences.fontSize) || 13;

        root.style.removeProperty("zoom");
        root.style.removeProperty("width");
        root.style.removeProperty("height");
        document.body.style.removeProperty("zoom");
        document.body.style.removeProperty("width");
        document.documentElement.style.setProperty("--ui-scale-factor", "1");
        document.documentElement.style.setProperty(
            "--journal-font-size",
            `${Math.max(6, fontSize * scale)}px`,
        );
        document.documentElement.style.setProperty(
            "--journal-row-height",
            `${Math.max(12, Math.round(34 * scale))}px`,
        );
        document.documentElement.style.setProperty(
            "--journal-control-height",
            `${Math.max(12, Math.round(30 * scale))}px`,
        );
        document.documentElement.style.setProperty(
            "--journal-toolbar-gap",
            `${Math.max(2, Math.round(8 * scale))}px`,
        );

        table.blockRedraw?.();
        try {
            table.getColumns().forEach((column) => {
                const field = column.getField();
                const metric = baseMetrics.get(field);
                if (!field || !metric) return;
                const width = Math.max(12, Math.round(metric.width * scale));
                const minWidth = Math.max(8, Math.round(metric.minWidth * scale));
                const definition = column.getDefinition?.();
                if (definition) definition.minWidth = minWidth;
                if (column._column) column._column.minWidth = minWidth;
                column.setWidth(width);
            });
        } finally {
            table.restoreRedraw?.();
        }
        table.redraw?.(false);
        finishZoom(holder, scrollTop, scrollLeft, value);
    }

    function zoomFromPointer(slider, event) {
        const rect = slider.getBoundingClientRect();
        if (!(rect.width > 0)) return;
        const position = ((event.clientX - rect.left) / rect.width) * 100;
        applyZoom(positionToZoom(position));
    }

    function buildSlider(native) {
        if (!native || sliders.has(native.id)) return;
        native.classList.add("acceptance-zoom-native");
        const slider = document.createElement("div");
        slider.id = `acceptance-${native.id}`;
        slider.className = "acceptance-zoom-slider";
        slider.tabIndex = 0;
        slider.setAttribute("role", "slider");
        slider.setAttribute("aria-label", "Масштаб таблицы");
        slider.setAttribute("aria-valuemin", "10");
        slider.setAttribute("aria-valuemax", "400");
        slider.innerHTML = `
            <span class="acceptance-zoom-track"></span>
            <span class="acceptance-zoom-progress"></span>
            <span class="acceptance-zoom-thumb"></span>
        `;
        native.insertAdjacentElement("afterend", slider);
        sliders.set(native.id, slider);

        let pointerId = null;
        slider.addEventListener("pointerdown", (event) => {
            event.preventDefault();
            pointerId = event.pointerId;
            slider.setPointerCapture(pointerId);
            zoomFromPointer(slider, event);
        });
        slider.addEventListener("pointermove", (event) => {
            if (pointerId !== event.pointerId || !(event.buttons & 1)) return;
            event.preventDefault();
            zoomFromPointer(slider, event);
        });
        const release = (event) => {
            if (pointerId !== event.pointerId) return;
            if (slider.hasPointerCapture(pointerId)) slider.releasePointerCapture(pointerId);
            pointerId = null;
        };
        slider.addEventListener("pointerup", release);
        slider.addEventListener("pointercancel", release);
        slider.addEventListener("wheel", (event) => {
            event.preventDefault();
            applyZoom(currentZoom + (event.deltaY < 0 ? 5 : -5));
        }, {passive: false});
        slider.addEventListener("keydown", (event) => {
            let next = null;
            if (["ArrowRight", "ArrowUp"].includes(event.key)) next = currentZoom + 5;
            else if (["ArrowLeft", "ArrowDown"].includes(event.key)) next = currentZoom - 5;
            else if (event.key === "Home") next = 10;
            else if (event.key === "End") next = 400;
            if (next === null) return;
            event.preventDefault();
            applyZoom(next);
        });
    }

    function cancelLegacyRowDrag() {
        window.dispatchEvent(new PointerEvent("pointercancel", {
            bubbles: false,
            cancelable: false,
            pointerId: 1,
        }));
    }

    function clearCellVisuals() {
        root.querySelectorAll(".journal-active-cell").forEach((element) => {
            element.classList.remove("journal-active-cell");
        });
        root.querySelectorAll(".operator-column-selected").forEach((element) => {
            element.classList.remove("operator-column-selected");
        });
        document.querySelectorAll(".journal-fill-handle").forEach((handle) => {
            handle.hidden = true;
        });
        root.dataset.selectionMode = "rows";
    }

    function dispatchRowSelection(rowNumber, modifiers = {}) {
        syntheticRowEvent = true;
        try {
            rowNumber.dispatchEvent(new PointerEvent("pointerdown", {
                bubbles: true,
                cancelable: true,
                composed: true,
                button: 0,
                buttons: 1,
                shiftKey: Boolean(modifiers.shiftKey),
                ctrlKey: Boolean(modifiers.ctrlKey),
                metaKey: Boolean(modifiers.metaKey),
            }));
        } finally {
            syntheticRowEvent = false;
        }
        clearCellVisuals();
        setTimeout(clearCellVisuals, 0);
    }

    function rowNumberAtPoint(x, y) {
        const element = document.elementFromPoint(x, y);
        return element instanceof Element ? element.closest(".journal-row-number") : null;
    }

    function installRowSelection() {
        window.addEventListener("pointerdown", (event) => {
            if (syntheticRowEvent || !event.isTrusted || event.button !== 0) return;
            if (!(event.target instanceof Element)) return;
            const rowNumber = event.target.closest(".journal-row-number");
            if (!rowNumber || !root.contains(rowNumber)) return;

            event.preventDefault();
            event.stopImmediatePropagation();
            cancelLegacyRowDrag();
            dispatchRowSelection(rowNumber, event);
            drag = {
                last: rowNumber,
                ctrlKey: event.ctrlKey,
                metaKey: event.metaKey,
            };
        }, true);

        window.addEventListener("pointermove", (event) => {
            if (!drag || !(event.buttons & 1)) return;
            const rowNumber = rowNumberAtPoint(event.clientX, event.clientY);
            if (rowNumber && rowNumber !== drag.last) {
                drag.last = rowNumber;
                dispatchRowSelection(rowNumber, {
                    shiftKey: true,
                    ctrlKey: drag.ctrlKey,
                    metaKey: drag.metaKey,
                });
            }
            const holder = root.querySelector(".tabulator-tableholder");
            if (holder) {
                const rect = holder.getBoundingClientRect();
                const edge = 30;
                if (event.clientY < rect.top + edge) holder.scrollTop -= 20;
                else if (event.clientY > rect.bottom - edge) holder.scrollTop += 20;
            }
            event.preventDefault();
            event.stopImmediatePropagation();
        }, true);

        const finish = () => { drag = null; };
        window.addEventListener("pointerup", finish, true);
        window.addEventListener("pointercancel", finish, true);
        window.addEventListener("click", (event) => {
            if (!(event.target instanceof Element)) return;
            if (event.target.closest(".journal-row-number") && root.contains(event.target)) {
                event.preventDefault();
                event.stopImmediatePropagation();
            }
        }, true);

        table.on("cellClick", () => {
            root.dataset.selectionMode = "cells";
        });
    }

    function installButtons() {
        const bind = (id, step) => {
            document.getElementById(id)?.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopImmediatePropagation();
                applyZoom(currentZoom + step);
            }, true);
        };
        bind("ribbon-zoom-out", -5);
        bind("ribbon-zoom-in", 5);
    }

    function start() {
        addStyles();
        currentZoom = roundZoom(
            root.dataset.sheetZoom
            || loadPreferences().zoom
            || localStorage.getItem(zoomKey)
            || 100,
        );
        captureBaseMetrics();
        controls.forEach((id) => buildSlider(document.getElementById(id)));
        installButtons();
        installRowSelection();
        window.shiftHelperZoom = {apply: applyZoom};
        window.shiftHelperAcceptanceStage1 = {
            setZoom: applyZoom,
            zoomToPosition,
            positionToZoom,
        };
        applyZoom(currentZoom, false);
        root.dataset.acceptanceStage1 = "ready";
    }

    start();
})();
