"use strict";

/*
 * Register before the journal modules. The regular Ribbon context menu remains
 * primary; this preflight only creates a menu when all later handlers fail.
 */
(() => {
    if (window.shiftHelperContextPreflight === "ready") return;
    window.shiftHelperContextPreflight = "ready";

    const ICONS = "/static/shift_helper_icons_v1.svg";
    let fallbackShell = null;
    let fallbackTimer = 0;
    const diagnostics = {
        events: [],
        showCalls: 0,
        closeCalls: 0,
        created: 0,
        removed: 0,
        lastReject: null,
        lastShell: null,
    };
    window.shiftHelperContextDiagnostics = diagnostics;

    const remember = (type, detail = {}) => {
        diagnostics.events.push({type, time: performance.now(), ...detail});
        if (diagnostics.events.length > 40) diagnostics.events.shift();
    };
    const describeElement = (element) => {
        if (!(element instanceof Element)) return null;
        return {
            tag: element.tagName,
            id: element.id || null,
            className: typeof element.className === "string" ? element.className : null,
        };
    };
    const shellSnapshot = (shell) => {
        if (!(shell instanceof Element)) return null;
        const rect = shell.getBoundingClientRect();
        const style = getComputedStyle(shell);
        return {
            connected: shell.isConnected,
            clientRects: shell.getClientRects().length,
            rect: {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
            },
            display: style.display,
            visibility: style.visibility,
            opacity: style.opacity,
            pointerEvents: style.pointerEvents,
            zIndex: style.zIndex,
            owner: shell.dataset.contextPreflightMenu || null,
        };
    };
    const svg = (name) => (
        `<svg class="ribbon-icon" aria-hidden="true"><use href="${ICONS}#${name}"></use></svg>`
    );
    const visibleShell = () => [...document.querySelectorAll(".journal-context-shell")]
        .find((shell) => shell.getClientRects().length > 0);

    function closeFallback(reason = "preflight-close") {
        window.clearTimeout(fallbackTimer);
        diagnostics.closeCalls += 1;
        remember("close", {reason, shell: shellSnapshot(fallbackShell)});
        fallbackShell?.remove();
        fallbackShell = null;
    }

    function mirrorSelect(sourceId, title) {
        const source = document.getElementById(sourceId);
        const select = document.createElement("select");
        select.title = title;
        if (source instanceof HTMLSelectElement) {
            [...source.options].forEach((option) => {
                select.add(new Option(option.textContent, option.value, false, option.selected));
            });
            select.value = source.value;
            select.addEventListener("change", () => {
                source.value = select.value;
                source.dispatchEvent(new Event("change", {bubbles: true}));
            });
        }
        return select;
    }

    function toolbarButton(icon, title, selector) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "ribbon-icon-button";
        button.innerHTML = svg(icon);
        button.title = title;
        button.addEventListener("click", () => document.querySelector(selector)?.click());
        return button;
    }

    function command(label, icon, selector, danger = false) {
        const button = document.createElement("button");
        button.type = "button";
        button.innerHTML = `${svg(icon)}<span>${label}</span>`;
        button.classList.toggle("is-danger", danger);
        button.addEventListener("click", () => {
            closeFallback("command");
            document.querySelector(selector)?.click();
        });
        return button;
    }

    function buildToolbar() {
        const toolbar = document.createElement("div");
        toolbar.className = "journal-mini-toolbar";
        toolbar.append(
            mirrorSelect("ribbon-font-family", "Шрифт"),
            mirrorSelect("ribbon-font-size", "Размер шрифта"),
            toolbarButton("bold", "Полужирный", '[data-text-style="bold"]'),
            toolbarButton("italic", "Курсив", '[data-text-style="italic"]'),
            toolbarButton("fill", "Применить заливку", "#operator-fill-control .operator-fill-main"),
            toolbarButton(
                "align-center",
                "Выровнять по центру",
                '[data-align-horizontal="center"]',
            ),
        );
        return toolbar;
    }

    function buildMenu(mode) {
        const menu = document.createElement("div");
        menu.className = "journal-context-menu";
        if (mode === "rows") {
            const count = Math.max(1, (window.shiftHelperSelectedRowKeys || []).length);
            const suffix = count > 1 ? ` ${count} строк` : " строку";
            menu.append(
                command(`Копировать${suffix}`, "copy", '[data-ribbon-command="copy"]'),
                command(`Вырезать${suffix}`, "cut", '[data-ribbon-command="cut"]'),
                command("Вставить в выбранные строки", "paste", '[data-ribbon-command="paste"]'),
            );
            const separator = document.createElement("div");
            separator.className = "journal-context-separator";
            menu.append(
                separator,
                command(
                    `Удалить${suffix}`,
                    "delete-row",
                    '[data-ribbon-command="delete-rows"]',
                    true,
                ),
            );
        } else {
            menu.append(
                command("Копировать", "copy", '[data-ribbon-command="copy"]'),
                command("Вырезать", "cut", '[data-ribbon-command="cut"]'),
                command("Вставить", "paste", '[data-ribbon-command="paste"]'),
            );
            const separator = document.createElement("div");
            separator.className = "journal-context-separator";
            menu.append(
                separator,
                command("Очистить содержимое", "clear", '[data-ribbon-command="clear"]'),
            );
        }
        return menu;
    }

    function showFallback(mode, coordinates) {
        diagnostics.showCalls += 1;
        const existing = visibleShell();
        if (existing) {
            diagnostics.lastShell = shellSnapshot(existing);
            remember("show-skipped-existing", {mode, shell: diagnostics.lastShell});
            return;
        }
        closeFallback("replace-before-show");
        const shell = document.createElement("div");
        shell.className = "journal-context-shell";
        shell.dataset.contextPreflightMenu = mode;
        shell.append(buildToolbar(), buildMenu(mode));
        document.body.appendChild(shell);
        fallbackShell = shell;
        diagnostics.created += 1;

        const rect = shell.getBoundingClientRect();
        const margin = 8;
        shell.style.left = `${Math.max(
            margin,
            Math.min(coordinates.x, innerWidth - rect.width - margin),
        )}px`;
        shell.style.top = `${Math.max(
            margin,
            coordinates.y + rect.height > innerHeight - margin
                ? coordinates.y - rect.height
                : coordinates.y,
        )}px`;
        diagnostics.lastShell = shellSnapshot(shell);
        remember("show-created", {mode, coordinates, shell: diagnostics.lastShell});
        requestAnimationFrame(() => {
            diagnostics.lastShell = shellSnapshot(shell);
            remember("show-frame", {shell: diagnostics.lastShell});
        });
        window.setTimeout(() => {
            diagnostics.lastShell = shellSnapshot(shell);
            remember("show-after-150ms", {shell: diagnostics.lastShell});
        }, 150);
    }

    function hitFromEvent(event) {
        const target = event.target instanceof Element ? event.target : null;
        const pointTarget = document.elementFromPoint(event.clientX, event.clientY);
        const candidates = [target, pointTarget].filter((item) => item instanceof Element);
        const rowNumber = candidates
            .map((item) => item.closest(".journal-row-number"))
            .find(Boolean);
        const cell = candidates
            .map((item) => item.closest(".tabulator-cell"))
            .find(Boolean);
        return {target, pointTarget, rowNumber, cell};
    }

    function scheduleFallback(event) {
        const root = document.getElementById("event-journal");
        if (!root) {
            diagnostics.lastReject = "missing-root";
            return false;
        }
        const rootRect = root.getBoundingClientRect();
        const insideRoot = event.clientX >= rootRect.left
            && event.clientX <= rootRect.right
            && event.clientY >= rootRect.top
            && event.clientY <= rootRect.bottom;
        const hit = hitFromEvent(event);
        const holder = root.querySelector(".tabulator-tableholder");
        const holderRect = holder?.getBoundingClientRect();
        const insideHolder = Boolean(holderRect)
            && event.clientX >= holderRect.left
            && event.clientX <= holderRect.right
            && event.clientY >= holderRect.top
            && event.clientY <= holderRect.bottom;
        const detail = {
            eventType: event.type,
            button: event.button,
            x: event.clientX,
            y: event.clientY,
            insideRoot,
            insideHolder,
            target: describeElement(hit.target),
            pointTarget: describeElement(hit.pointTarget),
            rowNumber: Boolean(hit.rowNumber),
            cell: Boolean(hit.cell),
        };
        remember("event", detail);
        if (!insideRoot) {
            diagnostics.lastReject = "outside-root";
            remember("reject", {reason: diagnostics.lastReject, ...detail});
            return false;
        }
        if (!hit.rowNumber && !hit.cell && !insideHolder) {
            diagnostics.lastReject = "no-cell-or-holder";
            remember("reject", {reason: diagnostics.lastReject, ...detail});
            return false;
        }

        const mode = hit.rowNumber ? "rows" : "cells";
        const coordinates = {x: event.clientX, y: event.clientY};
        diagnostics.lastReject = null;
        window.clearTimeout(fallbackTimer);
        fallbackTimer = window.setTimeout(() => showFallback(mode, coordinates), 40);
        remember("scheduled", {mode, coordinates});
        return true;
    }

    window.shiftHelperContextPreflightOpen = (mode, x, y) => {
        remember("api-open", {mode, x, y});
        showFallback(mode, {x: Number(x) || 8, y: Number(y) || 8});
    };
    window.shiftHelperContextPreflightClose = () => closeFallback("api-close");

    const observer = new MutationObserver((records) => {
        records.forEach((record) => {
            record.removedNodes.forEach((node) => {
                if (!(node instanceof Element)) return;
                const removedShell = node.matches(".journal-context-shell")
                    ? node
                    : node.querySelector(".journal-context-shell");
                if (!removedShell) return;
                diagnostics.removed += 1;
                remember("removed", {shell: shellSnapshot(removedShell)});
            });
        });
    });
    observer.observe(document.documentElement, {childList: true, subtree: true});

    window.addEventListener("pointerdown", (event) => {
        if (event.button === 2 && scheduleFallback(event)) return;
        if (
            fallbackShell
            && event.target instanceof Element
            && !fallbackShell.contains(event.target)
        ) {
            closeFallback("outside-pointerdown");
        }
    }, true);

    ["pointerup", "mouseup", "auxclick"].forEach((type) => {
        window.addEventListener(type, (event) => {
            if (event.button !== 2) return;
            scheduleFallback(event);
        }, true);
    });

    window.addEventListener("contextmenu", (event) => {
        if (!scheduleFallback(event)) return;
        event.preventDefault();
    }, true);

    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeFallback("escape");
    }, true);
    window.addEventListener("resize", () => closeFallback("resize"));
})();
