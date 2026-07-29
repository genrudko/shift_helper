import type { IWorkbookData } from '@univerjs/core';

import {
  JournalPresentationConflictError,
  savePresentation,
} from './api';
import type {
  JournalPresentationPayload,
  JournalPresentationState,
  JournalPresentationStyle,
} from './types';

const SAVE_DELAY_MS = 700;
const MAX_PERSISTED_ROWS = 5_000;

type SnapshotRecord = Record<string, any>;

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function activeSheet(snapshot: SnapshotRecord): SnapshotRecord | null {
  const sheetId = Array.isArray(snapshot.sheetOrder) ? snapshot.sheetOrder[0] : null;
  if (typeof sheetId !== 'string') return null;
  const sheet = snapshot.sheets?.[sheetId];
  return sheet && typeof sheet === 'object' ? sheet : null;
}

function numericEntries(
  value: unknown,
  maximum: number
): Array<[string, SnapshotRecord]> {
  if (!value || typeof value !== 'object') return [];
  return Object.entries(value as SnapshotRecord).filter(([key, settings]) => {
    const index = Number(key);
    return (
      Number.isInteger(index) &&
      index >= 0 &&
      index < maximum &&
      settings !== null &&
      typeof settings === 'object'
    );
  }) as Array<[string, SnapshotRecord]>;
}

function projectDimensions(
  value: unknown,
  maximum: number,
  sizeKey: 'w' | 'h'
): Record<string, Record<string, number>> {
  const result: Record<string, Record<string, number>> = {};
  numericEntries(value, maximum).forEach(([index, settings]) => {
    const projected: Record<string, number> = {};
    const size = settings[sizeKey];
    if (typeof size === 'number' && Number.isFinite(size)) projected[sizeKey] = size;
    const hidden = settings.hd;
    if (hidden === 0 || hidden === 1 || typeof hidden === 'boolean') {
      projected.hd = hidden ? 1 : 0;
    }
    if (Object.keys(projected).length > 0) result[index] = projected;
  });
  return result;
}

function projectCellStyles(
  cellData: unknown,
  visibleColumnCount: number
): Record<string, Record<string, JournalPresentationStyle>> {
  const result: Record<string, Record<string, JournalPresentationStyle>> = {};
  numericEntries(cellData, MAX_PERSISTED_ROWS).forEach(([row, columns]) => {
    const rowStyles: Record<string, JournalPresentationStyle> = {};
    numericEntries(columns, visibleColumnCount).forEach(([column, cell]) => {
      const style = cell.s;
      if (typeof style === 'string') {
        rowStyles[column] = style;
      } else if (style && typeof style === 'object') {
        rowStyles[column] = cloneJson(style as Record<string, unknown>);
      }
    });
    if (Object.keys(rowStyles).length > 0) result[row] = rowStyles;
  });
  return result;
}

function projectFreeze(value: unknown): JournalPresentationPayload['sheet']['freeze'] {
  const freeze = value && typeof value === 'object' ? (value as SnapshotRecord) : {};
  const integer = (key: string, fallback: number): number => {
    const candidate = freeze[key];
    return typeof candidate === 'number' && Number.isInteger(candidate)
      ? candidate
      : fallback;
  };
  return {
    startRow: integer('startRow', 1),
    startColumn: integer('startColumn', 1),
    ySplit: integer('ySplit', 1),
    xSplit: integer('xSplit', 1),
  };
}

export function projectPresentation(
  snapshot: IWorkbookData,
  visibleColumnCount: number
): JournalPresentationPayload {
  const raw = snapshot as SnapshotRecord;
  const sheet = activeSheet(raw);
  if (!sheet) throw new Error('Не найден активный лист для сохранения оформления.');

  const zoomRatio =
    typeof sheet.zoomRatio === 'number' && Number.isFinite(sheet.zoomRatio)
      ? sheet.zoomRatio
      : 1;
  return {
    schemaVersion: 1,
    workbookStyles:
      raw.styles && typeof raw.styles === 'object'
        ? cloneJson(raw.styles as Record<string, unknown>)
        : {},
    sheet: {
      zoomRatio,
      freeze: projectFreeze(sheet.freeze),
      columnData: projectDimensions(sheet.columnData, visibleColumnCount, 'w'),
      rowData: projectDimensions(sheet.rowData, MAX_PERSISTED_ROWS, 'h'),
      cellStyles: projectCellStyles(sheet.cellData, visibleColumnCount),
    },
  };
}

