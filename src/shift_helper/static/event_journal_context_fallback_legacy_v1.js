"use strict";

(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;

    if (!root || !table || root.dataset.contextFallback === "ready") {
        return;
    }
    root.dataset.contextFallback = "ready";

    if (root.dataset.lightRedrawGuard !== "ready" && typeof table.redraw === "function") {
        const guardedRedraw = table.redraw.bind(table);
        table.redraw = () => guardedRedraw(false);
        root.dataset.lightRedrawGuard = "ready";
    }

    function guardColumnMutations() {
        const sample = table.getColumns()?.[0];
        const prototype = sample ? Object.getPrototypeOf(sample) : null;
        if (!prototype || prototype.__shiftHelperMutationGuard === true) return;

        const originalShow = prototype.show;
        const originalHide = prototype.hide;
        const originalSetWidth = prototype.setWidth;
        Object.defineProperty(prototype, "__shiftHelperMutationGuard", {
            configurable: false,
            enumerable: false,
            value: true,
            writable: false,
        });

        if (typeof originalShow === "function") {
            prototype.show = function show() {
                if (typeof this.isVisible === "function" && this.isVisible()) return this;
                return originalShow.call(this);
            };
        }
        if (typeof originalHide === "function") {
            prototype.hide = function hide() {
                if (typeof this.isVisible === "function" && !this.isVisible()) return this;
                return originalHide.call(this);
            };
        }
        if (typeof originalSetWidth === "function") {
            prototype.setWidth = function setWidth(width) {
                const requested = Number(width);
                const current = Number(this.getWidth?.());
                if (
                    Number.isFinite(requested)
                    && Number.isFinite(current)
                    && Math.abs(requested - current) < 0.5
                ) {
                    return this;
                }
                return originalSetWidth.call(this, width);
            };
        }
        root.dataset.columnMutationGuard = "ready";
    }

    const ICONS = "/static/shift_helper_icons_v1.svg";
    let redispatching = false;
    let fallbackShell = null;

    const svg = (name) => (
        `<svg class="ribbon-icon" aria-hidden="true"><use href="${ICONS}#${name}"></use></svg>`
    );

    function pinRowHeaders() {
        root.querySelectorAll(".tabulator-row-header, .journal-row-number").forEach((element) => {
            if (!(element instanceof HTMLElement)) return;
            element.style.position = "sticky";
            element.style.left = "0px";
            element.style.right = "auto";
            element.style.zIndex = element.closest(".tabulator-header") ? "70" : "60";
        });
        root.dataset.rowHeaderPinned = "true";
    }

    function containsPoint(element, x, y) {
        const rect = element.getBoundingClientRect();
        return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
    }

    function liveRowHeaderAtPoint(x, y) {
        for (const row of table.getRows("visible")) {
            let rowElement = null;
            try {
                rowElement = row.getElement();
            } catch (_error) {
                continue;
            }
            const header = rowElement?.querySelector?.(".journal-row-number");
            if (header instanceof Element && header.isConnected && containsPoint(header, x, y)) {
                return header;
            }
        }
        return null;
    }

    function liveCellAtPoint(x, y) {
        for (const row of table.getRows("visible")) {
            for (const cell of row.getCells()) {
                let element = null;
                try {
                    element = cell.getElement();
                } catch (_error) {
                    continue;
                }
                if (
                    element instanceof Element
                    && element.isConnected
                    && containsPoint(element, x, y)
                ) {
                    return element;
                }
            }
        }
        return null;
    }

    function pointerInit(event) {
        return {
            bubbles: true,
            cancelable: true,
            composed: true,
            pointerId: event.pointerId,
            pointerType: event.pointerType || "mouse",
            isPrimary: event.isPrimary,
            button: event.button,
            buttons: event.buttons,
            clientX: event.clientX,
            clientY: event.clientY,
            screenX: event.screenX,
            screenY: event.screenY,
            ctrlKey: event.ctrlKey,
            shiftKey: event.shiftKey,
            altKey: event.altKey,
            metaKey: event.metaKey,
        };
    }

    function closeFallbackShell() {
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

    function buildToolbar() {
        const toolbar = document.createElement("div");
        toolbar.className = "journal-mini-toolbar";
        toolbar.append(
            mirrorSelect("ribbon-font-family", "Шрифт"),
            mirrorSelect("ribbon-font-size", "Размер шрифта"),
            toolbarButton("bold", "Полужирный", '[data-text-style="bold"]'),
            toolbarButton("italic", "Курсив", '[data-text-style="italic"]'),
            toolbarButton("fill", "Применить текущую заливку", "#apply-cell-fill"),
            toolbarButton(
                "align-center",
                "Выровнять по центру",
                '[data-align-horizontal="center"]',
            ),
        );
        return toolbar;
    }

    function fallbackCommand(label, icon, selector, danger = false) {
        const button = document.createElement("button");
        button.type = "button";
        button.innerHTML = `${svg(icon)}<span>${label}</span>`;
        button.classList.toggle("is-danger", danger);
        button.addEventListener("click", () => {
            closeFallbackShell();
            document.querySelector(selector)?.click();
        });
        return button;
    }

    function placeFallbackShell(shell, coordinates) {
        document.body.appendChild(shell);
        fallbackShell = shell;
        const rect = shell.getBoundingClientRect();
        const margin = 8;
        const left = Math.max(
            margin,
            Math.min(coordinates.clientX, innerWidth - rect.width - margin),
        );
        const top = Math.max(
            margin,
            coordinates.clientY + rect.height > innerHeight - margin
                ? coordinates.clientY - rect.height
                : coordinates.clientY,
        );
        shell.style.left = `${left}px`;
        shell.style.top = `${top}px`;
    }

    function showFallbackRowMenu(coordinates) {
        closeFallbackShell();
        const selectedCount = Math.max(1, (window.shiftHelperSelectedRowKeys || []).length);
        const suffix = selectedCount > 1 ? ` ${selectedCount} строк` : " строку";

        const shell = document.createElement("div");
        shell.className = "journal-context-shell";
        shell.dataset.contextFallbackMenu = "rows";

        const menu = document.createElement("div");
        menu.className = "journal-context-menu";
        menu.append(
            fallbackCommand(`Копировать${suffix}`, "copy", '[data-ribbon-command="copy"]'),
            fallbackCommand(`Вырезать${suffix}`, "cut", '[data-ribbon-command="cut"]'),
            fallbackCommand(
                "Вставить в выбранные строки",
                "paste",
                '[data-ribbon-command="paste"]',
            ),
        );
        const separator = document.createElement("div");
        separator.className = "journal-context-separator";
        menu.append(
            separator,
            fallbackCommand(
                `Удалить${suffix}`,
                "delete-row",
                '[data-ribbon-command="delete-rows"]',
                true,
            ),
        );

        shell.append(buildToolbar(), menu);
        placeFallbackShell(shell, coordinates);
    }

    function showFallbackCellMenu(coordinates) {
        closeFallbackShell();
        const shell = document.createElement("div");
        shell.className = "journal-context-shell";
        shell.dataset.contextFallbackMenu = "cells";

        const menu = document.createElement("div");
        menu.className = "journal-context-menu";
        menu.append(
            fallbackCommand("Копировать", "copy", '[data-ribbon-command="copy"]'),
            fallbackCommand("Вырезать", "cut", '[data-ribbon-command="cut"]'),
            fallbackCommand("Вставить", "paste", '[data-ribbon-command="paste"]'),
        );
        const separator = document.createElement("div");
        separator.className = "journal-context-separator";
        menu.append(
            separator,
            fallbackCommand("Заполнить вниз", "vertical-bottom", '[data-ribbon-command="fill-down"]'),
            fallbackCommand("Заполнить вправо", "align-right", '[data-ribbon-command="fill-right"]'),
            fallbackCommand("Очистить содержимое", "clear", '[data-ribbon-command="clear"]'),
        );

        shell.append(buildToolbar(), menu);
        placeFallbackShell(shell, coordinates);
    }

    window.addEventListener("pointerdown", (event) => {
        if (fallbackShell && event.target instanceof Element && !fallbackShell.contains(event.target)) {
            closeFallbackShell();
        }
        if (
            redispatching
            || !(event.target instanceof Element)
            || !root.contains(event.target)
            || event.target.closest(".journal-row-number")
        ) {
            return;
        }
        const header = liveRowHeaderAtPoint(event.clientX, event.clientY);
        if (!header) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        redispatching = true;
        try {
            header.dispatchEvent(new PointerEvent("pointerdown", pointerInit(event)));
        } finally {
            redispatching = false;
        }
    }, true);

    window.addEventListener("contextmenu", (event) => {
        if (
            redispatching
            || !(event.target instanceof Element)
            || !root.contains(event.target)
        ) {
            return;
        }
        if (event.target.closest(".journal-row-number")) return;

        const rowHeader = liveRowHeaderAtPoint(event.clientX, event.clientY);
        const liveCell = liveCellAtPoint(event.clientX, event.clientY);
        const target = rowHeader || liveCell;
        if (!target) return;

        event.preventDefault();
        const before = document.querySelectorAll(".journal-context-shell").length;
        const coordinates = {
            clientX: event.clientX,
            clientY: event.clientY,
            screenX: event.screenX,
            screenY: event.screenY,
        };
        const modifiers = {
            ctrlKey: event.ctrlKey,
            shiftKey: event.shiftKey,
            altKey: event.altKey,
            metaKey: event.metaKey,
        };

        window.setTimeout(() => {
            if (document.querySelectorAll(".journal-context-shell").length > before) return;
            redispatching = true;
            try {
                target.dispatchEvent(new MouseEvent("contextmenu", {
                    bubbles: true,
                    cancelable: true,
                    composed: true,
                    button: 2,
                    buttons: 2,
                    ...modifiers,
                    ...coordinates,
                }));
            } finally {
                redispatching = false;
            }
            window.setTimeout(() => {
                if (document.querySelectorAll(".journal-context-shell").length > before) return;
                if (rowHeader) showFallbackRowMenu(coordinates);
                else showFallbackCellMenu(coordinates);
            }, 0);
        }, 0);
    }, true);

    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeFallbackShell();
    }, true);
    window.addEventListener("resize", pinRowHeaders);
    table.on("renderComplete", () => {
        guardColumnMutations();
        pinRowHeaders();
    });
    guardColumnMutations();
    pinRowHeaders();
})();
