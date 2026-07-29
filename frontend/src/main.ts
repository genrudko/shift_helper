import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import sheetsCoreEnUS from '@univerjs/preset-sheets-core/locales/en-US';
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';

import '@univerjs/preset-sheets-core/lib/index.css';
import './styles.css';

import {
  DISPLAY_COLUMNS,
  HEADER_ROW_INDEX,
  RECORD_ID_COLUMN,
  REVISION_COLUMN,
  buildWorkbookData,
  getDisplayValue,
  getEditableField,
} from './journal/buildWorkbook';
import type {
  EditableJournalField,
  JournalApiErrorBody,
  JournalEventSnapshot,
  JournalPatchRequest,
  JournalPatchResponse,
  JournalSnapshot,
} from './journal/types';

const SNAPSHOT_ENDPOINT = '/events/api/v2/snapshot';
const RECORD_ENDPOINT = '/events/api/v2/records';

class JournalApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly current?: JournalEventSnapshot
  ) {
    super(message);
  }
}

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

async function patchRecord(
  recordId: number,
  payload: JournalPatchRequest
): Promise<JournalEventSnapshot> {
  const response = await fetch(`${RECORD_ENDPOINT}/${recordId}`, {
    method: 'PATCH',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    credentials: 'same-origin',
    body: JSON.stringify(payload),
  });

  const body: unknown = await response.json();
  if (!response.ok) {
    const apiError = body as JournalApiErrorBody;
    throw new JournalApiError(
      apiError.error?.message ?? `Сервер вернул HTTP ${response.status}.`,
      response.status,
      apiError.error?.code ?? 'unknown_error',
      apiError.error?.current
    );
  }

  const patch = body as JournalPatchResponse;
  if (patch.schemaVersion !== 1 || typeof patch.record?.id !== 'number') {
    throw new Error('Сервер вернул неподдерживаемый результат сохранения.');
  }
  return patch.record;
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

function numericCellValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isInteger(value) && value > 0) return value;
  if (typeof value === 'string' && /^\d+$/.test(value)) return Number(value);
  return null;
}

function editableCellValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  return String(value);
}

function startEditingPersistence(
  univerAPI: ReturnType<typeof createUniver>['univerAPI'],
  snapshot: JournalSnapshot,
  status: HTMLElement
): void {
  const recordsById = new Map(snapshot.records.map((record) => [record.id, record]));
  const saveQueues = new Map<number, Promise<void>>();
  const maximumScanRow = Math.max(snapshot.records.length + 200, 500);
  let pendingSaveCount = 0;

  const setReadyStatus = (): void => {
    const recordCount = new Intl.NumberFormat('ru-RU').format(recordsById.size);
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent = `Загружено записей: ${recordCount} · все изменения сохранены`;
  };

  const setSavingStatus = (): void => {
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent =
      pendingSaveCount > 1 ? `Сохранение изменений: ${pendingSaveCount}…` : 'Сохранение изменения…';
  };

  const setErrorStatus = (message: string): void => {
    status.classList.add('shift-helper-v2__status--error');
    status.textContent = message;
  };

  const findRecordRow = (worksheet: any, recordId: number): number | null => {
    for (let row = 1; row < maximumScanRow; row += 1) {
      const value = numericCellValue(worksheet.getRange(row, RECORD_ID_COLUMN).getValue());
      if (value === recordId) return row;
    }
    return null;
  };

  const applyRecordToRow = (worksheet: any, row: number, record: JournalEventSnapshot): void => {
    DISPLAY_COLUMNS.forEach((_column, columnIndex) => {
      worksheet.getRange(row, columnIndex).setValue(getDisplayValue(record, columnIndex, row - 1));
    });
    worksheet.getRange(row, RECORD_ID_COLUMN).setValue(record.id);
    worksheet.getRange(row, REVISION_COLUMN).setValue(record.revision);
  };

  const restoreRecord = (worksheet: any, record: JournalEventSnapshot): void => {
    const currentRow = findRecordRow(worksheet, record.id);
    if (currentRow !== null) applyRecordToRow(worksheet, currentRow, record);
  };

  const enqueueSave = (recordId: number, task: () => Promise<void>): void => {
    const previous = saveQueues.get(recordId) ?? Promise.resolve();
    const next = previous
      .catch(() => undefined)
      .then(task)
      .finally(() => {
        if (saveQueues.get(recordId) === next) saveQueues.delete(recordId);
      });
    saveQueues.set(recordId, next);
  };

  univerAPI.addEvent(univerAPI.Event.BeforeSheetEditStart, (params) => {
    const { row, column, worksheet } = params;
    const recordId = numericCellValue(worksheet.getRange(row, RECORD_ID_COLUMN).getValue());
    if (
      row === HEADER_ROW_INDEX ||
      recordId === null ||
      !recordsById.has(recordId) ||
      getEditableField(column) === null
    ) {
      params.cancel = true;
    }
  });

  univerAPI.addEvent(univerAPI.Event.SheetEditEnded, ({ row, column, worksheet }) => {
    const field = getEditableField(column);
    const recordId = numericCellValue(worksheet.getRange(row, RECORD_ID_COLUMN).getValue());
    if (field === null || recordId === null) return;

    const value = editableCellValue(worksheet.getRange(row, column).getValue());
    const existing = recordsById.get(recordId);
    if (!existing || value === String(getDisplayValue(existing, column, row - 1))) return;

    enqueueSave(recordId, async () => {
      const current = recordsById.get(recordId);
      if (!current) return;

      pendingSaveCount += 1;
      setSavingStatus();
      try {
        const changes: Partial<Record<EditableJournalField, string | null>> = {
          [field]: value,
        };
        const updated = await patchRecord(recordId, {
          revision: current.revision,
          changes,
        });
        recordsById.set(recordId, updated);
        restoreRecord(worksheet, updated);
      } catch (error) {
        if (error instanceof JournalApiError && error.current) {
          recordsById.set(recordId, error.current);
          restoreRecord(worksheet, error.current);
          setErrorStatus(`Конфликт сохранения: ${error.message}`);
        } else {
          restoreRecord(worksheet, current);
          const message = error instanceof Error ? error.message : String(error);
          setErrorStatus(`Изменение не сохранено: ${message}`);
        }
      } finally {
        pendingSaveCount -= 1;
        if (pendingSaveCount === 0 && !status.classList.contains('shift-helper-v2__status--error')) {
          setReadyStatus();
        } else if (pendingSaveCount > 0) {
          setSavingStatus();
        }
      }
    });
  });

  setReadyStatus();
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

    startEditingPersistence(univerAPI, snapshot, status);
    univerAPI.createWorkbook(buildWorkbookData(snapshot));
  } catch (error) {
    renderFailure(root, error);
  }
}

void start();
