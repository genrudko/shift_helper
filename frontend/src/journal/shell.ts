import type { JournalEventTypeOption } from './types';

export type EditorControls = {
  readonly selection: HTMLElement;
  readonly date: HTMLInputElement;
  readonly time: HTMLInputElement;
  readonly eventType: HTMLSelectElement;
  readonly includeInReport: HTMLInputElement;
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
      <div class="shift-helper-v2__editor" aria-label="Редактор выбранной строки">
        <span class="shift-helper-v2__selection" data-testid="journal-selection">
          Выберите строку
        </span>
        <label class="shift-helper-v2__field">
          <span>Дата</span>
          <input data-testid="journal-date" type="date" disabled>
        </label>
        <label class="shift-helper-v2__field">
          <span>Время</span>
          <input data-testid="journal-time" type="time" step="60" disabled>
        </label>
        <label class="shift-helper-v2__field shift-helper-v2__field--type">
          <span>Тип события</span>
          <select data-testid="journal-event-type" disabled></select>
        </label>
        <label class="shift-helper-v2__report">
          <input data-testid="journal-report" type="checkbox" disabled>
          <span>В утренний рапорт</span>
        </label>
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
      date: requireElement<HTMLInputElement>(root, '[data-testid="journal-date"]'),
      time: requireElement<HTMLInputElement>(root, '[data-testid="journal-time"]'),
      eventType: requireElement<HTMLSelectElement>(root, '[data-testid="journal-event-type"]'),
      includeInReport: requireElement<HTMLInputElement>(root, '[data-testid="journal-report"]'),
      close: requireElement<HTMLButtonElement>(root, '[data-testid="journal-close"]'),
    },
  };
}

export function configureEventTypeOptions(
  select: HTMLSelectElement,
  eventTypes: readonly JournalEventTypeOption[]
): void {
  const fragment = document.createDocumentFragment();
  eventTypes.forEach(({ value, label }) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    fragment.append(option);
  });
  select.replaceChildren(fragment);
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
