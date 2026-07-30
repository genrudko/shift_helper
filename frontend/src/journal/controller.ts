import {
  DISPLAY_COLUMNS,
  HEADER_ROW_INDEX,
  RECORD_ID_COLUMN,
  REVISION_COLUMN,
  applyDraftToWorkbookRow,
  getCellBinding,
  getDisplayValue,
  type JournalCellBinding,
} from './buildWorkbook';
import {
  JournalApiError,
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
  JournalPatchField,
  JournalPatchRequest,
  JournalSnapshot,
} from './types';

const DRAFT_ID_PREFIX = 'draft:';
const DRAFT_CLEAR_EVENT = 'shift-helper:draft-clear';
let draftSequence = 0;

type WorksheetFacade = any;
type UniverApi = any;
type EndParts = { date: string; time: string };
type DraftClearDetail = {
  readonly rows: Array<{
    readonly row: number;
    readonly fields: JournalPatchField[];
    readonly deleteRow?: boolean;
  }>;
};

function numericCellValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isInteger(value) && value > 0) return value;
  if (typeof value === 'string' && /^\d+$/.test(value)) return Number(value);
  return null;
}

function draftCellValue(value: unknown): string | null {
  return typeof value === 'string' && value.startsWith(DRAFT_ID_PREFIX) ? value : null;
}

function cellText(value: unknown): string {
  return value === null || value === undefined ? '' : String(value);
}

function pad(value: number): string {
  return String(value).padStart(2, '0');
}

function localMinuteIso(date = new Date()): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

function createDraft(): JournalDraftSnapshot {
  draftSequence += 1;
  return {
    clientId: `${DRAFT_ID_PREFIX}${Date.now().toString(36)}-${draftSequence.toString(36)}`,
    startAt: localMinuteIso(),
    endAt: null,
    assetLabel: '',
    eventType: 'other',
    description: '',
    reason: null,
    actions: null,
    performer: null,
    errorCodes: null,
    rotorLimit: null,
    repairPowerMw: null,
    status: 'open',
    includeInReport: true,
    enteredBy: '',
    downtimeMinutes: null,
    losses: null,
  };
}

function splitIso(value: string | null): EndParts {
  if (!value) return { date: '', time: '' };
  const [date = '', rawTime = ''] = value.split('T');
  return { date, time: rawTime.slice(0, 5) };
}

function combineIso(date: string, time: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) return null;
  return `${date}T${time}`;
}

function validDate(year: number, month: number, day: number): string | null {
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }
  return `${String(year).padStart(4, '0')}-${pad(month)}-${pad(day)}`;
}

function parseDate(value: unknown, current: string, above: unknown): string | null {
  const text = cellText(value).trim();
  const now = new Date();
  if (text === '!') return validDate(now.getFullYear(), now.getMonth() + 1, now.getDate());
  if (text === '.') return parseDate(above, current, '');
  const increment = /^\+(-?\d+)$/.exec(text);
  if (increment) {
    const base = /^\d{4}-\d{2}-\d{2}$/.test(current)
      ? new Date(`${current}T00:00:00`)
      : now;
    base.setDate(base.getDate() + Number(increment[1]));
    return validDate(base.getFullYear(), base.getMonth() + 1, base.getDate());
  }
  if (/^\d{4}$/.test(text)) {
    return validDate(now.getFullYear(), Number(text.slice(2, 4)), Number(text.slice(0, 2)));
  }
  if (/^\d{6}$/.test(text)) {
    return validDate(
      2000 + Number(text.slice(4, 6)),
      Number(text.slice(2, 4)),
      Number(text.slice(0, 2))
    );
  }
  const iso = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(text);
  const display = /^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$/.exec(text);
  if (iso) return validDate(Number(iso[1]), Number(iso[2]), Number(iso[3]));
  if (display) return validDate(Number(display[3]), Number(display[2]), Number(display[1]));
  return null;
}

