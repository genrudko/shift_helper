import { SheetsSelectionsService } from '@univerjs/sheets';

import './clearSelection.css';

import { deleteRecords, patchRecordsBatch } from './api';
import {
  DISPLAY_COLUMNS,
  HEADER_ROW_INDEX,
  RECORD_ID_COLUMN,
  REVISION_COLUMN,
  getCellBinding,
} from './buildWorkbook';
import type {
  JournalBatchOperation,
  JournalDeleteOperation,
  JournalPatchField,
} from './types';

const MAX_ROWS = 200;
const DRAFT_ID_PREFIX = 'draft:';
const DRAFT_CLEAR_EVENT = 'shift-helper:draft-clear';
const CLEAR_COMMANDS = new Set([
  'sheet.command.clear-selection-content',
  'sheet.command.clear-selection-all',
]);

type ResolvedRange = {
  startRow: number;
  startColumn: number;
  rowCount: number;
  columnCount: number;
};

type DraftClearRow = {
  row: number;
  fields: JournalPatchField[];
  deleteRow?: boolean;
};

function positiveInteger(value: unknown): number | null {
  if (typeof value === 'number' && Number.isInteger(value) && value > 0) return value;
  if (typeof value === 'string' && /^\d+$/.test(value)) return Number(value);
  return null;
}

function isDraft(value: unknown): boolean {
  return typeof value === 'string' && value.startsWith(DRAFT_ID_PREFIX);
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
  const explicit = event?.params?.ranges;
  if (Array.isArray(explicit) && explicit.length > 0) return explicit;
  try {
    const service = univerAPI?._injector?.get?.(SheetsSelectionsService) as
      | SheetsSelectionsService
      | undefined;
    const selections = service?.getCurrentSelections?.();
    if (Array.isArray(selections) && selections.length > 0) {
      return selections.map((selection) => selection.range);
    }
  } catch {
    // Public facade fallback below.
  }
  const worksheet = univerAPI.getActiveWorkbook?.()?.getActiveSheet?.();
  const activeRange = worksheet?.getSelection?.()?.getActiveRange?.();
  return activeRange ? [activeRange] : [];
}

function clearFields(startColumn: number, columnCount: number): JournalPatchField[] | null {
  const fields = new Set<JournalPatchField>();
  for (let offset = 0; offset < columnCount; offset += 1) {
    const binding = getCellBinding(startColumn + offset);
    if (!binding || binding.kind === 'readonly') return null;
    if (binding.kind === 'startDate' || binding.kind === 'startTime') return null;
    if (binding.kind === 'endDate' || binding.kind === 'endTime') {
      fields.add('endAt');
    } else {
      fields.add(binding.field);
    }
  }
  return [...fields];
}

function clearDraftCells(
  worksheet: any,
  range: ResolvedRange,
  fields: JournalPatchField[]
): DraftClearRow[] {
  const rows: DraftClearRow[] = [];
  for (let rowOffset = 0; rowOffset < range.rowCount; rowOffset += 1) {
    const row = range.startRow + rowOffset;
    const identity = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
    if (!isDraft(identity)) continue;
    for (let columnOffset = 0; columnOffset < range.columnCount; columnOffset += 1) {
      const column = range.startColumn + columnOffset;
      const binding = getCellBinding(column);
      if (binding?.kind === 'endDate' || binding?.kind === 'endTime') {
        worksheet.getRange(row, 7).setValue('');
        worksheet.getRange(row, 8).setValue('');
      } else {
        worksheet.getRange(row, column).setValue('');
      }
    }
    rows.push({ row, fields });
  }
  return rows;
}

