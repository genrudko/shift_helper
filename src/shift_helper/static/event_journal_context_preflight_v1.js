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

    const svg = (name) => (
        `<svg class="ribbon-icon" aria-hidden="true"><use href="${ICONS}#${name}"></use></svg>`
    );
    const visibleShell = () => [...document.querySelectorAll(".journal-context-shell")]
        .find((shell) => shell.getClientRects().length > 0);

    function closeFallback() {
        window.clearTimeout(fallbackTimer);
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
            closeFallback();
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
        if (visibleShell()) return;
        closeFallback();
        const shell = document.createElement("div");
        shell.className = "journal-context-shell";
        shell.dataset.contextPreflightMenu = mode;
        shell.append(buildToolbar(), buildMenu(mode));
        document.body.appendChild(shell);
        fallbackShell = shell;

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
    }

    function scheduleFallback(event) {
        if (!(event.target instanceof Element)) return false;
        const root = document.getElementById("event-journal");
        if (!root || !root.contains(event.target)) return false;
        const rowNumber = event.target.closest(".journal-row-number");
        const cell = event.target.closest(".tabulator-cell");
        if (!rowNumber && !cell) return false;

        const mode = rowNumber ? "rows" : "cells";
        const coordinates = {x: event.clientX, y: event.clientY};
        window.clearTimeout(fallbackTimer);
        fallbackTimer = window.setTimeout(() => showFallback(mode, coordinates), 40);
        return true;
    }

    window.shiftHelperContextPreflightOpen = (mode, x, y) => {
        showFallback(mode, {x: Number(x) || 8, y: Number(y) || 8});
    };
    window.shiftHelperContextPreflightClose = closeFallback;

    window.addEventListener("pointerdown", (event) => {
        if (event.button === 2 && scheduleFallback(event)) return;
        if (
            fallbackShell
            && event.target instanceof Element
            && !fallbackShell.contains(event.target)
        ) {
            closeFallback();
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
        if (event.key === "Escape") closeFallback();
    }, true);
    window.addEventListener("resize", closeFallback);
})();