function parseTime(value: unknown, current: string, above: unknown): string | null {
  const text = cellText(value).trim();
  const now = new Date();
  if (text === '!') return `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  if (text === '.') return parseTime(above, current, '');
  const increment = /^\+(-?\d+)$/.exec(text);
  if (increment) {
    const match = /^(\d{2}):(\d{2})$/.exec(current);
    const baseMinutes = match
      ? Number(match[1]) * 60 + Number(match[2])
      : now.getHours() * 60 + now.getMinutes();
    const total = ((baseMinutes + Number(increment[1])) % 1440 + 1440) % 1440;
    return `${pad(Math.floor(total / 60))}:${pad(total % 60)}`;
  }
  if (/^\d{3,4}$/.test(text)) {
    const digits = text.padStart(4, '0');
    const hour = Number(digits.slice(0, 2));
    const minute = Number(digits.slice(2, 4));
    return hour <= 23 && minute <= 59 ? `${pad(hour)}:${pad(minute)}` : null;
  }
  const match = /^(\d{1,2}):(\d{2})(?::\d{2})?$/.exec(text);
  if (!match || Number(match[1]) > 23 || Number(match[2]) > 59) return null;
  return `${pad(Number(match[1]))}:${match[2]}`;
}

function normalizeText(field: EditableJournalField, value: unknown): string | null {
  const text = cellText(value);
  return field === 'assetLabel' || field === 'description' ? text : text.trim() || null;
}

function draftComplete(draft: JournalDraftSnapshot): boolean {
  return Boolean(draft.assetLabel.trim() && draft.description.trim());
}

function createPayload(draft: JournalDraftSnapshot): JournalCreateRequest {
  return {
    clientId: draft.clientId,
    values: {
      startAt: draft.startAt,
      endAt: draft.endAt,
      assetLabel: draft.assetLabel,
      eventType: draft.eventType,
      description: draft.description,
      reason: draft.reason,
      actions: draft.actions,
      performer: draft.performer,
      errorCodes: draft.errorCodes,
      rotorLimit: draft.rotorLimit,
      includeInReport: draft.includeInReport,
    },
  };
}

function reconciliationChanges(
  record: JournalEventSnapshot,
  draft: JournalDraftSnapshot
): JournalPatchRequest['changes'] {
  const changes: JournalPatchRequest['changes'] = {};
  if (record.startAt !== draft.startAt) changes.startAt = draft.startAt;
  if (record.endAt !== draft.endAt) changes.endAt = draft.endAt;
  if (record.assetLabel !== draft.assetLabel) changes.assetLabel = draft.assetLabel;
  if (record.description !== draft.description) changes.description = draft.description;
  if (record.reason !== draft.reason) changes.reason = draft.reason;
  if (record.actions !== draft.actions) changes.actions = draft.actions;
  if (record.performer !== draft.performer) changes.performer = draft.performer;
  return changes;
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
  const endParts = new Map<string, EndParts>();
  let pendingSaveCount = 0;
  let batchInProgress = false;

  const setReadyStatus = (): void => {
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent = `Загружено записей: ${new Intl.NumberFormat('ru-RU').format(
      recordsById.size
    )} · изменения сохраняются автоматически`;
  };

  const setError = (message: string): void => {
    status.classList.add('shift-helper-v2__status--error');
    status.textContent = message;
  };

  const setDraftStatus = (row: number): void => {
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent = `Черновик в строке ${row + 1}: заполните № ВЭУ и описание события`;
  };

  const setSaving = (message = 'Сохранение изменения…'): void => {
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent = pendingSaveCount > 1
      ? `Сохранение изменений: ${pendingSaveCount}…`
      : message;
  };

  const finishPending = (): void => {
    pendingSaveCount = Math.max(0, pendingSaveCount - 1);
    if (pendingSaveCount > 0) setSaving();
    else if (!status.classList.contains('shift-helper-v2__status--error')) setReadyStatus();
  };

  const rowIdentity = (worksheet: WorksheetFacade, row: number): number | string | null => {
    const value = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
    return numericCellValue(value) ?? draftCellValue(value);
  };

  const applyRecord = (
    worksheet: WorksheetFacade,
    row: number,
    record: JournalEventSnapshot
  ): void => {
    DISPLAY_COLUMNS.forEach((_column, column) => {
      worksheet.getRange(row, column).setValue(getDisplayValue(record, column));
    });
    worksheet.getRange(row, RECORD_ID_COLUMN).setValue(record.id);
    worksheet.getRange(row, REVISION_COLUMN).setValue(record.revision);
  };

  const clearWorkbookRow = (worksheet: WorksheetFacade, row: number): void => {
    for (let column = 0; column <= REVISION_COLUMN; column += 1) {
      worksheet.getRange(row, column).setValue('');
    }
  };

  const materializeDraft = (
    worksheet: WorksheetFacade,
    row: number
  ): JournalDraftSnapshot => {
    const existingIdentity = rowIdentity(worksheet, row);
    if (typeof existingIdentity === 'string') {
      return draftsById.get(existingIdentity) ?? createDraft();
    }
    const draft = createDraft();
    draftsById.set(draft.clientId, draft);
    endParts.set(draft.clientId, { date: '', time: '' });
    applyDraftToWorkbookRow(worksheet, row, draft);
    return draft;
  };

  const enqueue = (key: string, task: () => Promise<void>): void => {
    const previous = saveQueues.get(key) ?? Promise.resolve();
    const next = previous
      .catch(() => undefined)
      .then(task)
      .finally(() => {
        if (saveQueues.get(key) === next) saveQueues.delete(key);
      });
    saveQueues.set(key, next);
  };

  const enqueueRecordPatch = (
    recordId: number,
    worksheet: WorksheetFacade,
    row: number,
    buildChanges: (current: JournalEventSnapshot) => JournalPatchRequest['changes']
  ): void => {
    enqueue(`record:${recordId}`, async () => {
      const current = recordsById.get(recordId);
      if (!current) return;
      const changes = buildChanges(current);
      if (Object.keys(changes).length === 0) return;
      pendingSaveCount += 1;
      setSaving();
      try {
        const updated = await patchRecord(recordId, {
          revision: current.revision,
          changes,
        });
        recordsById.set(recordId, updated);
        endParts.set(String(recordId), splitIso(updated.endAt));
        applyRecord(worksheet, row, updated);
      } catch (error) {
        if (error instanceof JournalApiError && error.current) {
          recordsById.set(recordId, error.current);
          applyRecord(worksheet, row, error.current);
        } else {
          applyRecord(worksheet, row, current);
        }
        setError(error instanceof Error ? error.message : String(error));
      } finally {
        finishPending();
      }
    });
  };

  const maybeCreateDraft = (
    draftId: string,
    worksheet: WorksheetFacade,
    row: number
  ): void => {
    const draft = draftsById.get(draftId);
    if (!draft || !draftComplete(draft)) {
      setDraftStatus(row);
      return;
    }
    if (creatingDrafts.has(draftId) || batchInProgress) return;
    creatingDrafts.add(draftId);
    enqueue(draftId, async () => {
      pendingSaveCount += 1;
      setSaving('Создание записи…');
      try {
        const submitted = draftsById.get(draftId);
        if (!submitted || !draftComplete(submitted)) return;
        const created = await createRecord(createPayload(submitted));
        let synchronized = created.record;

        while (true) {
          const latest = draftsById.get(draftId) ?? submitted;
          const changes = reconciliationChanges(synchronized, latest);
          if (Object.keys(changes).length === 0) break;
          synchronized = await patchRecord(synchronized.id, {
            revision: synchronized.revision,
            changes,
          });
        }

        draftsById.delete(draftId);
        endParts.delete(draftId);
        recordsById.set(synchronized.id, synchronized);
        endParts.set(String(synchronized.id), splitIso(synchronized.endAt));
        applyRecord(worksheet, row, synchronized);
      } catch (error) {
        setError(
          `Новая запись не сохранена: ${error instanceof Error ? error.message : String(error)}`
        );
      } finally {
        creatingDrafts.delete(draftId);
        finishPending();
      }
    });
  };

  const updateDraft = (
    draftId: string,
    worksheet: WorksheetFacade,
    row: number,
    update: (draft: JournalDraftSnapshot) => JournalDraftSnapshot
  ): void => {
    const current = draftsById.get(draftId);
    if (!current) return;
    draftsById.set(draftId, update(current));
    maybeCreateDraft(draftId, worksheet, row);
  };

  const editText = (
    identity: number | string,
    worksheet: WorksheetFacade,
    row: number,
    column: number,
    field: EditableJournalField,
    value: unknown
  ): void => {
    const normalized = normalizeText(field, value);
    if (typeof identity === 'number') {
      enqueueRecordPatch(identity, worksheet, row, (current) => {
        if (normalized === getDisplayValue(current, column)) return {};
        return { [field]: normalized };
      });
      return;
    }
    updateDraft(identity, worksheet, row, (current) => ({
      ...current,
      [field]: normalized,
    }) as JournalDraftSnapshot);
  };

  const editStartPart = (
    identity: number | string,
    model: JournalEventSnapshot | JournalDraftSnapshot,
    worksheet: WorksheetFacade,
    row: number,
    column: number,
    binding: Extract<JournalCellBinding, { kind: 'startDate' | 'startTime' }>,
    value: unknown
  ): void => {
    const parts = splitIso(model.startAt);
    const above = row > 1 ? worksheet.getRange(row - 1, column).getValue() : '';
    const parsed = binding.kind === 'startDate'
      ? parseDate(value, parts.date, above)
      : parseTime(value, parts.time, above);
    if (!parsed) {
      worksheet.getRange(row, column).setValue(getDisplayValue(model, column));
      setError(
        binding.kind === 'startDate'
          ? 'Дата останова не сохранена. Используйте ДД.ММ.ГГГГ, 2707, !, . или +N.'
          : 'Время останова не сохранено. Используйте ЧЧ:ММ, 830, !, . или +N.'
      );
      return;
    }
    const startAt = binding.kind === 'startDate'
      ? combineIso(parsed, parts.time)
      : combineIso(parts.date, parsed);
    if (!startAt) return;
    if (typeof identity === 'number') {
      enqueueRecordPatch(identity, worksheet, row, (current) =>
        current.startAt === startAt ? {} : { startAt }
      );
      return;
    }
    worksheet.getRange(row, column).setValue(
      binding.kind === 'startDate'
        ? `${parsed.slice(8, 10)}.${parsed.slice(5, 7)}.${parsed.slice(0, 4)}`
        : parsed
    );
    updateDraft(identity, worksheet, row, (current) => ({ ...current, startAt }));
  };

  const editEndPart = (
    identity: number | string,
    model: JournalEventSnapshot | JournalDraftSnapshot,
    worksheet: WorksheetFacade,
    row: number,
    column: number,
    binding: Extract<JournalCellBinding, { kind: 'endDate' | 'endTime' }>,
    value: unknown
  ): void => {
    const key = String(identity);
    const existing = endParts.get(key) ?? splitIso(model.endAt);
    const above = row > 1 ? worksheet.getRange(row - 1, column).getValue() : '';
    const raw = cellText(value).trim();
    if (!raw) {
      endParts.set(key, { date: '', time: '' });
      if (typeof identity === 'number') {
        enqueueRecordPatch(identity, worksheet, row, (current) =>
          current.endAt === null ? {} : { endAt: null }
        );
      } else {
        updateDraft(identity, worksheet, row, (current) => ({ ...current, endAt: null }));
      }
      return;
    }

    const parsed = binding.kind === 'endDate'
      ? parseDate(value, existing.date || splitIso(model.startAt).date, above)
      : parseTime(value, existing.time, above);
    if (!parsed) {
      worksheet.getRange(row, column).setValue(getDisplayValue(model, column));
      setError(
        binding.kind === 'endDate'
          ? 'Дата пуска не сохранена. Используйте ДД.ММ.ГГГГ, 2707, !, . или +N.'
          : 'Время пуска не сохранено. Используйте ЧЧ:ММ, 830, !, . или +N.'
      );
      return;
    }

    const nextParts = binding.kind === 'endDate'
      ? { ...existing, date: parsed }
      : { ...existing, time: parsed };
    endParts.set(key, nextParts);
    const endAt = combineIso(nextParts.date, nextParts.time);
    if (!endAt) {
      status.classList.remove('shift-helper-v2__status--error');
      status.textContent = 'Для завершения события заполните и дату, и время пуска.';
      return;
    }
    if (typeof identity === 'number') {
      enqueueRecordPatch(identity, worksheet, row, (current) =>
        current.endAt === endAt ? {} : { endAt }
      );
    } else {
      updateDraft(identity, worksheet, row, (current) => ({ ...current, endAt }));
    }
  };

  const editModel = (
    worksheet: WorksheetFacade,
    row: number,
    column: number,
    binding: JournalCellBinding,
    value: unknown
  ): void => {
    const identity = rowIdentity(worksheet, row);
    if (identity === null) return;
    const model = typeof identity === 'number'
      ? recordsById.get(identity)
      : draftsById.get(identity);
    if (!model || binding.kind === 'readonly') return;

    if (binding.kind === 'text') {
      editText(identity, worksheet, row, column, binding.field, value);
    } else if (binding.kind === 'startDate' || binding.kind === 'startTime') {
      editStartPart(identity, model, worksheet, row, column, binding, value);
    } else {
      editEndPart(identity, model, worksheet, row, column, binding, value);
    }
  };

  const applyBatchPaste = async (
    worksheet: WorksheetFacade,
    startRow: number,
    startColumn: number,
    text: string
  ): Promise<void> => {
    if (batchInProgress || saveQueues.size > 0 || creatingDrafts.size > 0) {
      setError('Дождитесь завершения текущего сохранения перед пакетной вставкой.');
      return;
    }
    const matrix = text
      .replace(/\r\n?/g, '\n')
      .replace(/\n$/, '')
      .split('\n')
      .map((line) => line.split('\t'));
    if (!matrix[0]?.length) return;
    if (matrix.length > 200) {
      setError('За одну пакетную вставку допускается не более 200 строк.');
      return;
    }

    const operations: JournalBatchOperation[] = [];
    for (let rowOffset = 0; rowOffset < matrix.length; rowOffset += 1) {
      const row = startRow + rowOffset;
      const recordId = numericCellValue(worksheet.getRange(row, RECORD_ID_COLUMN).getValue());
      const revision = numericCellValue(worksheet.getRange(row, REVISION_COLUMN).getValue());
      if (recordId === null || revision === null) {
        setError('Пакетная вставка поддерживается только для сохранённых строк.');
        return;
      }
      const changes: JournalPatchRequest['changes'] = {};
      const values = matrix[rowOffset] ?? [];
      for (let columnOffset = 0; columnOffset < values.length; columnOffset += 1) {
        const column = startColumn + columnOffset;
        const binding = getCellBinding(column);
        if (!binding || binding.kind !== 'text') {
          setError('Пакетная вставка сейчас разрешена только в текстовые графы формы.');
          return;
        }
        changes[binding.field] = normalizeText(binding.field, values[columnOffset]);
      }
      operations.push({ recordId, revision, changes });
    }

    batchInProgress = true;
    pendingSaveCount += 1;
    setSaving(`Пакетное сохранение: ${operations.length} строк…`);
    try {
      const updated = await patchRecordsBatch({ operations });
      updated.forEach((record) => recordsById.set(record.id, record));
      window.location.reload();
    } catch (error) {
      batchInProgress = false;
      finishPending();
      setError(
        `Пакетная вставка отменена: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  };

  univerAPI.addEvent(univerAPI.Event.BeforeSheetEditStart, (params: any) => {
    const { row, column, worksheet } = params;
    const binding = getCellBinding(column);
    if (
      batchInProgress ||
      row === HEADER_ROW_INDEX ||
      !binding ||
      binding.kind === 'readonly'
    ) {
      params.cancel = true;
      if (binding?.kind === 'readonly') setError('Эта графа рассчитывается автоматически.');
      return;
    }
    if (rowIdentity(worksheet, row) === null) materializeDraft(worksheet, row);
  });

  univerAPI.addEvent(univerAPI.Event.SheetEditEnded, ({ row, column, worksheet }: any) => {
    const binding = getCellBinding(column);
    if (!worksheet || !binding || binding.kind === 'readonly' || batchInProgress) return;
    editModel(worksheet, row, column, binding, worksheet.getRange(row, column).getValue());
  });

  univerAPI.addEvent(univerAPI.Event.BeforeClipboardPaste, (params: any) => {
    const text = typeof params.text === 'string' ? params.text : '';
    if (!text) return;
    const worksheet = univerAPI.getActiveWorkbook?.()?.getActiveSheet?.();
    const current = worksheet?.getSelection?.()?.getCurrentCell?.();
    if (!worksheet || !current) return;
    params.cancel = true;
    void applyBatchPaste(worksheet, current.actualRow, current.actualColumn, text);
  });

  const syncSelection = (worksheet: WorksheetFacade, row: number): void => {
    if (row === HEADER_ROW_INDEX) {
      controls.selection.textContent = 'Заголовок журнала';
      return;
    }
    const identity = rowIdentity(worksheet, row);
    controls.selection.textContent = typeof identity === 'number'
      ? `Запись №${identity} · строка ${row + 1}`
      : typeof identity === 'string'
        ? `Черновик · строка ${row + 1}`
        : `Пустая рабочая строка ${row + 1}`;
  };

  univerAPI.addEvent(univerAPI.Event.SelectionChanged, ({ worksheet }: any) => {
    const current = worksheet?.getSelection?.()?.getCurrentCell?.();
    if (worksheet && current) syncSelection(worksheet, current.actualRow);
  });

  univerAPI.addEvent(univerAPI.Event.CellClicked, ({ row, worksheet }: any) => {
    if (worksheet) syncSelection(worksheet, row);
  });

  window.addEventListener(DRAFT_CLEAR_EVENT, (event) => {
    const detail = (event as CustomEvent<DraftClearDetail>).detail;
    const worksheet = univerAPI.getActiveWorkbook?.()?.getActiveSheet?.();
    if (!worksheet || !detail?.rows) return;
    detail.rows.forEach(({ row, fields, deleteRow }) => {
      const draftId = draftCellValue(worksheet.getRange(row, RECORD_ID_COLUMN).getValue());
      if (!draftId) return;
      if (deleteRow) {
        draftsById.delete(draftId);
        endParts.delete(draftId);
        clearWorkbookRow(worksheet, row);
        return;
      }
      const current = draftsById.get(draftId);
      if (!current) return;
      const updated = { ...current };
      fields.forEach((field) => {
        if (field === 'endAt') {
          updated.endAt = null;
          endParts.set(draftId, { date: '', time: '' });
        } else if (field !== 'startAt' && field in updated) {
          (updated as Record<string, unknown>)[field] =
            field === 'assetLabel' || field === 'description' ? '' : null;
        }
      });
      draftsById.set(draftId, updated);
    });
  });

  document.documentElement.dataset.editingModel = 'approved-js-row';
  setReadyStatus();
}