export function startJournalClearSelection(
  univerAPI: any,
  status: HTMLElement
): void {
  let busy = false;

  const show = (message: string, error = false): void => {
    status.dataset.clearState = error ? 'error' : 'saving';
    status.classList.toggle('shift-helper-v2__status--error', error);
    status.textContent = message;
  };

  const dispatchDraftClear = (rows: DraftClearRow[]): void => {
    if (rows.length === 0) return;
    window.dispatchEvent(
      new CustomEvent(DRAFT_CLEAR_EVENT, { detail: { rows } })
    );
  };

  const deleteRows = async (worksheet: any, range: ResolvedRange): Promise<void> => {
    const saved: JournalDeleteOperation[] = [];
    const drafts: DraftClearRow[] = [];
    for (let offset = 0; offset < range.rowCount; offset += 1) {
      const row = range.startRow + offset;
      const identity = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
      const recordId = positiveInteger(identity);
      const revision = positiveInteger(worksheet.getRange(row, REVISION_COLUMN).getValue());
      if (recordId !== null && revision !== null) {
        saved.push({ recordId, revision });
      } else if (isDraft(identity)) {
        drafts.push({ row, fields: [], deleteRow: true });
      }
    }
    if (saved.length === 0 && drafts.length === 0) {
      show('Выбранные строки уже пусты.', false);
      return;
    }
    dispatchDraftClear(drafts);
    if (saved.length === 0) {
      show('Черновые строки очищены.', false);
      return;
    }
    busy = true;
    show(saved.length === 1 ? 'Удаление строки…' : `Удаление строк: ${saved.length}…`);
    try {
      await deleteRecords({ operations: saved });
      window.location.reload();
    } catch (error) {
      busy = false;
      show(`Строки не удалены: ${error instanceof Error ? error.message : String(error)}`, true);
    }
  };

  const clearCells = async (worksheet: any, range: ResolvedRange): Promise<void> => {
    const fields = clearFields(range.startColumn, range.columnCount);
    if (fields === null) {
      show(
        'Диапазон содержит дату/время останова или вычисляемую графу. Эти ячейки не очищены.',
        true
      );
      return;
    }

    const operations: JournalBatchOperation[] = [];
    let hasDraft = false;
    for (let rowOffset = 0; rowOffset < range.rowCount; rowOffset += 1) {
      const row = range.startRow + rowOffset;
      const identity = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
      const recordId = positiveInteger(identity);
      const revision = positiveInteger(worksheet.getRange(row, REVISION_COLUMN).getValue());
      if (recordId !== null && revision !== null) {
        const changes: JournalBatchOperation['changes'] = {};
        fields.forEach((field) => {
          changes[field] = field === 'assetLabel' || field === 'description' ? '' : null;
        });
        operations.push({ recordId, revision, changes });
      } else if (isDraft(identity)) {
        hasDraft = true;
      }
    }

    const draftRows = clearDraftCells(worksheet, range, fields);
    dispatchDraftClear(draftRows);
    if (operations.length === 0) {
      show(hasDraft ? 'Выбранные ячейки черновика очищены.' : 'Выбранные ячейки уже пусты.');
      return;
    }
    if (hasDraft) {
      show('Нельзя одной операцией очищать сохранённые строки и черновики.', true);
      return;
    }

    busy = true;
    show(
      operations.length === 1
        ? 'Очистка выбранных ячеек…'
        : `Очистка диапазона: ${operations.length} строк…`
    );
    try {
      await patchRecordsBatch({ operations });
      window.location.reload();
    } catch (error) {
      busy = false;
      show(`Ячейки не очищены: ${error instanceof Error ? error.message : String(error)}`, true);
    }
  };

  univerAPI.addEvent(univerAPI.Event.BeforeCommandExecute, (event: any) => {
    if (!CLEAR_COMMANDS.has(event.id)) return;
    event.cancel = true;
    if (busy) return;
    const worksheet = univerAPI.getActiveWorkbook?.()?.getActiveSheet?.();
    const ranges = commandRanges(univerAPI, event);
    if (!worksheet || ranges.length !== 1) {
      show('Не удалось однозначно определить выбранный диапазон.', true);
      return;
    }
    const range = resolveRange(ranges[0]);
    if (!range || range.rowCount < 1 || range.columnCount < 1) {
      show('Выбран некорректный диапазон.', true);
      return;
    }
    if (range.startRow <= HEADER_ROW_INDEX) {
      show('Заголовок журнала удалить нельзя.', true);
      return;
    }
    if (range.rowCount > MAX_ROWS) {
      show(`За одну операцию допускается не более ${MAX_ROWS} строк.`, true);
      return;
    }

    const wholeRows =
      range.startColumn === 0 && range.columnCount >= DISPLAY_COLUMNS.length;
    if (wholeRows) {
      void deleteRows(worksheet, range);
    } else {
      void clearCells(worksheet, range);
    }
  });

  document.documentElement.dataset.clearSelection = 'approved-js';
}
