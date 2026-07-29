import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import sheetsCoreEnUS from '@univerjs/preset-sheets-core/locales/en-US';
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';

import '@univerjs/preset-sheets-core/lib/index.css';
import './styles.css';

import { buildWorkbookData } from './journal/buildWorkbook';
import type { JournalSnapshot } from './journal/types';

const SNAPSHOT_ENDPOINT = '/events/api/v2/snapshot';

function requireRoot(): HTMLElement {
  const root = document.querySelector<HTMLElement>('#app');
  if (!root) {
    throw new Error('Не найден контейнер Journal UI V2.');
  }
  return root;
}

function renderShell(root: HTMLElement): { sheetHost: HTMLElement; status: HTMLElement } {
  root.innerHTML = `
    <section class="shift-helper-v2">
      <header class="shift-helper-v2__header">
        <div class="shift-helper-v2__title">
          <strong>Журнал событий</strong>
          <span>Journal UI V2 · Univer Sheets OSS</span>
        </div>
        <span class="shift-helper-v2__status" role="status">Загрузка данных…</span>
      </header>
      <div id="univer-sheet" class="shift-helper-v2__sheet"></div>
    </section>
  `;

  const sheetHost = root.querySelector<HTMLElement>('#univer-sheet');
  const status = root.querySelector<HTMLElement>('.shift-helper-v2__status');
  if (!sheetHost || !status) {
    throw new Error('Не удалось создать контейнер Univer Sheets.');
  }
  return { sheetHost, status };
}

async function loadSnapshot(): Promise<JournalSnapshot> {
  const response = await fetch(SNAPSHOT_ENDPOINT, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  });
  if (!response.ok) {
    throw new Error(`Сервер вернул HTTP ${response.status}.`);
  }

  const data: unknown = await response.json();
  if (
    typeof data !== 'object' ||
    data === null ||
    !('schemaVersion' in data) ||
    data.schemaVersion !== 1 ||
    !('records' in data) ||
    !Array.isArray(data.records)
  ) {
    throw new Error('Сервер вернул неподдерживаемый формат журнала.');
  }
  return data as JournalSnapshot;
}

function renderFailure(root: HTMLElement, error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  root.innerHTML = `
    <section class="shift-helper-v2__error" role="alert">
      <strong>Journal UI V2 не запущен.</strong><br>
      ${escapeHtml(message)}
    </section>
  `;
}

function escapeHtml(value: string): string {
  const element = document.createElement('span');
  element.textContent = value;
  return element.innerHTML;
}

async function start(): Promise<void> {
  document.documentElement.lang = 'ru';
  const root = requireRoot();
  const { status } = renderShell(root);

  try {
    const snapshot = await loadSnapshot();
    const { univerAPI } = createUniver({
      locale: LocaleType.EN_US,
      locales: {
        [LocaleType.EN_US]: mergeLocales(sheetsCoreEnUS),
      },
      presets: [
        UniverSheetsCorePreset({
          container: 'univer-sheet',
        }),
      ],
    });

    univerAPI.addEvent(univerAPI.Event.LifeCycleChanged, ({ stage }) => {
      if (stage !== univerAPI.Enum.LifecycleStages.Rendered) return;

      const workbook = univerAPI.getActiveWorkbook();
      if (!workbook) return;

      const permission = workbook.getWorkbookPermission();
      permission.setReadOnly();
      permission.setPermissionDialogVisible(false);
    });

    univerAPI.createWorkbook(buildWorkbookData(snapshot));
    const recordCount = new Intl.NumberFormat('ru-RU').format(snapshot.records.length);
    status.textContent = `Загружено записей: ${recordCount} · режим первого среза: только чтение`;
  } catch (error) {
    renderFailure(root, error);
  }
}

void start();
