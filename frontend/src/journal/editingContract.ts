import { DISPLAY_COLUMNS, HEADER_ROW_INDEX, RECORD_ID_COLUMN } from './buildWorkbook';
import type { EditorControls } from './shell';
import type { JournalEventTypeOption } from './types';

const DRAFT_PREFIX = 'draft:';
const DATE_COLUMN = 1;
const TIME_COLUMN = 2;
const TYPE_COLUMN = 4;
const SPECIAL_COLUMNS = new Set([DATE_COLUMN, TIME_COLUMN, TYPE_COLUMN]);
const MAX_SCAN_ROW = 600;

type Worksheet = any;
type UniverApi = any;
type PendingEdit = {
  worksheet: Worksheet;
  row: number;
  column: number;
  previousValue: unknown;
};

function isDraft(value: unknown): value is string {
  return typeof value === 'string' && value.startsWith(DRAFT_PREFIX);
}

function hasIdentity(worksheet: Worksheet, row: number): boolean {
  const value = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
  return (typeof value === 'number' && Number.isInteger(value) && value > 0) || isDraft(value);
}

function findDraftRow(worksheet: Worksheet): number | null {
  for (let row = 1; row < MAX_SCAN_ROW; row += 1) {
    if (isDraft(worksheet.getRange(row, RECORD_ID_COLUMN).getValue())) return row;
  }
  return null;
}

function markDraft(worksheet: Worksheet): number | null {
  const row = findDraftRow(worksheet);
  if (row === null) {
    delete document.documentElement.dataset.draftRow;
    return null;
  }
  document.documentElement.dataset.draftRow = String(row);
  const marker = worksheet.getRange(row, 0);
  if (marker.getValue() !== '＋') marker.setValue('＋');
  return row;
}

