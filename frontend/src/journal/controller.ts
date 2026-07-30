import {
  DISPLAY_COLUMNS,
  HEADER_ROW_INDEX,
  RECORD_ID_COLUMN,
  REVISION_COLUMN,
  formatDate,
  formatTime,
  getCellBinding,
  getDisplayValue,
  getEditableField,
  type JournalCellBinding,
} from './buildWorkbook';
import {
  JournalApiError,
  closeRecord,
  createRecord,
  patchRecord,
  patchRecordsBatch,
} from './api';
import type { EditorControls } from './shell';
import type {
  EditableJournalField,
  JournalBatchOperation,
  JournalCreateRequest,
  JournalDraftSnapshot,
  JournalEventSnapshot,
  JournalEventTypeOption,
  JournalPatchRequest,
  JournalSnapshot,
} from './types';

const DRAFT_ID_PREFIX = 'draft:';
let draftSequence = 0;

type WorksheetFacade = any;
type UniverApi = any;

type ActiveRow = {
  readonly worksheet: WorksheetFacade;
  readonly row: number;
  readonly identity: number | string | null;
};

type ParsedEdit =
  | { readonly ok: true; readonly draft: JournalDraftSnapshot; readonly changes: JournalPatchRequest['changes'] }
  | { readonly ok: false; readonly message: string };

function numericCellValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isInteger(value) && value > 0) return value;
  if (typeof value === 'string' && /^\d+$/.test(value)) return Number(value);
  return null;
}

function draftCellValue(value: unknown): string | null {
  return typeof value === 'string' && value.startsWith(DRAFT_ID_PREFIX) ? value : null;
}

function editableCellValue(value: unknown): string {
  return value === null || value === undefined ? '' : String(value);
}

function localMinuteIso(date = new Date()): string {
  const pad = (value: number): string => String(value).padStart(2, '0');
  return [
    date.getFullYear(),
    '-',
    pad(date.getMonth() + 1),
    '-',
    pad(date.getDate()),
    'T',
    pad(date.getHours()),
    ':',
    pad(date.getMinutes()),
  ].join('');
}

function createDraft(eventTypes: readonly JournalEventTypeOption[]): JournalDraftSnapshot {
  draftSequence += 1;
  const randomPart = Math.random().toString(36).slice(2, 10);
  const defaultType =
    eventTypes.find((option) => option.value === 'other') ??
    eventTypes[0] ??
    ({ value: 'other', label: 'Другое' } satisfies JournalEventTypeOption);
  return {
    clientId: `${DRAFT_ID_PREFIX}${Date.now().toString(36)}-${draftSequence.toString(36)}-${randomPart}`,
    startAt: localMinuteIso(),
    endAt: null,
    assetLabel: '',
    eventType: defaultType.value,
    eventTypeLabel: defaultType.label,
    description: '',
    reason: null,
    actions: null,
    performer: null,
    errorCodes: null,
    rotorLimit: null,
    repairPowerMw: null,
    status: 'open',
    includeInReport: true,
  };
}

function emptyToNull(value: string | null): string | null {
  return value?.trim() ? value : null;
}

function draftCreateRequest(draft: JournalDraftSnapshot): JournalCreateRequest {
  return {
    clientId: draft.clientId,
    values: {
      startAt: draft.startAt,
      assetLabel: draft.assetLabel,
      eventType: draft.eventType,
      description: draft.description,
      reason: emptyToNull(draft.reason),
      actions: emptyToNull(draft.actions),
      performer: emptyToNull(draft.performer),
      errorCodes: emptyToNull(draft.errorCodes),
      rotorLimit: emptyToNull(draft.rotorLimit),
      includeInReport: draft.includeInReport,
    },
  };
}

function draftIsComplete(draft: JournalDraftSnapshot): boolean {
  return Boolean(draft.assetLabel.trim() && draft.description.trim());
}

function splitStartAt(startAt: string): { date: string; time: string } {
  const [date = '', rawTime = ''] = startAt.split('T');
  return { date, time: rawTime.slice(0, 5) };
}

function combineStartAt(date: string, time: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) {
    return null;
  }
  return `${date}T${time}`;
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
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }
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

