import type { IWorkbookData } from '@univerjs/core';
import { LocaleType } from '@univerjs/presets';

import type {
  EditableJournalField,
  JournalDraftSnapshot,
  JournalRowSnapshot,
  JournalSnapshot,
} from './types';

export type CellValue = string | number;

export type JournalCellBinding =
  | { readonly kind: 'startDate' }
  | { readonly kind: 'startTime' }
  | { readonly kind: 'endDate' }
  | { readonly kind: 'endTime' }
  | { readonly kind: 'text'; readonly field: EditableJournalField }
  | { readonly kind: 'readonly' };

type JournalColumn = {
  readonly title: string;
  readonly width: number;
  readonly binding: JournalCellBinding;
  readonly value: (record: JournalRowSnapshot) => CellValue;
};

export const HEADER_ROW_INDEX = 0;

function formatDate(value: string | null): string {
  if (!value) return '';
  const [datePart] = value.split('T');
  const parts = datePart?.split('-');
  if (!parts || parts.length !== 3) return value;
  const [year, month, day] = parts;
  return `${day}.${month}.${year}`;
}

function formatTime(value: string | null): string {
  if (!value) return '';
  return value.split('T')[1]?.slice(0, 5) ?? '';
}

function formatDowntime(minutes: number | null): string {
  if (minutes === null) return '';
  const safeMinutes = Math.max(0, Math.trunc(minutes));
  const hours = Math.floor(safeMinutes / 60);
  const remainder = safeMinutes % 60;
  return `${String(hours).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
}

export const DISPLAY_COLUMNS: readonly JournalColumn[] = [
  {
    title: 'Дата останова',
    width: 104,
    binding: { kind: 'startDate' },
    value: (record) => formatDate(record.startAt),
  },
  {
    title: 'Время останова',
    width: 88,
    binding: { kind: 'startTime' },
    value: (record) => formatTime(record.startAt),
  },
  {
    title: '№ ВЭУ',
    width: 108,
    binding: { kind: 'text', field: 'assetLabel' },
    value: (record) => record.assetLabel,
  },
  {
    title: 'Описание события',
    width: 300,
    binding: { kind: 'text', field: 'description' },
    value: (record) => record.description,
  },
  {
    title: 'Причина',
    width: 230,
    binding: { kind: 'text', field: 'reason' },
    value: (record) => record.reason ?? '',
  },
  {
    title: 'Действия персонала',
    width: 260,
    binding: { kind: 'text', field: 'actions' },
    value: (record) => record.actions ?? '',
  },
  {
    title: 'Исполнитель',
    width: 170,
    binding: { kind: 'text', field: 'performer' },
    value: (record) => record.performer ?? '',
  },
  {
    title: 'Дата пуска',
    width: 104,
    binding: { kind: 'endDate' },
    value: (record) => formatDate(record.endAt),
  },
  {
    title: 'Время пуска',
    width: 88,
    binding: { kind: 'endTime' },
    value: (record) => formatTime(record.endAt),
  },
  {
    title: 'Простой',
    width: 94,
    binding: { kind: 'readonly' },
    value: (record) => formatDowntime(record.downtimeMinutes),
  },
  {
    title: 'Кто внёс запись',
    width: 180,
    binding: { kind: 'readonly' },
    value: (record) => record.enteredBy,
  },
  {
    title: 'Потери',
    width: 100,
    binding: { kind: 'readonly' },
    value: (record) => record.losses ?? '',
  },
];

export const RECORD_ID_COLUMN = DISPLAY_COLUMNS.length;
export const REVISION_COLUMN = DISPLAY_COLUMNS.length + 1;
const COLUMN_COUNT = DISPLAY_COLUMNS.length + 2;
const HEADER_STYLE_ID = 'journal-header';
const BODY_STYLE_ID = 'journal-body';

export function getCellBinding(columnIndex: number): JournalCellBinding | null {
  return DISPLAY_COLUMNS[columnIndex]?.binding ?? null;
}

export function getEditableField(columnIndex: number): EditableJournalField | null {
  const binding = getCellBinding(columnIndex);
  return binding?.kind === 'text' ? binding.field : null;
}

export function getDisplayValue(record: JournalRowSnapshot, columnIndex: number): CellValue {
  return DISPLAY_COLUMNS[columnIndex]?.value(record) ?? '';
}

function buildDisplayRow(record: JournalRowSnapshot): Record<number, object> {
  const row: Record<number, object> = {};
  DISPLAY_COLUMNS.forEach((column, columnIndex) => {
    const value = column.value(record);
    row[columnIndex] = {
      v: value,
      t: typeof value === 'number' ? 2 : 1,
      s: BODY_STYLE_ID,
    };
  });
  return row;
}

export function applyDraftToWorkbookRow(
  worksheet: any,
  rowIndex: number,
  draft: JournalDraftSnapshot
): void {
  DISPLAY_COLUMNS.forEach((_column, columnIndex) => {
    worksheet.getRange(rowIndex, columnIndex).setValue(getDisplayValue(draft, columnIndex));
  });
  worksheet.getRange(rowIndex, RECORD_ID_COLUMN).setValue(draft.clientId);
  worksheet.getRange(rowIndex, REVISION_COLUMN).setValue('');
}

function buildCellData(snapshot: JournalSnapshot): Record<number, Record<number, object>> {
  const cellData: Record<number, Record<number, object>> = {
    [HEADER_ROW_INDEX]: {},
  };

  DISPLAY_COLUMNS.forEach((column, columnIndex) => {
    cellData[HEADER_ROW_INDEX]![columnIndex] = {
      v: column.title,
      t: 1,
      s: HEADER_STYLE_ID,
    };
  });

  snapshot.records.forEach((record, recordIndex) => {
    const rowIndex = recordIndex + 1;
    const row = buildDisplayRow(record);
    row[RECORD_ID_COLUMN] = { v: record.id, t: 2 };
    row[REVISION_COLUMN] = { v: record.revision, t: 2 };
    cellData[rowIndex] = row;
  });

  return cellData;
}

function buildColumnData(): Record<number, { w: number; hd: 0 | 1 }> {
  const columnData: Record<number, { w: number; hd: 0 | 1 }> = {};
  DISPLAY_COLUMNS.forEach((column, columnIndex) => {
    columnData[columnIndex] = { w: column.width, hd: 0 };
  });
  columnData[RECORD_ID_COLUMN] = { w: 0, hd: 1 };
  columnData[REVISION_COLUMN] = { w: 0, hd: 1 };
  return columnData;
}

export function buildWorkbookData(snapshot: JournalSnapshot): IWorkbookData {
  const sheetId = 'event-journal-v2-sheet';
  const visibleRows = snapshot.records.length + 1;

  return {
    id: 'shift-helper-event-journal-v2',
    name: 'Журнал событий',
    appVersion: '0.25.1',
    locale: LocaleType.RU_RU,
    styles: {
      [HEADER_STYLE_ID]: {
        bl: 1,
        fs: 11,
        bg: { rgb: '#E8EEF7' },
        cl: { rgb: '#172033' },
        ht: 2,
        vt: 2,
        tb: 3,
      },
      [BODY_STYLE_ID]: {
        fs: 11,
        vt: 1,
        tb: 3,
      },
    },
    sheetOrder: [sheetId],
    sheets: {
      [sheetId]: {
        id: sheetId,
        name: 'ЖС',
        tabColor: '#2563EB',
        hidden: 0,
        rowCount: Math.max(visibleRows + 500, 500),
        columnCount: COLUMN_COUNT,
        zoomRatio: 1,
        freeze: {
          startRow: 1,
          startColumn: 3,
          ySplit: 1,
          xSplit: 3,
        },
        scrollTop: 0,
        scrollLeft: 0,
        defaultColumnWidth: 100,
        defaultRowHeight: 32,
        mergeData: [],
        cellData: buildCellData(snapshot),
        rowData: {
          [HEADER_ROW_INDEX]: { h: 42 },
        },
        columnData: buildColumnData(),
        showGridlines: 1,
        rowHeader: { width: 48, hidden: 0 },
        columnHeader: { height: 24, hidden: 0 },
        rightToLeft: 0,
      },
    },
  };
}