function parseDate(value: unknown): string | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    const date = new Date(Date.UTC(1899, 11, 30) + Math.floor(value) * 86_400_000);
    return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}`;
  }
  const text = String(value ?? '').trim();
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  const display = /^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$/.exec(text);
  const year = Number(iso?.[1] ?? display?.[3]);
  const month = Number(iso?.[2] ?? display?.[2]);
  const day = Number(iso?.[3] ?? display?.[1]);
  if (!year || !month || !day) return null;
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

function parseTime(value: unknown): string | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    const fraction = ((value % 1) + 1) % 1;
    const minutes = Math.round(fraction * 1440) % 1440;
    return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
  }
  const match = /^(\d{1,2}):(\d{2})(?::\d{2})?$/.exec(String(value ?? '').trim());
  if (!match || Number(match[1]) > 23 || Number(match[2]) > 59) return null;
  return `${String(Number(match[1])).padStart(2, '0')}:${match[2]}`;
}

function resolveType(value: unknown, eventTypes: readonly JournalEventTypeOption[]): JournalEventTypeOption | null {
  const normalized = String(value ?? '').trim().toLocaleLowerCase('ru-RU');
  return eventTypes.find((item) => item.value.toLocaleLowerCase('ru-RU') === normalized || item.label.toLocaleLowerCase('ru-RU') === normalized) ?? null;
}

function setStatus(status: HTMLElement, message: string, error = false): void {
  status.dataset.editingContract = error ? 'error' : 'notice';
  status.classList.toggle('shift-helper-v2__status--error', error);
  status.textContent = message;
}

function clearStatus(status: HTMLElement): void {
  if (!status.dataset.editingContract) return;
  delete status.dataset.editingContract;
  status.classList.remove('shift-helper-v2__status--error');
  status.textContent = 'Строка выбрана · изменения сохраняются автоматически';
}

function selectDraft(univerAPI: UniverApi, worksheet: Worksheet, clickedRow: number, column: number, status: HTMLElement): void {
  const draftRow = findDraftRow(worksheet);
  if (draftRow === null) {
    setStatus(status, 'Нет активной строки для новой записи.', true);
    return;
  }
  const targetColumn = Math.max(0, Math.min(column, DISPLAY_COLUMNS.length - 1));
  worksheet.getRange(draftRow, targetColumn).activate?.();
  univerAPI.fireEvent(univerAPI.Event.CellClicked, { row: draftRow, column: targetColumn, worksheet });
  setStatus(status, `Строка ${clickedRow + 1} пока не активна. Продолжайте новую запись в строке ${draftRow + 1}.`, true);
}

function change(control: HTMLInputElement | HTMLSelectElement): void {
  control.dispatchEvent(new Event('change', { bubbles: true }));
}

export function startJournalEditingContract(
  univerAPI: UniverApi,
  status: HTMLElement,
  controls: EditorControls,
  eventTypes: readonly JournalEventTypeOption[]
): void {
  let pending: PendingEdit | null = null;
  let marking = false;
  let initialized = false;

  const queueMarker = (worksheet: Worksheet | null = univerAPI.getActiveWorkbook?.()?.getActiveSheet?.() ?? null): void => {
    if (!worksheet || marking) return;
    marking = true;
    window.setTimeout(() => {
      try {
        const draftRow = markDraft(worksheet);
        if (draftRow !== null && !initialized) {
          initialized = true;
          worksheet.getRange(draftRow, 3).activate?.();
          univerAPI.fireEvent(univerAPI.Event.CellClicked, { row: draftRow, column: 3, worksheet });
          setStatus(status, `Новая запись: заполните строку ${draftRow + 1}. Дата, время и тип редактируются прямо в таблице.`);
        }
      } finally {
        marking = false;
      }
    }, 0);
  };

  univerAPI.addEvent(univerAPI.Event.BeforeSheetEditStart, (params: any) => {
    const { row, column, worksheet } = params;
    if (!worksheet || row === HEADER_ROW_INDEX) return;
    if (!hasIdentity(worksheet, row)) {
      params.cancel = true;
      selectDraft(univerAPI, worksheet, row, column, status);
      return;
    }
    if (!SPECIAL_COLUMNS.has(column)) {
      clearStatus(status);
      return;
    }
    pending = { worksheet, row, column, previousValue: worksheet.getRange(row, column).getValue() };
    params.cancel = false;
    clearStatus(status);
  });

  univerAPI.addEvent(univerAPI.Event.SheetEditEnded, ({ row, column, worksheet }: any) => {
    queueMarker(worksheet);
    if (!worksheet || !SPECIAL_COLUMNS.has(column) || !hasIdentity(worksheet, row)) return;
    const previous = pending?.worksheet === worksheet && pending.row === row && pending.column === column
      ? pending.previousValue
      : worksheet.getRange(row, column).getValue();
    pending = null;
    const value = worksheet.getRange(row, column).getValue();
    univerAPI.fireEvent(univerAPI.Event.CellClicked, { row, column, worksheet });

    if (column === DATE_COLUMN) {
      const date = parseDate(value);
      if (!date) {
        worksheet.getRange(row, column).setValue(previous);
        setStatus(status, 'Дата не сохранена. Используйте формат ДД.ММ.ГГГГ.', true);
        return;
      }
      controls.date.value = date;
      change(controls.date);
      return;
    }
    if (column === TIME_COLUMN) {
      const time = parseTime(value);
      if (!time) {
        worksheet.getRange(row, column).setValue(previous);
        setStatus(status, 'Время не сохранено. Используйте формат ЧЧ:ММ.', true);
        return;
      }
      controls.time.value = time;
      change(controls.time);
      return;
    }
    const eventType = resolveType(value, eventTypes);
    if (!eventType) {
      worksheet.getRange(row, column).setValue(previous);
      setStatus(status, `Тип события не сохранён. Допустимые значения: ${eventTypes.map((item) => item.label).join(', ')}.`, true);
      return;
    }
    controls.eventType.value = eventType.value;
    change(controls.eventType);
  });

  univerAPI.addEvent(univerAPI.Event.CellClicked, ({ row, column, worksheet }: any) => {
    if (!worksheet || row === HEADER_ROW_INDEX) return;
    queueMarker(worksheet);
    if (!hasIdentity(worksheet, row)) selectDraft(univerAPI, worksheet, row, column, status);
    else clearStatus(status);
  });

  univerAPI.addEvent(univerAPI.Event.SelectionChanged, ({ worksheet }: any) => {
    if (!worksheet) return;
    queueMarker(worksheet);
    const current = worksheet.getSelection?.()?.getCurrentCell?.();
    if (current && current.actualRow !== HEADER_ROW_INDEX && !hasIdentity(worksheet, current.actualRow)) {
      selectDraft(univerAPI, worksheet, current.actualRow, current.actualColumn, status);
    }
  });

  [controls.date, controls.time, controls.eventType, controls.includeInReport].forEach((control) =>
    control.addEventListener('change', () => queueMarker())
  );
  queueMarker();
  document.documentElement.dataset.editingContract = 'active';
}