function parseReportFlag(value: unknown): boolean | null {
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') {
    if (value === 1) return true;
    if (value === 0) return false;
  }
  const normalized = String(value ?? '').trim().toLocaleLowerCase('ru-RU');
  if (['да', 'yes', 'true', '1', '+'].includes(normalized)) return true;
  if (['нет', 'no', 'false', '0', '-'].includes(normalized)) return false;
  return null;
}

function resolveEventType(
  value: unknown,
  eventTypes: readonly JournalEventTypeOption[]
): JournalEventTypeOption | null {
  const normalized = String(value ?? '').trim().toLocaleLowerCase('ru-RU');
  return (
    eventTypes.find(
      (item) =>
        item.value.toLocaleLowerCase('ru-RU') === normalized ||
        item.label.toLocaleLowerCase('ru-RU') === normalized
    ) ?? null
  );
}

function parseClipboardMatrix(text: string): string[][] {
  const normalized = text.replace(/\r\n?/g, '\n');
  const withoutFinalNewline = normalized.endsWith('\n')
    ? normalized.slice(0, -1)
    : normalized;
  if (!withoutFinalNewline) return [];
  return withoutFinalNewline.split('\n').map((row) => row.split('\t'));
}

function normalizeTextField(field: EditableJournalField, value: string): string | null {
  if (field === 'assetLabel' || field === 'description') return value;
  return value.trim() ? value : null;
}

function parseDraftEdit(
  draft: JournalDraftSnapshot,
  binding: JournalCellBinding,
  value: unknown,
  eventTypes: readonly JournalEventTypeOption[]
): ParsedEdit {
  if (binding.kind === 'text') {
    const normalized = normalizeTextField(binding.field, editableCellValue(value));
    return {
      ok: true,
      draft: { ...draft, [binding.field]: normalized } as JournalDraftSnapshot,
      changes: { [binding.field]: normalized },
    };
  }

  if (binding.kind === 'date') {
    const date = parseDate(value);
    if (!date) return { ok: false, message: 'Дата не сохранена. Используйте формат ДД.ММ.ГГГГ.' };
    const { time } = splitStartAt(draft.startAt);
    const startAt = combineStartAt(date, time);
    if (!startAt) return { ok: false, message: 'Дата не сохранена: не удалось собрать дату и время.' };
    return { ok: true, draft: { ...draft, startAt }, changes: { startAt } };
  }

  if (binding.kind === 'time') {
    const time = parseTime(value);
    if (!time) return { ok: false, message: 'Время не сохранено. Используйте формат ЧЧ:ММ.' };
    const { date } = splitStartAt(draft.startAt);
    const startAt = combineStartAt(date, time);
    if (!startAt) return { ok: false, message: 'Время не сохранено: не удалось собрать дату и время.' };
    return { ok: true, draft: { ...draft, startAt }, changes: { startAt } };
  }

  if (binding.kind === 'eventType') {
    const eventType = resolveEventType(value, eventTypes);
    if (!eventType) {
      return {
        ok: false,
        message: `Тип события не сохранён. Допустимые значения: ${eventTypes
          .map((item) => item.label)
          .join(', ')}.`,
      };
    }
    return {
      ok: true,
      draft: { ...draft, eventType: eventType.value, eventTypeLabel: eventType.label },
      changes: { eventType: eventType.value },
    };
  }

  const includeInReport = parseReportFlag(value);
  if (includeInReport === null) {
    return { ok: false, message: 'Поле «В рапорт» принимает только «Да» или «Нет».' };
  }
  return {
    ok: true,
    draft: { ...draft, includeInReport },
    changes: { includeInReport },
  };
}