export function applyPresentation(
  workbookData: IWorkbookData,
  state: JournalPresentationState,
  visibleColumnCount: number
): IWorkbookData {
  const workbook = workbookData as SnapshotRecord;
  const stored = state.presentation;
  workbook.styles = {
    ...(workbook.styles ?? {}),
    ...cloneJson(stored.workbookStyles),
  };
  const sheet = activeSheet(workbook);
  if (!sheet) return workbookData;

  sheet.zoomRatio = stored.sheet.zoomRatio;
  sheet.freeze = cloneJson(stored.sheet.freeze);
  sheet.columnData = {
    ...(sheet.columnData ?? {}),
    ...Object.fromEntries(
      Object.entries(stored.sheet.columnData).filter(
        ([key]) => Number(key) < visibleColumnCount
      )
    ),
  };
  sheet.rowData = {
    ...(sheet.rowData ?? {}),
    ...cloneJson(stored.sheet.rowData),
  };
  sheet.cellData = sheet.cellData ?? {};
  Object.entries(stored.sheet.cellStyles).forEach(([row, columns]) => {
    const rowIndex = Number(row);
    if (!Number.isInteger(rowIndex) || rowIndex < 0 || rowIndex >= MAX_PERSISTED_ROWS) return;
    sheet.cellData[row] = sheet.cellData[row] ?? {};
    Object.entries(columns).forEach(([column, style]) => {
      const columnIndex = Number(column);
      if (
        !Number.isInteger(columnIndex) ||
        columnIndex < 0 ||
        columnIndex >= visibleColumnCount
      ) {
        return;
      }
      sheet.cellData[row][column] = {
        ...(sheet.cellData[row][column] ?? {}),
        s: cloneJson(style),
      };
    });
  });
  return workbookData;
}

export function startPresentationPersistence(
  univerAPI: any,
  workbook: any,
  initialState: JournalPresentationState,
  visibleColumnCount: number,
  status: HTMLElement
): void {
  let state = initialState;
  let lastFingerprint = JSON.stringify(
    projectPresentation(workbook.save(), visibleColumnCount)
  );
  let timer: number | null = null;
  let saveInFlight = false;
  let saveAgain = false;

  const exposeState = (value: 'saved' | 'saving' | 'conflict' | 'error'): void => {
    status.dataset.presentationState = value;
    document.documentElement.dataset.presentationRevision = String(state.revision);
  };

  const flush = async (): Promise<void> => {
    timer = null;
    const presentation = projectPresentation(workbook.save(), visibleColumnCount);
    const fingerprint = JSON.stringify(presentation);
    if (fingerprint === lastFingerprint) return;
    if (saveInFlight) {
      saveAgain = true;
      return;
    }

    saveInFlight = true;
    exposeState('saving');
    try {
      state = await savePresentation({
        revision: state.revision,
        presentation,
      });
      lastFingerprint = JSON.stringify(state.presentation);
      status.title = 'Оформление и геометрия таблицы сохранены.';
      exposeState('saved');
    } catch (error) {
      if (error instanceof JournalPresentationConflictError) {
        state = error.current;
        lastFingerprint = JSON.stringify(state.presentation);
        status.title = `${error.message} Обновите страницу перед продолжением оформления.`;
        exposeState('conflict');
      } else {
        const message = error instanceof Error ? error.message : String(error);
        status.title = `Оформление не сохранено: ${message}`;
        exposeState('error');
      }
    } finally {
      saveInFlight = false;
      if (saveAgain) {
        saveAgain = false;
        window.setTimeout(() => void flush(), 0);
      }
    }
  };

  const schedule = (): void => {
    if (timer !== null) window.clearTimeout(timer);
    timer = window.setTimeout(() => void flush(), SAVE_DELAY_MS);
  };

  exposeState('saved');
  univerAPI.onCommandExecuted(() => schedule());
}
