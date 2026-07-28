"use strict";

/*
 * Acceptance stage 1 is now a thin UI adapter.
 * The authoritative zoom and row-selection controllers live in bootstrap_v1.
 */
(() => {
    const root = document.getElementById("event-journal");
    if (!root || root.dataset.acceptanceStage1 === "ready") return;

    const controls = ["journal-zoom", "ribbon-zoom"];
    const sliders = new Map();
    const baseApply = window.shiftHelperStage1BaseZoomApply
        || window.shiftHelperZoom?.apply?.bind(window.shiftHelperZoom);
    if (typeof baseApply !== "function") return;

    const clampZoom = (raw) => Math.min(400, Math.max(10, Number(raw) || 100));
    const roundZoom = (raw) => clampZoom(Math.round(clampZoom(raw) / 5) * 5);
    const zoomToPosition = (raw) => ((clampZoom(raw) - 10) / 390) * 100;
    const positionToZoom = (raw) => roundZoom(10 + ((Math.min(100, Math.max(0, Number(raw) || 0)) / 100) * 390));

    function addStyles() {
        if (document.getElementById("acceptance-stage1-style")) return;
        const style = document.createElement("style");
        style.id = "acceptance-stage1-style";
        style.textContent = `
            .acceptance-zoom-native { display: none !important; }
            .acceptance-zoom-slider {
                --acceptance-zoom-position: 23.0769%;
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

    function syncZoomUi(raw) {
        const value = roundZoom(raw);
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

    function applyZoom(raw, persist = true) {
        const value = roundZoom(raw);
        baseApply(value, persist);
        syncZoomUi(value);
        return value;
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
            const current = Number(root.dataset.sheetZoom || 100);
            applyZoom(current + (event.deltaY < 0 ? 5 : -5));
        }, {passive: false});
        slider.addEventListener("keydown", (event) => {
            const current = Number(root.dataset.sheetZoom || 100);
            let next = null;
            if (["ArrowRight", "ArrowUp"].includes(event.key)) next = current + 5;
            else if (["ArrowLeft", "ArrowDown"].includes(event.key)) next = current - 5;
            else if (event.key === "Home") next = 10;
            else if (event.key === "End") next = 400;
            if (next === null) return;
            event.preventDefault();
            applyZoom(next);
        });
    }

    addStyles();
    controls.forEach((id) => buildSlider(document.getElementById(id)));
    window.addEventListener("shifthelper:zoom", (event) => {
        syncZoomUi(event.detail?.value || root.dataset.sheetZoom || 100);
    });

    const initial = Number(root.dataset.sheetZoom || 100);
    syncZoomUi(initial);
    window.shiftHelperAcceptanceStage1 = {
        setZoom: applyZoom,
        zoomToPosition,
        positionToZoom,
    };
    root.dataset.acceptanceStage1 = "ready";
})();
