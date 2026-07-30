import {
  EDITOR_ACTIVATED,
  FOCUSING_COMMON_DRAWINGS,
  FOCUSING_SHEET,
} from '@univerjs/core';
import { SheetsSelectionsService } from '@univerjs/sheets';

import './clearSelection.css';

import { deleteRecords, loadSnapshot, patchRecordsBatch } from './api';
import {
  DISPLAY_COLUMNS,
  HEADER_ROW_INDEX,
  RECORD_ID_COLUMN,
  getCellBinding,
} from './buildWorkbook';
import type {
  JournalBatchOperation,
  JournalDeleteOperation,
  JournalPatchField,
} from './types';

const MAX_ROWS = 200;
const DELETE_KEY_CODE = 46;
const DELETE_SHORTCUT_PRIORITY = 10_000;
const ROW_HEADER_WIDTH = 48;
const GRID_HEADER_HEIGHT = 80;
const DRAFT_ID_PREFIX = 'draft:';
const DRAFT_CLEAR_EVENT = 'shift-helper:draft-clear';
const ROW_DELETE_KEY_EVENT = 'shift-helper:row-delete-key';
const CLEAR_CONTENT_COMMAND = 'sheet.command.clear-selection-content';
const CLEAR_COMMANDS = new Set([
  CLEAR_CONTENT_COMMAND,
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

type ContextReader = {
  getContextValue: (key: unknown) => unknown;
};

type ShortcutServiceFacade = {
  _shortcutService?: {
    registerShortcut?: (shortcut: object) => unknown;
  };
};

type RowDeleteKeyDetail = {
  handled: boolean;
  wholeRowIntent: boolean;
};

export function installJournalDeleteCapture(): void {
  const html = document.documentElement;
  if (html.dataset.rowDeleteCaptureInstalled === 'true') return;

  window.addEventListener(
    'pointerdown',
    (event) => {
      const sheet = document.querySelector<HTMLElement>('#univer-sheet');
      const rect = sheet?.getBoundingClientRect();
      const rowHeaderIntent = Boolean(
        rect &&
        event.clientX >= rect.left &&
        event.clientX < rect.left + ROW_HEADER_WIDTH &&
        event.clientY >= rect.top + GRID_HEADER_HEIGHT &&
        event.clientY <= rect.bottom
      );
      html.dataset.rowDeleteHeaderIntent = rowHeaderIntent ? 'true' : 'false';
    },
    true
  );

  window.addEventListener(
    'keydown',
    (event) => {
      if (event.key !== 'Delete') return;
      if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return;

      html.dataset.rowDeleteCaptureSeen = 'true';
      const detail: RowDeleteKeyDetail = {
        handled: false,
        wholeRowIntent: html.dataset.rowDeleteHeaderIntent === 'true',
      };
      window.dispatchEvent(new CustomEvent(ROW_DELETE_KEY_EVENT, { detail }));
      if (!detail.handled) return;

      html.dataset.rowDeleteCaptureHandled = 'true';
      html.dataset.rowDeleteHeaderIntent = 'false';
      event.preventDefault();
      event.stopImmediatePropagation();
    },
    true
  );
  html.dataset.rowDeleteCaptureInstalled = 'true';
}

function positiveInteger(value: unknown): number | null {
  if (typeof value === 'number' && Number.isInteger(value) && value > 0) return value;
  if (typeof value === 'string' && /^\d+$/.test(value)) return Number(value);
  return null;
}

function isDraft(value: unknown): boolean {
  return typeof value === 'string' && value.startsWith(DRAFT_ID_PREFIX);
}

function isTextEditorTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement;
}

function sheetSelectionFocused(contextService: ContextReader): boolean {
  return Boolean(contextService.getContextValue(FOCUSING_SHEET)) &&
    !Boolean(contextService.getContextValue(EDITOR_ACTIVATED)) &&
    !Boolean(contextService.getContextValue(FOCUSING_COMMON_DRAWINGS)) &&
    !isTextEditorTarget(document.activeElement);
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
  const countedStartRow = Number(candidate.startRow);
  const countedStartColumn = Number(candidate.startColumn);
  const rowCount = Number(candidate.rowCount);
  const columnCount = Number(candidate.columnCount);
  if (
    Number.isInteger(countedStartRow) &&
    Number.isInteger(countedStartColumn) &&
    Number.isInteger(rowCount) &&
    Number.isInteger(columnCount) &&
    rowCount > 0 &&
    columnCount > 0
  ) {
    return {
      startRow: countedStartRow,
      startColumn: countedStartColumn,
      rowCount,
      columnCount,
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

function selectionRanges(univerAPI: any, explicit?: unknown): unknown[] {
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

async function currentRevisions(recordIds: readonly number[]): Promise<Map<number, number>> {
  const requested = new Set(recordIds);
  const snapshot = await loadSnapshot();
  return new Map(
    snapshot.records
      .filter((record) => requested.has(record.id))
      .map((record) => [record.id, record.revision])
  );
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
    window.dispatchEvent(new CustomEvent(DRAFT_CLEAR_EVENT, { detail: { rows } }));
  };

  const deleteRows = async (worksheet: any, range: ResolvedRange): Promise<void> => {
    const recordIds: number[] = [];
    const drafts: DraftClearRow[] = [];
    for (let offset = 0; offset < range.rowCount; offset += 1) {
      const row = range.startRow + offset;
      const identity = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
      const recordId = positiveInteger(identity);
      if (recordId !== null) recordIds.push(recordId);
      else if (isDraft(identity)) drafts.push({ row, fields: [], deleteRow: true });
    }
    if (recordIds.length === 0 && drafts.length === 0) {
      show('Выбранные строки уже пусты.');
      return;
    }
    if (recordIds.length === 0) {
      dispatchDraftClear(drafts);
      show('Черновые строки очищены.');
      return;
    }

    busy = true;
    show(recordIds.length === 1 ? 'Удаление строки…' : `Удаление строк: ${recordIds.length}…`);
    try {
      const revisions = await currentRevisions(recordIds);
      const operations: JournalDeleteOperation[] = recordIds.map((recordId) => {
        const revision = revisions.get(recordId);
        if (revision === undefined) throw new Error(`Запись №${recordId} уже отсутствует.`);
        return { recordId, revision };
      });
      await deleteRecords({ operations });
      dispatchDraftClear(drafts);
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

    const recordIds: number[] = [];
    let hasDraft = false;
    for (let rowOffset = 0; rowOffset < range.rowCount; rowOffset += 1) {
      const row = range.startRow + rowOffset;
      const identity = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
      const recordId = positiveInteger(identity);
      if (recordId !== null) recordIds.push(recordId);
      else if (isDraft(identity)) hasDraft = true;
    }

    if (hasDraft && recordIds.length > 0) {
      show('Нельзя одной операцией очищать сохранённые строки и черновики.', true);
      return;
    }
    if (hasDraft) {
      dispatchDraftClear(clearDraftCells(worksheet, range, fields));
      show('Выбранные ячейки черновика очищены.');
      return;
    }
    if (recordIds.length === 0) {
      show('Выбранные ячейки уже пусты.');
      return;
    }

    busy = true;
    show(
      recordIds.length === 1
        ? 'Очистка выбранных ячеек…'
        : `Очистка диапазона: ${recordIds.length} строк…`
    );
    try {
      const revisions = await currentRevisions(recordIds);
      const operations: JournalBatchOperation[] = recordIds.map((recordId) => {
        const revision = revisions.get(recordId);
        if (revision === undefined) throw new Error(`Запись №${recordId} уже отсутствует.`);
        const changes: JournalBatchOperation['changes'] = {};
        fields.forEach((field) => {
          changes[field] = field === 'assetLabel' || field === 'description' ? '' : null;
        });
        return { recordId, revision, changes };
      });
      await patchRecordsBatch({ operations });
      window.location.reload();
    } catch (error) {
      busy = false;
      show(`Ячейки не очищены: ${error instanceof Error ? error.message : String(error)}`, true);
    }
  };

  const executeClear = (explicitRanges?: unknown): void => {
    if (busy) return;
    const worksheet = univerAPI.getActiveWorkbook?.()?.getActiveSheet?.();
    const ranges = selectionRanges(univerAPI, explicitRanges);
    document.documentElement.dataset.clearRangeCount = String(ranges.length);
    if (!worksheet || ranges.length !== 1) {
      show('Не удалось однозначно определить выбранный диапазон.', true);
      return;
    }
    const range = resolveRange(ranges[0]);
    if (range) document.documentElement.dataset.clearResolvedRange = JSON.stringify(range);
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
    if (wholeRows) void deleteRows(worksheet, range);
    else void clearCells(worksheet, range);
  };

  window.addEventListener(ROW_DELETE_KEY_EVENT, (event) => {
    const request = event as CustomEvent<RowDeleteKeyDetail>;
    const ranges = selectionRanges(univerAPI);
    const range = ranges.length === 1 ? resolveRange(ranges[0]) : null;
    if (range) {
      document.documentElement.dataset.rowDeleteCaptureRange = JSON.stringify(range);
    }
    const wholeRows = Boolean(
      range &&
      (request.detail.wholeRowIntent ||
        (range.startColumn === 0 && range.columnCount >= DISPLAY_COLUMNS.length))
    );
    if (!range || !wholeRows) return;

    request.detail.handled = true;
    const rowRange: ResolvedRange = {
      startRow: range.startRow,
      startColumn: 0,
      rowCount: range.rowCount,
      columnCount: DISPLAY_COLUMNS.length,
    };
    executeClear([rowRange]);
  });

  document.addEventListener(
    'keydown',
    (event) => {
      if (event.key !== 'Delete' && event.key !== 'Backspace') return;
      document.documentElement.dataset.clearLastKey = event.key;
      document.documentElement.dataset.clearKeyTarget =
        event.target instanceof HTMLElement ? event.target.tagName : 'unknown';
      if (event.ctrlKey || event.metaKey || event.altKey || event.isComposing) return;
      if (isTextEditorTarget(event.target)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      executeClear();
    },
    true
  );

  univerAPI.addEvent(univerAPI.Event.BeforeCommandExecute, (event: any) => {
    if (!CLEAR_COMMANDS.has(event.id)) return;
    event.cancel = true;
    executeClear(event?.params?.ranges);
  });

  const shortcutFacade = univerAPI.getShortcut?.() as ShortcutServiceFacade | undefined;
  shortcutFacade?._shortcutService?.registerShortcut?.({
    id: CLEAR_CONTENT_COMMAND,
    description: 'Удалить выбранные данные журнала',
    priority: DELETE_SHORTCUT_PRIORITY,
    binding: DELETE_KEY_CODE,
    preconditions: sheetSelectionFocused,
  });

  document.documentElement.dataset.clearSelection = 'approved-js';
}
