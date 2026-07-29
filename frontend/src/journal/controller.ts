import {
  DISPLAY_COLUMNS,
  HEADER_ROW_INDEX,
  RECORD_ID_COLUMN,
  REVISION_COLUMN,
  getDisplayValue,
  getEditableField,
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
  readonly identity: number | string;
};

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

export function createDraft(
  eventTypes: readonly JournalEventTypeOption[]
): JournalDraftSnapshot {
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

function updateDraftField(
  draft: JournalDraftSnapshot,
  field: EditableJournalField,
  value: string
): JournalDraftSnapshot {
  return { ...draft, [field]: value } as JournalDraftSnapshot;
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

function parseClipboardMatrix(text: string): string[][] {
  const normalized = text.replace(/\r\n?/g, '\n');
  const withoutFinalNewline = normalized.endsWith('\n')
    ? normalized.slice(0, -1)
    : normalized;
  if (!withoutFinalNewline) return [];
  return withoutFinalNewline.split('\n').map((row) => row.split('\t'));
}

function setControlsEnabled(controls: EditorControls, enabled: boolean): void {
  controls.date.disabled = !enabled;
  controls.time.disabled = !enabled;
  controls.eventType.disabled = !enabled;
  controls.includeInReport.disabled = !enabled;
  if (!enabled) controls.close.disabled = true;
}

export function startJournalController(
  univerAPI: UniverApi,
  snapshot: JournalSnapshot,
  initialDraft: JournalDraftSnapshot,
  status: HTMLElement,
  controls: EditorControls
): void {
  const eventTypeLabels = new Map(snapshot.eventTypes.map(({ value, label }) => [value, label]));
  const recordsById = new Map(snapshot.records.map((record) => [record.id, record]));
  const draftsById = new Map([[initialDraft.clientId, initialDraft]]);
  const saveQueues = new Map<string, Promise<void>>();
  const creatingDrafts = new Set<string>();
  const maximumScanRow = Math.max(snapshot.records.length + 400, 600);
  let pendingSaveCount = 0;
  let activeRow: ActiveRow | null = null;
  let batchInProgress = false;

  const setReadyStatus = (): void => {
    const recordCount = new Intl.NumberFormat('ru-RU').format(recordsById.size);
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent = `Загружено записей: ${recordCount} · все изменения сохранены`;
  };

  const setSavingStatus = (message?: string): void => {
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent =
      message ??
      (pendingSaveCount > 1
        ? `Сохранение изменений: ${pendingSaveCount}…`
        : 'Сохранение изменения…');
  };

  const setDraftStatus = (): void => {
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent = 'Новая строка: заполните оборудование и описание';
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

  const findRecordRow = (worksheet: WorksheetFacade, recordId: number): number | null => {
    for (let row = 1; row < maximumScanRow; row += 1) {
      const value = numericCellValue(worksheet.getRange(row, RECORD_ID_COLUMN).getValue());
      if (value === recordId) return row;
    }
    return null;
  };

  const findDraftRow = (worksheet: WorksheetFacade, clientId: string): number | null => {
    for (let row = 1; row < maximumScanRow; row += 1) {
      const value = draftCellValue(worksheet.getRange(row, RECORD_ID_COLUMN).getValue());
      if (value === clientId) return row;
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

  const restoreRecord = (worksheet: WorksheetFacade, record: JournalEventSnapshot): void => {
    const currentRow = findRecordRow(worksheet, record.id);
    if (currentRow !== null) applyRecordToRow(worksheet, currentRow, record);
  };

  const clearEditorSelection = (): void => {
    activeRow = null;
    controls.selection.textContent = 'Выберите строку';
    controls.date.value = '';
    controls.time.value = '';
    controls.eventType.value = '';
    controls.includeInReport.checked = false;
    setControlsEnabled(controls, false);
  };

  const syncEditorSelection = (worksheet: WorksheetFacade, row: number): void => {
    if (row === HEADER_ROW_INDEX) {
      clearEditorSelection();
      return;
    }
    const identityValue = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
    const recordId = numericCellValue(identityValue);
    const draftId = draftCellValue(identityValue);
    const model =
      recordId !== null
        ? recordsById.get(recordId)
        : draftId !== null
          ? draftsById.get(draftId)
          : undefined;
    const identity = recordId ?? draftId;
    if (!model || identity === null) {
      clearEditorSelection();
      return;
    }

    activeRow = { worksheet, row, identity };
    const { date, time } = splitStartAt(model.startAt);
    controls.selection.textContent =
      recordId !== null ? `Событие №${recordId}` : `Новая строка №${row}`;
    controls.date.value = date;
    controls.time.value = time;
    controls.eventType.value = model.eventType;
    controls.includeInReport.checked = model.includeInReport;
    setControlsEnabled(controls, !batchInProgress);
    controls.close.disabled = batchInProgress || recordId === null || model.status === 'closed';
    controls.close.textContent =
      model.status === 'closed' ? 'Событие завершено' : 'Завершить событие';
  };

  const refreshActiveEditor = (): void => {
    if (activeRow) syncEditorSelection(activeRow.worksheet, activeRow.row);
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
          if (queueMatchesActiveRow(queueKey)) refreshActiveEditor();
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
      refreshActiveEditor();
      setErrorStatus(`Конфликт сохранения: ${error.message}`);
      return;
    }
    restoreRecord(worksheet, current);
    refreshActiveEditor();
    const message = error instanceof Error ? error.message : String(error);
    setErrorStatus(`${prefix}: ${message}`);
  };

  const enqueueRecordPatch = (
    recordId: number,
    worksheet: WorksheetFacade,
    buildChanges: (current: JournalEventSnapshot) => JournalPatchRequest['changes']
  ): void => {
    enqueueSave(`record:${recordId}`, async () => {
      const current = recordsById.get(recordId);
      if (!current) return;
      const changes = buildChanges(current);
      if (Object.keys(changes).length === 0) return;

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

  const maybeCreateDraft = (draftId: string, worksheet: WorksheetFacade): void => {
    const draft = draftsById.get(draftId);
    if (!draft || !draftIsComplete(draft)) {
      setDraftStatus();
      return;
    }
    if (creatingDrafts.has(draftId) || batchInProgress) return;

    creatingDrafts.add(draftId);
    enqueueSave(draftId, async () => {
      pendingSaveCount += 1;
      setSavingStatus();
      try {
        const currentDraft = draftsById.get(draftId);
        if (!currentDraft || !draftIsComplete(currentDraft)) return;
        const created = await createRecord(draftCreateRequest(currentDraft));
        const draftRow = findDraftRow(worksheet, draftId);
        draftsById.delete(draftId);
        recordsById.set(created.record.id, created.record);
        if (draftRow !== null) {
          applyRecordToRow(worksheet, draftRow, created.record);
          const nextDraft = createDraft(snapshot.eventTypes);
          draftsById.set(nextDraft.clientId, nextDraft);
          applyDraftToRow(worksheet, draftRow + 1, nextDraft);
          if (activeRow?.identity === draftId) {
            activeRow = { worksheet, row: draftRow, identity: created.record.id };
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

  const updateActiveDraft = (
    update: (draft: JournalDraftSnapshot) => JournalDraftSnapshot
  ): void => {
    if (!activeRow || typeof activeRow.identity !== 'string' || batchInProgress) return;
    const draftId = activeRow.identity;
    const current = draftsById.get(draftId);
    if (!current) return;
    const updated = update(current);
    draftsById.set(draftId, updated);
    applyDraftToRow(activeRow.worksheet, activeRow.row, updated);
    refreshActiveEditor();
    maybeCreateDraft(draftId, activeRow.worksheet);
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
        setErrorStatus('Пакетная вставка пока поддерживается только для сохранённых строк.');
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
          setErrorStatus('Диапазон вставки содержит защищённую колонку. Операция отменена.');
          return;
        }
        const value = values[columnOffset] ?? '';
        if (value !== String(getDisplayValue(record, targetColumn, targetRow - 1))) {
          changes[field] = value;
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
    setControlsEnabled(controls, false);
    setSavingStatus(`Пакетное сохранение: ${operations.length} строк…`);
    try {
      const updatedRecords = await patchRecordsBatch({ operations });
      updatedRecords.forEach((record) => {
        recordsById.set(record.id, record);
        restoreRecord(worksheet, record);
      });
      refreshActiveEditor();
    } catch (error) {
      if (error instanceof JournalApiError && error.current) {
        recordsById.set(error.current.id, error.current);
        restoreRecord(worksheet, error.current);
      }
      const message = error instanceof Error ? error.message : String(error);
      setErrorStatus(`Пакетная вставка отменена: ${message}`);
    } finally {
      batchInProgress = false;
      refreshActiveEditor();
      finishPendingOperation();
    }
  };

  controls.date.addEventListener('change', () => {
    if (!activeRow || batchInProgress) return;
    const selectedDate = controls.date.value;
    if (typeof activeRow.identity === 'number') {
      enqueueRecordPatch(activeRow.identity, activeRow.worksheet, (current) => {
        const { time } = splitStartAt(current.startAt);
        const startAt = combineStartAt(selectedDate, time);
        return startAt && startAt !== current.startAt ? { startAt } : {};
      });
    } else {
      updateActiveDraft((draft) => {
        const { time } = splitStartAt(draft.startAt);
        const startAt = combineStartAt(selectedDate, time);
        return startAt ? { ...draft, startAt } : draft;
      });
    }
  });

  controls.time.addEventListener('change', () => {
    if (!activeRow || batchInProgress) return;
    const selectedTime = controls.time.value;
    if (typeof activeRow.identity === 'number') {
      enqueueRecordPatch(activeRow.identity, activeRow.worksheet, (current) => {
        const { date } = splitStartAt(current.startAt);
        const startAt = combineStartAt(date, selectedTime);
        return startAt && startAt !== current.startAt ? { startAt } : {};
      });
    } else {
      updateActiveDraft((draft) => {
        const { date } = splitStartAt(draft.startAt);
        const startAt = combineStartAt(date, selectedTime);
        return startAt ? { ...draft, startAt } : draft;
      });
    }
  });

  controls.eventType.addEventListener('change', () => {
    if (!activeRow || batchInProgress) return;
    const eventType = controls.eventType.value;
    const eventTypeLabel = eventTypeLabels.get(eventType);
    if (!eventTypeLabel) {
      setErrorStatus('Выбран неизвестный тип события.');
      refreshActiveEditor();
      return;
    }
    if (typeof activeRow.identity === 'number') {
      enqueueRecordPatch(activeRow.identity, activeRow.worksheet, (current) =>
        current.eventType === eventType ? {} : { eventType }
      );
    } else {
      updateActiveDraft((draft) => ({ ...draft, eventType, eventTypeLabel }));
    }
  });

  controls.includeInReport.addEventListener('change', () => {
    if (!activeRow || batchInProgress) return;
    const includeInReport = controls.includeInReport.checked;
    if (typeof activeRow.identity === 'number') {
      enqueueRecordPatch(activeRow.identity, activeRow.worksheet, (current) =>
        current.includeInReport === includeInReport ? {} : { includeInReport }
      );
    } else {
      updateActiveDraft((draft) => ({ ...draft, includeInReport }));
    }
  });

  controls.close.addEventListener('click', () => {
    if (!activeRow || typeof activeRow.identity !== 'number' || batchInProgress) return;
    const record = recordsById.get(activeRow.identity);
    if (record?.status === 'open') enqueueRecordClose(record.id, activeRow.worksheet);
  });

  univerAPI.addEvent(univerAPI.Event.BeforeSheetEditStart, (params: any) => {
    const { row, column, worksheet } = params;
    const identity = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
    const recordId = numericCellValue(identity);
    const draftId = draftCellValue(identity);
    const editableIdentity =
      (recordId !== null && recordsById.has(recordId)) ||
      (draftId !== null && draftsById.has(draftId));
    if (
      batchInProgress ||
      row === HEADER_ROW_INDEX ||
      !editableIdentity ||
      getEditableField(column) === null
    ) {
      params.cancel = true;
    }
  });

  univerAPI.addEvent(
    univerAPI.Event.SheetEditEnded,
    ({ row, column, worksheet }: any) => {
      const field = getEditableField(column);
      if (field === null || batchInProgress) return;
      const identity = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
      const recordId = numericCellValue(identity);
      const draftId = draftCellValue(identity);
      const value = editableCellValue(worksheet.getRange(row, column).getValue());

      if (recordId !== null) {
        const existing = recordsById.get(recordId);
        if (!existing || value === String(getDisplayValue(existing, column, row - 1))) return;
        enqueueRecordPatch(recordId, worksheet, () => ({ [field]: value }));
        return;
      }
      if (draftId === null) return;
      const existingDraft = draftsById.get(draftId);
      if (!existingDraft) return;
      const updatedDraft = updateDraftField(existingDraft, field, value);
      draftsById.set(draftId, updatedDraft);
      if (activeRow?.identity === draftId) refreshActiveEditor();
      maybeCreateDraft(draftId, worksheet);
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
    const selection = worksheet?.getSelection?.();
    const currentCell = selection?.getCurrentCell?.();
    if (!worksheet || !currentCell) {
      clearEditorSelection();
      return;
    }
    syncEditorSelection(worksheet, currentCell.actualRow);
  });

  univerAPI.addEvent(univerAPI.Event.CellClicked, ({ row, worksheet }: any) => {
    if (worksheet) syncEditorSelection(worksheet, row);
  });

  clearEditorSelection();
  setReadyStatus();
}
