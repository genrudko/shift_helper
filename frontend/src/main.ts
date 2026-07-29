import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import sheetsCoreEnUS from '@univerjs/preset-sheets-core/locales/en-US';
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';

import '@univerjs/preset-sheets-core/lib/index.css';
import './styles.css';

import {
  DISPLAY_COLUMNS,
  HEADER_ROW_INDEX,
  RECORD_ID_COLUMN,
  REVISION_COLUMN,
  buildWorkbookData,
  getDisplayValue,
  getEditableField,
} from './journal/buildWorkbook';
import type {
  EditableJournalField,
  JournalApiErrorBody,
  JournalCreateRequest,
  JournalCreateResponse,
  JournalDraftSnapshot,
  JournalEventSnapshot,
  JournalEventTypeOption,
  JournalPatchField,
  JournalPatchRequest,
  JournalPatchResponse,
  JournalPatchValue,
  JournalSnapshot,
  JournalTransitionRequest,
} from './journal/types';

const SNAPSHOT_ENDPOINT = '/events/api/v2/snapshot';
const RECORD_ENDPOINT = '/events/api/v2/records';
const DRAFT_ID_PREFIX = 'draft:';
let draftSequence = 0;

type WorksheetFacade = any;

type EditorControls = {
  readonly selection: HTMLElement;
  readonly date: HTMLInputElement;
  readonly time: HTMLInputElement;
  readonly eventType: HTMLSelectElement;
  readonly includeInReport: HTMLInputElement;
  readonly close: HTMLButtonElement;
};

type ShellElements = {
  readonly status: HTMLElement;
  readonly controls: EditorControls;
};

type ActiveRow = {
  readonly worksheet: WorksheetFacade;
  readonly row: number;
  readonly identity: number | string;
};

class JournalApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly current?: JournalEventSnapshot
  ) {
    super(message);
  }
}

function requireRoot(): HTMLElement {
  const root = document.querySelector<HTMLElement>('#app');
  if (!root) {
    throw new Error('Не найден контейнер Journal UI V2.');
  }
  return root;
}

function requireElement<T extends Element>(root: ParentNode, selector: string): T {
  const element = root.querySelector<T>(selector);
  if (!element) {
    throw new Error(`Не найден элемент Journal UI V2: ${selector}`);
  }
  return element;
}

function renderShell(root: HTMLElement): ShellElements {
  root.innerHTML = `
    <section class="shift-helper-v2">
      <header class="shift-helper-v2__header">
        <div class="shift-helper-v2__title">
          <strong>Журнал событий</strong>
          <span>Journal UI V2 · Univer Sheets OSS</span>
        </div>
        <span class="shift-helper-v2__status" role="status">Загрузка данных…</span>
      </header>
      <div class="shift-helper-v2__editor" aria-label="Редактор выбранной строки">
        <span class="shift-helper-v2__selection" data-testid="journal-selection">
          Выберите строку
        </span>
        <label class="shift-helper-v2__field">
          <span>Дата</span>
          <input data-testid="journal-date" type="date" disabled>
        </label>
        <label class="shift-helper-v2__field">
          <span>Время</span>
          <input data-testid="journal-time" type="time" step="60" disabled>
        </label>
        <label class="shift-helper-v2__field shift-helper-v2__field--type">
          <span>Тип события</span>
          <select data-testid="journal-event-type" disabled></select>
        </label>
        <label class="shift-helper-v2__report">
          <input data-testid="journal-report" type="checkbox" disabled>
          <span>В утренний рапорт</span>
        </label>
        <button
          class="shift-helper-v2__close"
          data-testid="journal-close"
          type="button"
          disabled
        >
          Завершить событие
        </button>
      </div>
      <div id="univer-sheet" class="shift-helper-v2__sheet"></div>
    </section>
  `;

  requireElement<HTMLElement>(root, '#univer-sheet');
  return {
    status: requireElement<HTMLElement>(root, '.shift-helper-v2__status'),
    controls: {
      selection: requireElement<HTMLElement>(root, '[data-testid="journal-selection"]'),
      date: requireElement<HTMLInputElement>(root, '[data-testid="journal-date"]'),
      time: requireElement<HTMLInputElement>(root, '[data-testid="journal-time"]'),
      eventType: requireElement<HTMLSelectElement>(root, '[data-testid="journal-event-type"]'),
      includeInReport: requireElement<HTMLInputElement>(root, '[data-testid="journal-report"]'),
      close: requireElement<HTMLButtonElement>(root, '[data-testid="journal-close"]'),
    },
  };
}

