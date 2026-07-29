import { SheetsSelectionsService } from '@univerjs/sheets';

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
const CLEAR_COMMANDS = new Set([
  'sheet.command.clear-selection-content',
  'sheet.command.clear-selection-all',
]);
const CLEARABLE_FIELDS = new Set<EditableJournalField>([
  'reason',
  'actions',
  'performer',
  'errorCodes',
  'rotorLimit',
]);

type ResolvedRange = {
  startRow: number;
  startColumn: number;
  rowCount: number;
  columnCount: number;
};

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

function resolveRange(value: unknown): ResolvedRange | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Record<string, unknown>;

  if (
    typeof candidate.getRow === 'function' &&
    typeof candidate.getColumn === 'function' &&
    typeof candidate.getNumRows === 'function' &&
    typeof candidate.getNumColumns === 'function'
  ) {
    return {
      startRow: Number((candidate.getRow as () => unknown)()),
      startColumn: Number((candidate.getColumn as () => unknown)()),
      rowCount: Number((candidate.getNumRows as () => unknown)()),
      columnCount: Number((candidate.getNumColumns as () => unknown)()),
    };
  }

  const startRow = Number(candidate.startRow);
  const endRow = Number(candidate.endRow);
  const startColumn = Number(candidate.startColumn);
  const endColumn = Number(candidate.endColumn);
  if (
    !Number.isInteger(startRow) ||
    !Number.isInteger(endRow) ||
    !Number.isInteger(startColumn) ||
    !Number.isInteger(endColumn) ||
    endRow < startRow ||
    endColumn < startColumn
  ) {
    return null;
  }
  return {
    startRow,
    startColumn,
    rowCount: endRow - startRow + 1,
    columnCount: endColumn - startColumn + 1,
  };
}

function commandRanges(univerAPI: any, event: any): unknown[] {
  const explicitRanges = event?.params?.ranges;
  if (Array.isArray(explicitRanges) && explicitRanges.length > 0) {
    return explicitRanges;
  }

  try {
    const injector = univerAPI?._injector;
    const selectionService = injector?.get?.(SheetsSelectionsService) as
      | SheetsSelectionsService
      | undefined;
    const selections = selectionService?.getCurrentSelections?.();
    if (Array.isArray(selections) && selections.length > 0) {
      return selections.map((selection) => selection.range);
    }
  } catch {
    // Fall through to the public facade as a compatibility fallback.
  }

  const worksheet = univerAPI.getActiveWorkbook?.()?.getActiveSheet?.();
  const activeRange = worksheet?.getSelection?.()?.getActiveRange?.();
  return activeRange ? [activeRange] : [];
}

export function startJournalClearSelection(
  univerAPI: any,
  status: HTMLElement
): void {
  let clearing = false;
  const html = document.documentElement;

  const setStatus = (
    state: 'saving' | 'error',
    message: string
  ): void => {
    status.dataset.clearState = state;
    status.classList.toggle('shift-helper-v2__status--error', state === 'error');
    status.textContent = message;
  };

  const clearResolvedRange = async (
    worksheet: any,
    range: ResolvedRange | null
  ): Promise<void> => {
    if (clearing) return;
    if (!worksheet || !range) {
      setStatus('error', 'Не удалось определить диапазон для очистки.');
      return;
    }

    const { startRow, startColumn, rowCount, columnCount } = range;
    html.dataset.clearResolvedRange = JSON.stringify(range);
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

    html.dataset.clearOperationCount = String(operations.length);
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
      html.dataset.clearBatchResult = 'success';
      window.location.reload();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      html.dataset.clearBatchResult = `error:${message}`;
      clearing = false;
      setStatus('error', `Диапазон не очищен: ${message}`);
    }
  };

  document.addEventListener(
    'keydown',
    (event) => {
      html.dataset.clearLastKey = event.key;
      html.dataset.clearLastKeyTarget =
        event.target instanceof Element ? event.target.tagName : 'unknown';
    },
    true
  );

  univerAPI.addEvent(univerAPI.Event.SelectionChanged, (event: any) => {
    try {
      html.dataset.clearLastSelection = JSON.stringify(event.selections ?? null);
    } catch {
      html.dataset.clearLastSelection = 'unserializable';
    }
  });

  univerAPI.addEvent(univerAPI.Event.BeforeCommandExecute, (event: any) => {
    html.dataset.clearLastCommand = String(event.id ?? 'unknown');
    if (!CLEAR_COMMANDS.has(event.id)) return;

    const worksheet = univerAPI.getActiveWorkbook?.()?.getActiveSheet?.();
    const ranges = commandRanges(univerAPI, event);
    html.dataset.clearCommandRangeCount = String(ranges.length);
    if (ranges.length !== 1) {
      event.cancel = true;
      html.dataset.clearIntercepted = 'true';
      setStatus(
        'error',
        ranges.length === 0
          ? 'Не удалось определить диапазон для очистки.'
          : 'Очистка нескольких несмежных диапазонов пока недоступна.'
      );
      return;
    }

    const range = resolveRange(ranges[0]);
    html.dataset.clearSelectionResolvedBeforeCancel = String(Boolean(range));
    event.cancel = true;
    html.dataset.clearIntercepted = 'true';
    void clearResolvedRange(worksheet, range);
  });

  html.dataset.clearSelection = 'active';
}
