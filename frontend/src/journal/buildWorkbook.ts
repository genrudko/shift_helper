import type { IWorkbookData } from '@univerjs/core';
import { LocaleType } from '@univerjs/presets';

import type { JournalEventSnapshot, JournalSnapshot } from './types';

type CellValue = string | number;

type JournalColumn = {
  readonly title: string;
  readonly width: number;
  readonly value: (record: JournalEventSnapshot, visualIndex: number) => CellValue;
};

const DISPLAY_COLUMNS: readonly JournalColumn[] = [
  { title: '№', width: 56, value: (_record, index) => index + 1 },
  { title: 'Дата', width: 92, value: (record) => formatDate(record.startAt) },
  { title: 'Время', width: 72, value: (record) => formatTime(record.startAt) },
  { title: 'Оборудование', width: 150, value: (record) => record.assetLabel },
  { title: 'Тип события', width: 150, value: (record) => record.eventTypeLabel },
  { title: 'Описание', width: 300, value: (record) => record.description },
  { title: 'Причина', width: 240, value: (record) => record.reason ?? '' },
  { title: 'Принятые меры', width: 260, value: (record) => record.actions ?? '' },
  { title: 'Исполнитель', width: 170, value: (record) => record.performer ?? '' },
  { title: 'Код ошибки', width: 110, value: (record) => record.errorCodes ?? '' },
  { title: 'Ограничение', width: 110, value: (record) => formatDecimal(record.rotorLimit) },
  { title: 'P ремонт, МВт', width: 120, value: (record) => formatDecimal(record.repairPowerMw) },
  { title: 'Состояние', width: 110, value: (record) => record.status === 'open' ? 'Открыто' : 'Завершено' },
  { title: 'Окончание', width: 132, value: (record) => formatDateTime(record.endAt) },
];

const RECORD_ID_COLUMN = DISPLAY_COLUMNS.length;
const REVISION_COLUMN = DISPLAY_COLUMNS.length + 1;
const COLUMN_COUNT = DISPLAY_COLUMNS.length + 2;
const HEADER_STYLE_ID = 'journal-header';
const BODY_STYLE_ID = 'journal-body';

function formatDate(value: string): string {
  const [datePart] = value.split('T');
  const parts = datePart?.split('-');
  if (!parts || parts.length !== 3) return value;
  const [year, month, day] = parts;
  return `${day}.${month}.${year}`;
}

function formatTime(value: string): string {
  const timePart = value.split('T')[1];
  return timePart?.slice(0, 5) ?? '';
}

function formatDateTime(value: string | null): string {
  if (value === null) return '';
  return `${formatDate(value)} ${formatTime(value)}`.trim();
}

function formatDecimal(value: string | null): string {
  return value?.replace('.', ',') ?? '';
}

function buildCellData(snapshot: JournalSnapshot): Record<number, Record<number, object>> {
  const cellData: Record<number, Record<number, object>> = {
    0: {},
  };

  DISPLAY_COLUMNS.forEach((column, columnIndex) => {
    cellData[0]![columnIndex] = {
      v: column.title,
      t: 1,
      s: HEADER_STYLE_ID,
    };
  });

  snapshot.records.forEach((record, recordIndex) => {
    const rowIndex = recordIndex + 1;
    const row: Record<number, object> = {};

    DISPLAY_COLUMNS.forEach((column, columnIndex) => {
      const value = column.value(record, recordIndex);
      row[columnIndex] = {
        v: value,
        t: typeof value === 'number' ? 2 : 1,
        s: BODY_STYLE_ID,
      };
    });

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
    locale: LocaleType.EN_US,
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
        name: 'Журнал событий',
        tabColor: '#2563EB',
        hidden: 0,
        rowCount: Math.max(visibleRows + 200, 500),
        columnCount: COLUMN_COUNT,
        zoomRatio: 1,
        freeze: {
          startRow: 1,
          startColumn: 1,
          ySplit: 1,
          xSplit: 1,
        },
        scrollTop: 0,
        scrollLeft: 0,
        defaultColumnWidth: 100,
        defaultRowHeight: 32,
        mergeData: [],
        cellData: buildCellData(snapshot),
        rowData: {
          0: { h: 36 },
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