function configureEventTypeOptions(
  select: HTMLSelectElement,
  eventTypes: readonly JournalEventTypeOption[]
): void {
  const fragment = document.createDocumentFragment();
  eventTypes.forEach(({ value, label }) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    fragment.append(option);
  });
  select.replaceChildren(fragment);
}

async function loadSnapshot(): Promise<JournalSnapshot> {
  const response = await fetch(SNAPSHOT_ENDPOINT, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  });
  if (!response.ok) {
    throw new Error(`Сервер вернул HTTP ${response.status}.`);
  }

  const data: unknown = await response.json();
  if (
    typeof data !== 'object' ||
    data === null ||
    !('schemaVersion' in data) ||
    data.schemaVersion !== 1 ||
    !('eventTypes' in data) ||
    !Array.isArray(data.eventTypes) ||
    !('records' in data) ||
    !Array.isArray(data.records)
  ) {
    throw new Error('Сервер вернул неподдерживаемый формат журнала.');
  }
  return data as JournalSnapshot;
}

async function apiRecordRequest(
  endpoint: string,
  method: 'PATCH' | 'POST',
  payload: JournalPatchRequest | JournalTransitionRequest
): Promise<JournalEventSnapshot> {
  const response = await fetch(endpoint, {
    method,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    credentials: 'same-origin',
    body: JSON.stringify(payload),
  });

  const body: unknown = await response.json();
  if (!response.ok) {
    const apiError = body as JournalApiErrorBody;
    throw new JournalApiError(
      apiError.error?.message ?? `Сервер вернул HTTP ${response.status}.`,
      response.status,
      apiError.error?.code ?? 'unknown_error',
      apiError.error?.current
    );
  }

  const result = body as JournalPatchResponse;
  if (result.schemaVersion !== 1 || typeof result.record?.id !== 'number') {
    throw new Error('Сервер вернул неподдерживаемый результат операции.');
  }
  return result.record;
}

async function patchRecord(
  recordId: number,
  payload: JournalPatchRequest
): Promise<JournalEventSnapshot> {
  return apiRecordRequest(`${RECORD_ENDPOINT}/${recordId}`, 'PATCH', payload);
}

async function closeRecord(
  recordId: number,
  payload: JournalTransitionRequest
): Promise<JournalEventSnapshot> {
  return apiRecordRequest(`${RECORD_ENDPOINT}/${recordId}/close`, 'POST', payload);
}

async function createRecord(payload: JournalCreateRequest): Promise<JournalCreateResponse> {
  const response = await fetch(RECORD_ENDPOINT, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    credentials: 'same-origin',
    body: JSON.stringify(payload),
  });

  const body: unknown = await response.json();
  if (!response.ok) {
    const apiError = body as JournalApiErrorBody;
    throw new JournalApiError(
      apiError.error?.message ?? `Сервер вернул HTTP ${response.status}.`,
      response.status,
      apiError.error?.code ?? 'unknown_error'
    );
  }

  const created = body as JournalCreateResponse;
  if (
    created.schemaVersion !== 1 ||
    created.clientId !== payload.clientId ||
    typeof created.record?.id !== 'number'
  ) {
    throw new Error('Сервер вернул неподдерживаемый результат создания записи.');
  }
  return created;
}

function renderFailure(root: HTMLElement, error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  root.innerHTML = `
    <section class="shift-helper-v2__error" role="alert">
      <strong>Journal UI V2 не запущен.</strong><br>
      ${escapeHtml(message)}
    </section>
  `;
}

function escapeHtml(value: string): string {
  const element = document.createElement('span');
  element.textContent = value;
  return element.innerHTML;
}

function numericCellValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isInteger(value) && value > 0) return value;
  if (typeof value === 'string' && /^\d+$/.test(value)) return Number(value);
  return null;
}

