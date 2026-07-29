import './dateControl.css';

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

function validIsoDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

function isoToDisplay(value: string): string {
  if (!validIsoDate(value)) return '';
  const [year, month, day] = value.split('-');
  return `${day}.${month}.${year}`;
}

function displayToIso(value: string): string | null {
  const trimmed = value.trim();
  if (validIsoDate(trimmed)) return trimmed;
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(trimmed);
  if (!match) return null;
  const iso = `${match[3]}-${match[2]}-${match[1]}`;
  return validIsoDate(iso) ? iso : null;
}

function maskDisplayDate(value: string): string {
  if (value.includes('-')) return value;
  const digits = value.replace(/\D/g, '').slice(0, 8);
  const day = digits.slice(0, 2);
  const month = digits.slice(2, 4);
  const year = digits.slice(4, 8);
  return [day, month, year].filter(Boolean).join('.');
}

function createLocalizedDateControl(root: ParentNode): HTMLInputElement {
  const display = requireElement<HTMLInputElement>(root, '[data-testid="journal-date"]');
  const valueInput = requireElement<HTMLInputElement>(
    root,
    '[data-testid="journal-date-value"]'
  );
  const openButton = requireElement<HTMLButtonElement>(
    root,
    '[data-testid="journal-date-open"]'
  );

  const synchronizeDisplay = (): void => {
    display.value = isoToDisplay(valueInput.value);
    display.setCustomValidity('');
    display.removeAttribute('aria-invalid');
  };

  const commitDisplay = (): void => {
    if (!display.value.trim()) {
      valueInput.value = '';
      valueInput.dispatchEvent(new Event('change', { bubbles: true }));
      synchronizeDisplay();
      return;
    }
    const iso = displayToIso(display.value);
    if (iso === null) {
      display.setCustomValidity('Введите дату в формате ДД.ММ.ГГГГ.');
      display.setAttribute('aria-invalid', 'true');
      display.reportValidity();
      return;
    }
    valueInput.value = iso;
    synchronizeDisplay();
    valueInput.dispatchEvent(new Event('change', { bubbles: true }));
  };

  display.addEventListener('input', () => {
    display.value = maskDisplayDate(display.value);
    display.setCustomValidity('');
    display.removeAttribute('aria-invalid');
  });
  display.addEventListener('change', commitDisplay);
  display.addEventListener('blur', () => {
    if (display.validity.valid) {
      synchronizeDisplay();
    }
  });
  valueInput.addEventListener('input', synchronizeDisplay);
  valueInput.addEventListener('change', synchronizeDisplay);
  openButton.addEventListener('click', () => {
    if (typeof valueInput.showPicker === 'function') {
      valueInput.showPicker();
    } else {
      valueInput.click();
    }
  });

  return new Proxy(valueInput, {
    get(target, property): unknown {
      const value = Reflect.get(target, property, target);
      return typeof value === 'function' ? value.bind(target) : value;
    },
    set(target, property, value): boolean {
      const result = Reflect.set(target, property, value, target);
      if (property === 'value') synchronizeDisplay();
      if (property === 'disabled') {
        const disabled = Boolean(value);
        display.disabled = disabled;
        openButton.disabled = disabled;
      }
      return result;
    },
  }) as HTMLInputElement;
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
          <span class="shift-helper-v2__date-control">
            <input
              data-testid="journal-date"
              class="shift-helper-v2__date-display"
              type="text"
              inputmode="numeric"
              autocomplete="off"
              maxlength="10"
              placeholder="дд.мм.гггг"
              aria-label="Дата события в формате день, месяц, год"
              disabled
            >
            <button
              data-testid="journal-date-open"
              class="shift-helper-v2__date-open"
              type="button"
              aria-label="Открыть календарь"
              title="Открыть календарь"
              disabled
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M7 2v3M17 2v3M3.5 9h17M5.5 4.5h13a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2v-12a2 2 0 0 1 2-2Z" />
              </svg>
            </button>
            <input
              data-testid="journal-date-value"
              class="shift-helper-v2__date-native"
              type="date"
              tabindex="-1"
              aria-hidden="true"
              disabled
            >
          </span>
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
      date: createLocalizedDateControl(root),
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
