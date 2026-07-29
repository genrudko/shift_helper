import './clearSelection.css';

import { patchRecordsBatch } from './api';
import {
  HEADER_ROW_INDEX,
  RECORD_ID_COLUMN,
  REVISION_COLUMN,
  getEditableField,
} from './buildWorkbook';
import type {
  EditableJournalField,
  JournalBatchOperation,
} from './types';

const MAX_CLEAR_ROWS = 200;
const CLEARABLE_FIELDS = new Set<EditableJournalField>([
  'reason',
  'actions',
  'performer',
  'errorCodes',
  'rotorLimit',
]);

function positiveInteger(value: unknown): number | null {
  if (typeof value === 'number' && Number.isInteger(value) && value > 0) {
    return value;
  }
  if (typeof value === 'string' && /^\d+$/.test(value)) {
    const parsed = Number(value);
    return parsed > 0 ? parsed : null;
  }
  return null;
}

function displayValue(value: unknown): string {
  return value === null || value === undefined ? '' : String(value);
}

export function startJournalClearSelection(
  univerAPI: any,
  status: HTMLElement
): void {
  let clearing = false;
  let sheetEditing = false;

  const setStatus = (
    state: 'saving' | 'error',
    message: string
  ): void => {
    status.dataset.clearState = state;
    status.classList.toggle('shift-helper-v2__status--error', state === 'error');
    status.textContent = message;
  };

  const clearActiveRange = async (): Promise<void> => {
    if (clearing || sheetEditing) return;
    const worksheet = univerAPI.getActiveWorkbook?.()?.getActiveSheet?.();
    const range = worksheet?.getActiveRange?.();
    if (!worksheet || !range) {
      setStatus('error', 'Не удалось определить диапазон для очистки.');
      return;
    }

    const startRow = range.getRow();
    const startColumn = range.getColumn();
    const rowCount = range.getNumRows();
    const columnCount = range.getNumColumns();
    if (
      !Number.isInteger(startRow) ||
      !Number.isInteger(startColumn) ||
      !Number.isInteger(rowCount) ||
      !Number.isInteger(columnCount) ||
      rowCount < 1 ||
      columnCount < 1
    ) {
      setStatus('error', 'Выбран некорректный диапазон. Данные не изменены.');
      return;
    }
    if (startRow === HEADER_ROW_INDEX || startRow < 1) {
      setStatus('error', 'Заголовок журнала очищать нельзя. Данные не изменены.');
      return;
    }
    if (rowCount > MAX_CLEAR_ROWS) {
      setStatus(
        'error',
        `За одну операцию можно очистить не более ${MAX_CLEAR_ROWS} строк.`
      );
      return;
    }

    const columns: Array<{ index: number; field: EditableJournalField }> = [];
    for (let offset = 0; offset < columnCount; offset += 1) {
      const columnIndex = startColumn + offset;
      const field = getEditableField(columnIndex);
      if (field === null || !CLEARABLE_FIELDS.has(field)) {
        setStatus(
          'error',
          'Диапазон содержит обязательную или защищённую колонку. Данные не изменены.'
        );
        return;
      }
      columns.push({ index: columnIndex, field });
    }

    const operations: JournalBatchOperation[] = [];
    for (let offset = 0; offset < rowCount; offset += 1) {
      const row = startRow + offset;
      const recordId = positiveInteger(
        worksheet.getRange(row, RECORD_ID_COLUMN).getValue()
      );
      const revision = positiveInteger(
        worksheet.getRange(row, REVISION_COLUMN).getValue()
      );
      if (recordId === null || revision === null) {
        setStatus(
          'error',
          'Очистка поддерживается только для сохранённых строк. Данные не изменены.'
        );
        return;
      }

      const changes: Partial<Record<EditableJournalField, string | null>> = {};
      columns.forEach(({ index, field }) => {
        const current = displayValue(worksheet.getRange(row, index).getValue());
        if (current !== '') changes[field] = '';
      });
      if (Object.keys(changes).length > 0) {
        operations.push({ recordId, revision, changes });
      }
    }

    if (operations.length === 0) {
      status.dataset.clearState = 'idle';
      status.classList.remove('shift-helper-v2__status--error');
      status.textContent = 'Выбранные ячейки уже пусты.';
      return;
    }

    clearing = true;
    setStatus(
      'saving',
      operations.length === 1
        ? 'Очистка выбранных ячеек…'
        : `Очистка диапазона: ${operations.length} строк…`
    );
    try {
      await patchRecordsBatch({ operations });
      window.location.reload();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      clearing = false;
      setStatus('error', `Диапазон не очищен: ${message}`);
    }
  };

  univerAPI.addEvent(univerAPI.Event.SheetEditStarted, () => {
    sheetEditing = true;
  });
  univerAPI.addEvent(univerAPI.Event.SheetEditEnded, () => {
    sheetEditing = false;
  });

  document.addEventListener(
    'keydown',
    (event) => {
      if (
        event.isComposing ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        sheetEditing ||
        (event.key !== 'Delete' && event.key !== 'Backspace')
      ) {
        return;
      }
      event.preventDefault();
      event.stopImmediatePropagation();
      void clearActiveRange();
    },
    true
  );

  document.documentElement.dataset.clearSelection = 'active';
}