function draftCellValue(value: unknown): string | null {
  return typeof value === 'string' && value.startsWith(DRAFT_ID_PREFIX) ? value : null;
}

function editableCellValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  return String(value);
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
  const normalized = value?.trim() ?? '';
  return normalized ? value : null;
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

function setControlsEnabled(controls: EditorControls, enabled: boolean): void {
  controls.date.disabled = !enabled;
  controls.time.disabled = !enabled;
  controls.eventType.disabled = !enabled;
  controls.includeInReport.disabled = !enabled;
  if (!enabled) controls.close.disabled = true;
}

function startEditingPersistence(
  univerAPI: ReturnType<typeof createUniver>['univerAPI'],
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

  const setReadyStatus = (): void => {
    const recordCount = new Intl.NumberFormat('ru-RU').format(recordsById.size);
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent = `Загружено записей: ${recordCount} · все изменения сохранены`;
  };

  const setSavingStatus = (): void => {
    status.classList.remove('shift-helper-v2__status--error');
    status.textContent =
      pendingSaveCount > 1 ? `Сохранение изменений: ${pendingSaveCount}…` : 'Сохранение изменения…';
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
    pendingSaveCount -= 1;
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

  const enqueueSave = (queueKey: string, task: () => Promise<void>): void => {
    const previous = saveQueues.get(queueKey) ?? Promise.resolve();
    const next = previous
      .catch(() => undefined)
      .then(task)
      .finally(() => {
        if (saveQueues.get(queueKey) === next) saveQueues.delete(queueKey);
      });
    saveQueues.set(queueKey, next);
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

    if (!model) {
      clearEditorSelection();
      return;
    }

    const identity = recordId ?? draftId;
    if (identity === null) {
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
    setControlsEnabled(controls, true);
    controls.close.disabled = recordId === null || model.status === 'closed';
    controls.close.textContent =
      model.status === 'closed' ? 'Событие завершено' : 'Завершить событие';
  };

  const refreshActiveEditor = (): void => {
    if (activeRow !== null) {
      syncEditorSelection(activeRow.worksheet, activeRow.row);
    }
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
        const updated = await patchRecord(recordId, {
          revision: current.revision,
          changes,
        });
        recordsById.set(recordId, updated);
        restoreRecord(worksheet, updated);
        refreshActiveEditor();
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
        refreshActiveEditor();
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
    if (creatingDrafts.has(draftId)) return;

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
            refreshActiveEditor();
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
    if (activeRow === null || typeof activeRow.identity !== 'string') return;
    const draftId = activeRow.identity;
    const current = draftsById.get(draftId);
    if (!current) return;

    const updated = update(current);
    draftsById.set(draftId, updated);
    applyDraftToRow(activeRow.worksheet, activeRow.row, updated);
    refreshActiveEditor();
    maybeCreateDraft(draftId, activeRow.worksheet);
  };

  controls.date.addEventListener('change', () => {
    if (activeRow === null) return;
    const selectedDate = controls.date.value;
    if (typeof activeRow.identity === 'number') {
      enqueueRecordPatch(activeRow.identity, activeRow.worksheet, (current) => {
        const { time } = splitStartAt(current.startAt);
        const startAt = combineStartAt(selectedDate, time);
        return startAt && startAt !== current.startAt ? { startAt } : {};
      });
      return;
    }
    updateActiveDraft((draft) => {
      const { time } = splitStartAt(draft.startAt);
      const startAt = combineStartAt(selectedDate, time);
      return startAt ? { ...draft, startAt } : draft;
    });
  });

  controls.time.addEventListener('change', () => {
    if (activeRow === null) return;
    const selectedTime = controls.time.value;
    if (typeof activeRow.identity === 'number') {
      enqueueRecordPatch(activeRow.identity, activeRow.worksheet, (current) => {
        const { date } = splitStartAt(current.startAt);
        const startAt = combineStartAt(date, selectedTime);
        return startAt && startAt !== current.startAt ? { startAt } : {};
      });
      return;
    }
    updateActiveDraft((draft) => {
      const { date } = splitStartAt(draft.startAt);
      const startAt = combineStartAt(date, selectedTime);
      return startAt ? { ...draft, startAt } : draft;
    });
  });

  controls.eventType.addEventListener('change', () => {
    if (activeRow === null) return;
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
      return;
    }
    updateActiveDraft((draft) => ({ ...draft, eventType, eventTypeLabel }));
  });

  controls.includeInReport.addEventListener('change', () => {
    if (activeRow === null) return;
    const includeInReport = controls.includeInReport.checked;
    if (typeof activeRow.identity === 'number') {
      enqueueRecordPatch(activeRow.identity, activeRow.worksheet, (current) =>
        current.includeInReport === includeInReport ? {} : { includeInReport }
      );
      return;
    }
    updateActiveDraft((draft) => ({ ...draft, includeInReport }));
  });

  controls.close.addEventListener('click', () => {
    if (activeRow === null || typeof activeRow.identity !== 'number') return;
    const record = recordsById.get(activeRow.identity);
    if (!record || record.status === 'closed') return;
    enqueueRecordClose(record.id, activeRow.worksheet);
  });

  univerAPI.addEvent(univerAPI.Event.BeforeSheetEditStart, (params) => {
    const { row, column, worksheet } = params;
    const identity = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
    const recordId = numericCellValue(identity);
    const draftId = draftCellValue(identity);
    const editableIdentity =
      (recordId !== null && recordsById.has(recordId)) ||
      (draftId !== null && draftsById.has(draftId));

    if (row === HEADER_ROW_INDEX || !editableIdentity || getEditableField(column) === null) {
      params.cancel = true;
    }
  });

  univerAPI.addEvent(univerAPI.Event.SheetEditEnded, ({ row, column, worksheet }) => {
    const field = getEditableField(column);
    if (field === null) return;

    const identity = worksheet.getRange(row, RECORD_ID_COLUMN).getValue();
    const recordId = numericCellValue(identity);
    const draftId = draftCellValue(identity);
    const value = editableCellValue(worksheet.getRange(row, column).getValue());

    if (recordId !== null) {
      const existing = recordsById.get(recordId);
      if (!existing || value === String(getDisplayValue(existing, column, row - 1))) return;

      enqueueRecordPatch(recordId, worksheet, () => {
        const changes: Partial<Record<JournalPatchField, JournalPatchValue>> = {
          [field]: value,
        };
        return changes;
      });
      return;
    }

    if (draftId === null) return;
    const existingDraft = draftsById.get(draftId);
    if (!existingDraft) return;

    const updatedDraft = updateDraftField(existingDraft, field, value);
    draftsById.set(draftId, updatedDraft);
    if (activeRow?.identity === draftId) refreshActiveEditor();
    maybeCreateDraft(draftId, worksheet);
  });

  univerAPI.addEvent(univerAPI.Event.SelectionChanged, ({ worksheet }) => {
    if (!worksheet) {
      clearEditorSelection();
      return;
    }
    const currentCell = worksheet.getSelection().getCurrentCell();
    if (!currentCell) {
      clearEditorSelection();
      return;
    }
    syncEditorSelection(worksheet, currentCell.actualRow);
  });

  univerAPI.addEvent(univerAPI.Event.CellClicked, ({ row, worksheet }) => {
    if (worksheet) syncEditorSelection(worksheet, row);
  });

  clearEditorSelection();
  setReadyStatus();
}

async function start(): Promise<void> {
  document.documentElement.lang = 'ru';
  const root = requireRoot();
  const { status, controls } = renderShell(root);

  try {
    const snapshot = await loadSnapshot();
    configureEventTypeOptions(controls.eventType, snapshot.eventTypes);
    const draft = createDraft(snapshot.eventTypes);
    const { univerAPI } = createUniver({
      locale: LocaleType.EN_US,
      locales: {
        [LocaleType.EN_US]: mergeLocales(sheetsCoreEnUS),
      },
      presets: [
        UniverSheetsCorePreset({
          container: 'univer-sheet',
        }),
      ],
    });

    startEditingPersistence(univerAPI, snapshot, draft, status, controls);
    univerAPI.createWorkbook(buildWorkbookData(snapshot, draft));
  } catch (error) {
    renderFailure(root, error);
  }
}

void start();