export function startJournalController(
  univerAPI: UniverApi,
  snapshot: JournalSnapshot,
  status: HTMLElement,
  controls: EditorControls
): void {
  const recordsById = new Map(snapshot.records.map((record) => [record.id, record]));
  const draftsById = new Map<string, JournalDraftSnapshot>();
  const saveQueues = new Map<string, Promise<void>>();
  const creatingDrafts = new Set<string>();
  const maximumScanRow = Math.max(snapshot.records.length + 600, 800);
  let pendingSaveCount = 0;
  let activeRow: ActiveRow | null = null;
  let batchInProgress = false;

  const setReadyStatus = (): void => {
    const recordCount = new Intl.NumberFormat('ru-RU').format(recordsById.size);
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent = `Загружено записей: ${recordCount} · изменения сохраняются автоматически`;
  };

  const setSavingStatus = (message?: string): void => {
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent =
      message ??
      (pendingSaveCount > 1
        ? `Сохранение изменений: ${pendingSaveCount}…`
        : 'Сохранение изменения…');
  };

  const setDraftStatus = (row: number): void => {
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent = `Черновик в строке ${row + 1}: для создания записи заполните оборудование и описание`;
  };

  const setErrorStatus = (message: string): void => {
    status.classList.add('shift-helper-v2__status--error');
    status.textContent = message;
  };

  const finishPendingOperation = (): void => {
    pendingSaveCount = Math.max(0, pendingSaveCount - 1);
    if (pendingSaveCount === 0 && !status.classList.contains('shift-helper-v2__status--error')) {
      setReadyStatus();
    } else if (pendingSaveCount > 0) {
      setSavingStatus();
    }
  };

  const rowIdentity = (worksheet: WorksheetFacade, row: number): number | string | null => {
    const value = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
    return numericCellValue(value) ?? draftCellValue(value);
  };

  const findRecordRow = (worksheet: WorksheetFacade, recordId: number): number | null => {
    for (let row = 1; row < maximumScanRow; row += 1) {
      if (numericCellValue(worksheet.getRange(row, RECORD_ID_COLUMN).getValue()) === recordId) {
        return row;
      }
    }
    return null;
  };

  const findDraftRow = (worksheet: WorksheetFacade, clientId: string): number | null => {
    for (let row = 1; row < maximumScanRow; row += 1) {
      if (draftCellValue(worksheet.getRange(row, RECORD_ID_COLUMN).getValue()) === clientId) {
        return row;
      }
    }
    return null;
  };

  const applyRecordToRow = (
    worksheet: WorksheetFacade,
    row: number,
    record: JournalEventSnapshot
  ): void => {
    DISPLAY_COLUMNS.forEach((_column, columnIndex) => {
      worksheet.getRange(row, columnIndex).setValue(getDisplayValue(record, columnIndex, row - 1));
    });
    worksheet.getRange(row, RECORD_ID_COLUMN).setValue(record.id);
    worksheet.getRange(row, REVISION_COLUMN).setValue(record.revision);
  };

  const applyDraftToRow = (
    worksheet: WorksheetFacade,
    row: number,
    draft: JournalDraftSnapshot
  ): void => {
    DISPLAY_COLUMNS.forEach((_column, columnIndex) => {
      worksheet.getRange(row, columnIndex).setValue(getDisplayValue(draft, columnIndex, row - 1));
    });
    worksheet.getRange(row, RECORD_ID_COLUMN).setValue(draft.clientId);
    worksheet.getRange(row, REVISION_COLUMN).setValue('');
  };

  const scheduleModelRender = (
    worksheet: WorksheetFacade,
    row: number,
    model: JournalEventSnapshot | JournalDraftSnapshot
  ): void => {
    window.setTimeout(() => {
      if ('id' in model) applyRecordToRow(worksheet, row, model);
      else applyDraftToRow(worksheet, row, model);
    }, 0);
  };

  const restoreRecord = (worksheet: WorksheetFacade, record: JournalEventSnapshot): void => {
    const currentRow = findRecordRow(worksheet, record.id);
    if (currentRow !== null) scheduleModelRender(worksheet, currentRow, record);
  };

  const syncSelectionContext = (worksheet: WorksheetFacade, row: number): void => {
    if (row === HEADER_ROW_INDEX) {
      activeRow = null;
      controls.selection.textContent = 'Заголовок таблицы';
      controls.close.disabled = true;
      controls.close.textContent = 'Завершить событие';
      return;
    }

    const identity = rowIdentity(worksheet, row);
    activeRow = { worksheet, row, identity };
    if (typeof identity === 'number') {
      const record = recordsById.get(identity);
      controls.selection.textContent = record ? `Событие №${record.id}` : `Строка ${row + 1}`;
      controls.close.disabled = batchInProgress || !record || record.status === 'closed';
      controls.close.textContent = record?.status === 'closed' ? 'Событие завершено' : 'Завершить событие';
      return;
    }
    if (typeof identity === 'string') {
      controls.selection.textContent = `Черновик · строка ${row + 1}`;
      controls.close.disabled = true;
      controls.close.textContent = 'Завершить событие';
      return;
    }
    controls.selection.textContent = `Пустая строка ${row + 1} · начните ввод в нужной ячейке`;
    controls.close.disabled = true;
    controls.close.textContent = 'Завершить событие';
  };

  const queueMatchesActiveRow = (queueKey: string): boolean => {
    if (!activeRow) return false;
    return typeof activeRow.identity === 'number'
      ? queueKey === `record:${activeRow.identity}`
      : queueKey === activeRow.identity;
  };

  const enqueueSave = (queueKey: string, task: () => Promise<void>): void => {
    const previous = saveQueues.get(queueKey) ?? Promise.resolve();
    const next = previous
      .catch(() => undefined)
      .then(task)
      .finally(() => {
        if (saveQueues.get(queueKey) === next) {
          saveQueues.delete(queueKey);
          if (queueMatchesActiveRow(queueKey) && activeRow) {
            syncSelectionContext(activeRow.worksheet, activeRow.row);
          }
          if (
            pendingSaveCount === 0 &&
            !status.classList.contains('shift-helper-v2__status--error')
          ) {
            setReadyStatus();
          }
        }
      });
    saveQueues.set(queueKey, next);
  };

  const handleRecordError = (
    worksheet: WorksheetFacade,
    current: JournalEventSnapshot,
    error: unknown,
    prefix: string
  ): void => {
    if (error instanceof JournalApiError && error.current) {
      recordsById.set(current.id, error.current);
      restoreRecord(worksheet, error.current);
      setErrorStatus(`Конфликт сохранения: ${error.message}`);
      return;
    }
    restoreRecord(worksheet, current);
    const message = error instanceof Error ? error.message : String(error);
    setErrorStatus(`${prefix}: ${message}`);
  };

  const enqueueRecordPatch = (
    recordId: number,
    worksheet: WorksheetFacade,
    changes: JournalPatchRequest['changes']
  ): void => {
    enqueueSave(`record:${recordId}`, async () => {
      const current = recordsById.get(recordId);
      if (!current || Object.keys(changes).length === 0) return;
      pendingSaveCount += 1;
      setSavingStatus();
      try {
        const updated = await patchRecord(recordId, { revision: current.revision, changes });
        recordsById.set(recordId, updated);
        restoreRecord(worksheet, updated);
      } catch (error) {
        handleRecordError(worksheet, current, error, 'Изменение не сохранено');
      } finally {
        finishPendingOperation();
      }
    });
  };

  const enqueueRecordClose = (recordId: number, worksheet: WorksheetFacade): void => {
    enqueueSave(`record:${recordId}`, async () => {
      const current = recordsById.get(recordId);
      if (!current || current.status === 'closed') return;
      pendingSaveCount += 1;
      setSavingStatus();
      try {
        const updated = await closeRecord(recordId, { revision: current.revision });
        recordsById.set(recordId, updated);
        restoreRecord(worksheet, updated);
      } catch (error) {
        handleRecordError(worksheet, current, error, 'Событие не завершено');
      } finally {
        finishPendingOperation();
      }
    });
  };

  const materializeDraft = (worksheet: WorksheetFacade, row: number): JournalDraftSnapshot => {
    const existingIdentity = rowIdentity(worksheet, row);
    if (typeof existingIdentity === 'string') {
      const existing = draftsById.get(existingIdentity);
      if (existing) return existing;
    }
    const draft = createDraft(snapshot.eventTypes);
    draftsById.set(draft.clientId, draft);
    applyDraftToRow(worksheet, row, draft);
    activeRow = { worksheet, row, identity: draft.clientId };
    controls.selection.textContent = `Черновик · строка ${row + 1}`;
    controls.close.disabled = true;
    setDraftStatus(row);
    return draft;
  };

  const maybeCreateDraft = (draftId: string, worksheet: WorksheetFacade): void => {
    const draft = draftsById.get(draftId);
    if (!draft || !draftIsComplete(draft)) {
      const row = findDraftRow(worksheet, draftId);
      if (row !== null) setDraftStatus(row);
      return;
    }
    if (creatingDrafts.has(draftId) || batchInProgress) return;

    creatingDrafts.add(draftId);
    enqueueSave(draftId, async () => {
      pendingSaveCount += 1;
      setSavingStatus('Создание записи…');
      try {
        const currentDraft = draftsById.get(draftId);
        if (!currentDraft || !draftIsComplete(currentDraft)) return;
        const created = await createRecord(draftCreateRequest(currentDraft));
        const draftRow = findDraftRow(worksheet, draftId);
        draftsById.delete(draftId);
        recordsById.set(created.record.id, created.record);
        if (draftRow !== null) {
          applyRecordToRow(worksheet, draftRow, created.record);
          if (activeRow?.identity === draftId) {
            activeRow = { worksheet, row: draftRow, identity: created.record.id };
            syncSelectionContext(worksheet, draftRow);
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setErrorStatus(`Новая запись не сохранена: ${message}`);
      } finally {
        creatingDrafts.delete(draftId);
        finishPendingOperation();
      }
    });
  };

  const applyBatchPaste = async (
    worksheet: WorksheetFacade,
    startRow: number,
    startColumn: number,
    text: string
  ): Promise<void> => {
    if (batchInProgress || saveQueues.size > 0 || creatingDrafts.size > 0) {
      setErrorStatus('Дождитесь завершения текущего сохранения перед пакетной вставкой.');
      return;
    }
    const matrix = parseClipboardMatrix(text);
    if (matrix.length === 0) return;
    if (matrix.length > 200) {
      setErrorStatus('За одну пакетную вставку допускается не более 200 строк.');
      return;
    }

    const operations: JournalBatchOperation[] = [];
    for (let rowOffset = 0; rowOffset < matrix.length; rowOffset += 1) {
      const targetRow = startRow + rowOffset;
      const recordId = numericCellValue(
        worksheet.getRange(targetRow, RECORD_ID_COLUMN).getValue()
      );
      if (recordId === null) {
        setErrorStatus('Транзакционная вставка диапазона поддерживается только для сохранённых строк.');
        return;
      }
      const record = recordsById.get(recordId);
      if (!record) {
        setErrorStatus(`Не найдена сохранённая запись для строки ${targetRow + 1}.`);
        return;
      }

      const changes: Partial<Record<EditableJournalField, string | null>> = {};
      const values = matrix[rowOffset] ?? [];
      for (let columnOffset = 0; columnOffset < values.length; columnOffset += 1) {
        const targetColumn = startColumn + columnOffset;
        const field = getEditableField(targetColumn);
        if (field === null) {
          setErrorStatus('Диапазон вставки содержит специальную или защищённую колонку. Операция отменена.');
          return;
        }
        const value = values[columnOffset] ?? '';
        if (value !== String(getDisplayValue(record, targetColumn, targetRow - 1))) {
          changes[field] = normalizeTextField(field, value);
        }
      }
      if (Object.keys(changes).length > 0) {
        operations.push({ recordId, revision: record.revision, changes });
      }
    }
    if (operations.length === 0) {
      setReadyStatus();
      return;
    }

    batchInProgress = true;
    pendingSaveCount += 1;
    controls.close.disabled = true;
    setSavingStatus(`Пакетное сохранение: ${operations.length} строк…`);
    try {
      const updatedRecords = await patchRecordsBatch({ operations });
      updatedRecords.forEach((record) => {
        recordsById.set(record.id, record);
        restoreRecord(worksheet, record);
      });
      if (activeRow) syncSelectionContext(activeRow.worksheet, activeRow.row);
    } catch (error) {
      if (error instanceof JournalApiError && error.current) {
        recordsById.set(error.current.id, error.current);
        restoreRecord(worksheet, error.current);
      }
      const message = error instanceof Error ? error.message : String(error);
      setErrorStatus(`Пакетная вставка отменена: ${message}`);
    } finally {
      batchInProgress = false;
      if (activeRow) syncSelectionContext(activeRow.worksheet, activeRow.row);
      finishPendingOperation();
    }
  };

  controls.close.addEventListener('click', () => {
    if (!activeRow || typeof activeRow.identity !== 'number' || batchInProgress) return;
    const record = recordsById.get(activeRow.identity);
    if (record?.status === 'open') enqueueRecordClose(record.id, activeRow.worksheet);
  });

  univerAPI.addEvent(univerAPI.Event.BeforeSheetEditStart, (params: any) => {
    const { row, column, worksheet } = params;
    const binding = getCellBinding(column);
    if (!worksheet || batchInProgress || row === HEADER_ROW_INDEX || binding === null) {
      params.cancel = true;
      if (worksheet && row !== HEADER_ROW_INDEX && binding === null) {
        setErrorStatus('Эта колонка вычисляется автоматически или защищена от редактирования.');
      }
      return;
    }

    const identity = rowIdentity(worksheet, row);
    if (typeof identity === 'string' && creatingDrafts.has(identity)) {
      params.cancel = true;
      setErrorStatus('Дождитесь создания записи из этой строки.');
      return;
    }
    if (identity === null) materializeDraft(worksheet, row);
    else syncSelectionContext(worksheet, row);
  });

  univerAPI.addEvent(
    univerAPI.Event.SheetEditEnded,
    ({ row, column, worksheet }: any) => {
      if (!worksheet || batchInProgress) return;
      const binding = getCellBinding(column);
      if (binding === null) return;
      const identity = rowIdentity(worksheet, row);
      const rawValue = worksheet.getRange(row, column).getValue();

      if (typeof identity === 'number') {
        const current = recordsById.get(identity);
        if (!current) return;
        const currentAsDraft: JournalDraftSnapshot = {
          ...current,
          clientId: `${DRAFT_ID_PREFIX}record-${current.id}`,
        };
        const parsed = parseDraftEdit(currentAsDraft, binding, rawValue, snapshot.eventTypes);
        if (!parsed.ok) {
          scheduleModelRender(worksheet, row, current);
          setErrorStatus(parsed.message);
          return;
        }
        if (Object.keys(parsed.changes).length === 0) {
          scheduleModelRender(worksheet, row, current);
          return;
        }
        enqueueRecordPatch(identity, worksheet, parsed.changes);
        return;
      }

      if (typeof identity !== 'string') return;
      const currentDraft = draftsById.get(identity);
      if (!currentDraft) return;
      const parsed = parseDraftEdit(currentDraft, binding, rawValue, snapshot.eventTypes);
      if (!parsed.ok) {
        scheduleModelRender(worksheet, row, currentDraft);
        setErrorStatus(parsed.message);
        return;
      }
      draftsById.set(identity, parsed.draft);
      scheduleModelRender(worksheet, row, parsed.draft);
      if (activeRow?.row === row) syncSelectionContext(worksheet, row);
      maybeCreateDraft(identity, worksheet);
    }
  );

  univerAPI.addEvent(univerAPI.Event.BeforeClipboardPaste, (params: any) => {
    const text = typeof params.text === 'string' ? params.text : '';
    if (!text) return;
    const workbook = univerAPI.getActiveWorkbook?.();
    const worksheet = workbook?.getActiveSheet?.();
    const selection = worksheet?.getSelection?.();
    const activeRange = selection?.getActiveRange?.();
    const startRow = activeRange?.getRow?.();
    const startColumn = activeRange?.getColumn?.();
    if (
      !worksheet ||
      typeof startRow !== 'number' ||
      typeof startColumn !== 'number'
    ) {
      return;
    }
    params.cancel = true;
    if (startRow === HEADER_ROW_INDEX) {
      setErrorStatus('Вставка в заголовок запрещена.');
      return;
    }
    void applyBatchPaste(worksheet, startRow, startColumn, text);
  });

  univerAPI.addEvent(univerAPI.Event.SelectionChanged, ({ worksheet }: any) => {
    const currentCell = worksheet?.getSelection?.()?.getCurrentCell?.();
    if (!worksheet || !currentCell) return;
    syncSelectionContext(worksheet, currentCell.actualRow);
  });

  univerAPI.addEvent(univerAPI.Event.CellClicked, ({ row, worksheet }: any) => {
    if (worksheet) syncSelectionContext(worksheet, row);
  });

  setReadyStatus();
  const worksheet = univerAPI.getActiveWorkbook?.()?.getActiveSheet?.();
  if (worksheet) {
    const firstBlankRow = snapshot.records.length + 1;
    worksheet.getRange(firstBlankRow, 3).activate?.();
    syncSelectionContext(worksheet, firstBlankRow);
  }
  document.documentElement.dataset.editingModel = 'native-row';
}
