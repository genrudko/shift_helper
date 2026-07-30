export type EditorControls = {
  readonly selection: HTMLElement;
  readonly close: HTMLButtonElement;
};

export type ShellElements = {
  readonly status: HTMLElement;
  readonly controls: EditorControls;
};

function requireElement<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);
  if (!element) throw new Error(`Не найден элемент журнала событий: ${selector}`);
  return element;
}

export function renderShell(root: HTMLElement): ShellElements {
  root.innerHTML = `
    <section class="shift-helper-v2">
      <header class="shift-helper-v2__header">
        <div class="shift-helper-v2__title">
          <strong>Журнал событий</strong>
          <span>Оперативные записи смены</span>
        </div>
        <span class="shift-helper-v2__status" role="status">Загрузка данных…</span>
      </header>
      <div class="shift-helper-v2__editor" aria-label="Контекст выбранной строки">
        <span class="shift-helper-v2__selection" data-testid="journal-selection">
          Выберите строку
        </span>
        <span class="shift-helper-v2__editing-hint">
          Ввод и изменение выполняются непосредственно в ячейках таблицы
        </span>
        <button
          class="shift-helper-v2__close"
          data-testid="journal-close"
          type="button"
          disabled
        >Завершить событие</button>
      </div>
      <div id="univer-sheet" class="shift-helper-v2__sheet"></div>
    </section>
  `;

  requireElement<HTMLElement>(root, '#univer-sheet');
  return {
    status: requireElement<HTMLElement>(root, '.shift-helper-v2__status'),
    controls: {
      selection: requireElement<HTMLElement>(root, '[data-testid="journal-selection"]'),
      close: requireElement<HTMLButtonElement>(root, '[data-testid="journal-close"]'),
    },
  };
}

export function renderFailure(root: HTMLElement, error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  const container = document.createElement('section');
  container.className = 'shift-helper-v2__error';
  container.setAttribute('role', 'alert');
  const title = document.createElement('strong');
  title.textContent = 'Журнал событий не запущен.';
  container.append(title, document.createElement('br'), document.createTextNode(message));
  root.replaceChildren(container);
}
