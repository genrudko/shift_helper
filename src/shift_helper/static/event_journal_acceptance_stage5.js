"use strict";

/* Operator acceptance stage 5: Insert tab and technical symbol picker. */
(() => {
    const root = document.getElementById("event-journal");
    const table = window.shiftHelperEventGrid;
    const ribbon = document.getElementById("journal-ribbon");
    if (!root || !table || !ribbon || root.dataset.acceptanceStage5 === "ready") return;

    const iconUrl = "/static/shift_helper_icons_v1.svg";
    const recentKey = "shift-helper-recent-symbols-v1";
    const categories = {
        greek: "Греческий алфавит",
        roman: "Римские числа",
        math: "Математика",
        electrical: "Электротехника",
        arrows: "Стрелки",
    };
    const symbols = [
        ...[
            ["Α", "Альфа"], ["Β", "Бета"], ["Γ", "Гамма"], ["Δ", "Дельта"],
            ["Ε", "Эпсилон"], ["Ζ", "Дзета"], ["Η", "Эта"], ["Θ", "Тета"],
            ["Ι", "Йота"], ["Κ", "Каппа"], ["Λ", "Лямбда"], ["Μ", "Мю"],
            ["Ν", "Ню"], ["Ξ", "Кси"], ["Ο", "Омикрон"], ["Π", "Пи"],
            ["Ρ", "Ро"], ["Σ", "Сигма"], ["Τ", "Тау"], ["Υ", "Ипсилон"],
            ["Φ", "Фи"], ["Χ", "Хи"], ["Ψ", "Пси"], ["Ω", "Омега"],
            ["α", "альфа"], ["β", "бета"], ["γ", "гамма"], ["δ", "дельта"],
            ["ε", "эпсилон"], ["θ", "тета"], ["λ", "лямбда"], ["μ", "мю"],
            ["π", "пи"], ["ρ", "ро"], ["σ", "сигма"], ["τ", "тау"],
            ["φ", "фи"], ["ψ", "пси"], ["ω", "омега"],
        ].map(([glyph, name]) => ({glyph, name, category: "greek"})),
        ...[
            ["Ⅰ", "I"], ["Ⅱ", "II"], ["Ⅲ", "III"], ["Ⅳ", "IV"],
            ["Ⅴ", "V"], ["Ⅵ", "VI"], ["Ⅶ", "VII"], ["Ⅷ", "VIII"],
            ["Ⅸ", "IX"], ["Ⅹ", "X"], ["Ⅺ", "XI"], ["Ⅻ", "XII"],
        ].map(([glyph, name]) => ({glyph, name: `Римское ${name}`, category: "roman"})),
        ...[
            ["±", "Плюс-минус"], ["∓", "Минус-плюс"], ["×", "Умножение"],
            ["÷", "Деление"], ["≈", "Приблизительно"], ["≠", "Не равно"],
            ["≤", "Меньше или равно"], ["≥", "Больше или равно"], ["∞", "Бесконечность"],
            ["√", "Корень"], ["∑", "Сумма"], ["∫", "Интеграл"], ["∆", "Приращение"],
            ["∂", "Частная производная"], ["∅", "Пустое множество"], ["∈", "Принадлежит"],
            ["∝", "Пропорционально"], ["·", "Средняя точка"], ["²", "Квадрат"],
            ["³", "Куб"], ["₁", "Индекс 1"], ["₂", "Индекс 2"], ["₃", "Индекс 3"],
        ].map(([glyph, name]) => ({glyph, name, category: "math"})),
        ...[
            ["Ω", "Ом"], ["µ", "Микро"], ["°", "Градус"], ["℃", "Градус Цельсия"],
            ["℉", "Градус Фаренгейта"], ["∠", "Угол"], ["⌀", "Диаметр"],
            ["⏚", "Заземление"], ["⚡", "Высокое напряжение"], ["ϕ", "Фи"],
            ["η", "КПД эта"], ["ω", "Угловая частота"], ["Δ", "Дельта"],
            ["∇", "Набла"], ["⋂", "Пересечение"], ["⊕", "Суммирование"],
        ].map(([glyph, name]) => ({glyph, name, category: "electrical"})),
        ...[
            ["←", "Влево"], ["→", "Вправо"], ["↑", "Вверх"], ["↓", "Вниз"],
            ["↔", "В обе стороны"], ["↕", "Вертикально"], ["⇒", "Следует"],
            ["⇐", "Обратно"], ["⇄", "Переключение"], ["↗", "Вверх-вправо"],
            ["↘", "Вниз-вправо"], ["⟶", "Длинная стрелка"],
        ].map(([glyph, name]) => ({glyph, name, category: "arrows"})),
    ];
    let dialog = null;
    let currentCategory = "all";
    let currentSearch = "";

    function svg(name) {
        return `<svg class="ribbon-icon" aria-hidden="true"><use href="${iconUrl}#${name}"></use></svg>`;
    }

    function loadRecent() {
        try {
            const value = JSON.parse(localStorage.getItem(recentKey) || "[]");
            return Array.isArray(value) ? value.filter((item) => typeof item === "string") : [];
        } catch (_error) {
            return [];
        }
    }

    function saveRecent(glyph) {
        const next = [glyph, ...loadRecent().filter((item) => item !== glyph)].slice(0, 12);
        try { localStorage.setItem(recentKey, JSON.stringify(next)); } catch (_error) { /* optional */ }
        renderRecent();
    }

    function selectedCell() {
        const cells = window.shiftHelperAcceptanceStage4?.selectedCells?.() || [];
        if (cells.length) return cells[0];
        const active = root.querySelector(".journal-active-cell");
        if (!active) return null;
        for (const row of table.getRows("active")) {
            const cell = row.getCells().find((candidate) => candidate.getElement?.() === active);
            if (cell) return cell;
        }
        return null;
    }

    function insertIntoEditor(editor, glyph) {
        const start = Number.isInteger(editor.selectionStart) ? editor.selectionStart : editor.value.length;
        const end = Number.isInteger(editor.selectionEnd) ? editor.selectionEnd : start;
        editor.setRangeText(glyph, start, end, "end");
        editor.dispatchEvent(new Event("input", {bubbles: true}));
        editor.focus();
    }

    function insertSymbol(glyph) {
        const editor = root.querySelector(".journal-stable-editor");
        if (editor instanceof HTMLInputElement || editor instanceof HTMLTextAreaElement) {
            insertIntoEditor(editor, glyph);
            saveRecent(glyph);
            updateStatus(`Вставлен символ ${glyph}.`);
            return true;
        }
        const cell = selectedCell();
        if (!cell) {
            updateStatus("Сначала выберите ячейку.");
            return false;
        }
        const before = String(cell.getValue() ?? "");
        cell.setValue(`${before}${glyph}`, true);
        saveRecent(glyph);
        updateStatus(`Символ ${glyph} добавлен в выбранную ячейку.`);
        try { cell.getElement()?.focus?.(); } catch (_error) { /* non-focusable cell */ }
        return true;
    }

    function activateInsertTab() {
        document.querySelectorAll("[data-ribbon-tab]").forEach((button) => {
            button.setAttribute("aria-selected", String(button.dataset.ribbonTab === "insert"));
        });
        document.querySelectorAll("[data-ribbon-panel]").forEach((panel) => {
            panel.hidden = panel.dataset.ribbonPanel !== "insert";
        });
        if (ribbon.dataset.ribbonState === "collapsed") ribbon.dataset.ribbonState = "temporary";
    }

    function buildInsertTab() {
        if (document.querySelector('[data-ribbon-tab="insert"]')) return;
        const tabs = ribbon.querySelector(".journal-ribbon__tabs");
        const dataTab = tabs?.querySelector('[data-ribbon-tab="data"]');
        const panels = ribbon.querySelector(".journal-ribbon__panels");
        if (!tabs || !panels) return;

        const tab = document.createElement("button");
        tab.className = "ribbon-tab";
        tab.type = "button";
        tab.role = "tab";
        tab.dataset.ribbonTab = "insert";
        tab.setAttribute("aria-selected", "false");
        tab.textContent = "Вставка";
        tab.addEventListener("click", activateInsertTab);
        tabs.insertBefore(tab, dataTab || tabs.querySelector("#ribbon-collapse"));

        const panel = document.createElement("div");
        panel.className = "ribbon-panel";
        panel.dataset.ribbonPanel = "insert";
        panel.role = "tabpanel";
        panel.hidden = true;
        panel.innerHTML = `
            <section class="ribbon-group stage5-symbol-group" aria-label="Символы">
                <button class="ribbon-command ribbon-command--large stage5-symbol-command" id="stage5-open-symbols" type="button">
                    ${svg("conditional")}<span>Символ</span>
                </button>
                <div class="stage5-symbol-quick" aria-label="Часто используемые символы"></div>
                <span class="ribbon-group__label">Символы</span>
            </section>
        `;
        panels.insertBefore(panel, panels.querySelector('[data-ribbon-panel="data"]'));
        panel.querySelector("#stage5-open-symbols")?.addEventListener("click", openDialog);
        const quick = panel.querySelector(".stage5-symbol-quick");
        ["Ω", "Δ", "±", "°", "→", "←", "Ⅰ", "Ⅳ"].forEach((glyph) => {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = glyph;
            button.title = symbols.find((item) => item.glyph === glyph)?.name || glyph;
            button.addEventListener("click", () => insertSymbol(glyph));
            quick?.appendChild(button);
        });
    }

    function buildDialog() {
        if (dialog) return dialog;
        dialog = document.createElement("dialog");
        dialog.id = "stage5-symbol-dialog";
        dialog.className = "stage5-symbol-dialog";
        dialog.innerHTML = `
            <form method="dialog" class="stage5-symbol-panel">
                <header class="stage5-symbol-header">
                    <div><h2>Вставка символа</h2><p>Греческие, римские, математические и электротехнические обозначения.</p></div>
                    <button class="stage5-symbol-close" value="close" aria-label="Закрыть">×</button>
                </header>
                <div class="stage5-symbol-tools">
                    <input id="stage5-symbol-search" type="search" autocomplete="off" placeholder="Поиск: ом, дельта, стрелка…">
                    <select id="stage5-symbol-category"><option value="all">Все категории</option></select>
                </div>
                <section class="stage5-symbol-recent" id="stage5-symbol-recent" hidden>
                    <span class="stage5-symbol-recent-title">Последние использованные</span>
                    <div class="stage5-symbol-recent-list"></div>
                </section>
                <div class="stage5-symbol-grid" id="stage5-symbol-grid"></div>
                <footer class="stage5-symbol-footer">
                    <span class="stage5-symbol-preview" id="stage5-symbol-preview">Выберите символ</span>
                    <span id="stage5-symbol-status">Двойной щелчок не требуется — символ вставляется сразу.</span>
                </footer>
            </form>
        `;
        document.body.appendChild(dialog);
        const category = dialog.querySelector("#stage5-symbol-category");
        Object.entries(categories).forEach(([value, label]) => category?.add(new Option(label, value)));
        dialog.querySelector("#stage5-symbol-search")?.addEventListener("input", (event) => {
            currentSearch = event.target.value;
            renderGrid();
        });
        category?.addEventListener("change", (event) => {
            currentCategory = event.target.value;
            renderGrid();
        });
        dialog.addEventListener("click", (event) => {
            if (event.target === dialog) dialog.close();
        });
        renderRecent();
        renderGrid();
        return dialog;
    }

    function symbolButton(item, compact = false) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "stage5-symbol-button";
        button.dataset.symbol = item.glyph;
        button.dataset.category = item.category;
        button.title = item.name;
        button.innerHTML = `<span class="stage5-symbol-glyph">${item.glyph}</span>${
            compact ? "" : `<span class="stage5-symbol-name">${item.name}</span>`
        }`;
        button.addEventListener("pointerenter", () => preview(item));
        button.addEventListener("focus", () => preview(item));
        button.addEventListener("click", () => insertSymbol(item.glyph));
        return button;
    }

    function normalized(value) {
        return String(value || "").trim().toLocaleLowerCase("ru");
    }

    function filteredSymbols() {
        const query = normalized(currentSearch);
        return symbols.filter((item) => {
            if (currentCategory !== "all" && item.category !== currentCategory) return false;
            if (!query) return true;
            return normalized(`${item.glyph} ${item.name} ${categories[item.category]}`).includes(query);
        });
    }

    function renderGrid() {
        const grid = document.getElementById("stage5-symbol-grid");
        if (!grid) return;
        const items = filteredSymbols();
        grid.replaceChildren();
        if (!items.length) {
            const empty = document.createElement("div");
            empty.className = "stage5-symbol-empty";
            empty.textContent = "Подходящих символов не найдено.";
            grid.appendChild(empty);
            return;
        }
        items.forEach((item) => grid.appendChild(symbolButton(item)));
    }

    function renderRecent() {
        const section = document.getElementById("stage5-symbol-recent");
        const list = section?.querySelector(".stage5-symbol-recent-list");
        if (!section || !list) return;
        const recent = loadRecent()
            .map((glyph) => symbols.find((item) => item.glyph === glyph) || {glyph, name: glyph, category: "math"});
        section.hidden = !recent.length;
        list.replaceChildren();
        recent.forEach((item) => list.appendChild(symbolButton(item, true)));
    }

    function preview(item) {
        const target = document.getElementById("stage5-symbol-preview");
        target?.replaceChildren();
        if (!target) return;
        const glyph = document.createElement("strong");
        glyph.textContent = item.glyph;
        const name = document.createElement("span");
        name.textContent = `${item.name} · ${categories[item.category] || "Символ"}`;
        target.append(glyph, name);
    }

    function updateStatus(message) {
        document.getElementById("stage5-symbol-status")?.replaceChildren(message);
    }

    function openDialog() {
        const target = buildDialog();
        currentCategory = "all";
        currentSearch = "";
        const search = target.querySelector("#stage5-symbol-search");
        const category = target.querySelector("#stage5-symbol-category");
        if (search) search.value = "";
        if (category) category.value = "all";
        renderRecent();
        renderGrid();
        if (!target.open) target.showModal();
        search?.focus();
    }

    window.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && dialog?.open) dialog.close();
    }, true);

    buildInsertTab();
    buildDialog();
    window.shiftHelperAcceptanceStage5 = {openDialog, insertSymbol, symbols};
    root.dataset.acceptanceStage5 = "ready";
})();
