import type {
  JournalApiErrorBody,
  JournalBatchRequest,
  JournalBatchResponse,
  JournalCreateRequest,
  JournalCreateResponse,
  JournalDeleteRequest,
  JournalDeleteResponse,
  JournalEventSnapshot,
  JournalOperationState,
  JournalOperationTransitionResponse,
  JournalPatchRequest,
  JournalPatchResponse,
  JournalPresentationSaveRequest,
  JournalPresentationState,
  JournalSnapshot,
} from './types';

const SNAPSHOT_ENDPOINT = '/events/api/v3/snapshot';
const RECORD_ENDPOINT = '/events/api/v3/records';
const PRESENTATION_ENDPOINT = '/events/api/v2/presentation';
const OPERATION_ENDPOINT = '/events/api/v2/operations';
export const JOURNAL_DATA_MUTATED_EVENT = 'shift-helper:data-mutated';

export class JournalApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly current?: JournalEventSnapshot,
    readonly operationState?: JournalOperationState,
    readonly operationIndex?: number,
    readonly recordId?: number
  ) {
    super(message);
  }
}

export class JournalPresentationConflictError extends Error {
  constructor(
    message: string,
    readonly current: JournalPresentationState
  ) {
    super(message);
  }
}

function notifyDataMutation(): void {
  window.dispatchEvent(new CustomEvent(JOURNAL_DATA_MUTATED_EVENT));
}

async function jsonResponse(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new Error(`Сервер вернул HTTP ${response.status} без JSON-ответа.`);
  }
}

function apiError(response: Response, body: unknown): JournalApiError {
  const data = body as JournalApiErrorBody;
  return new JournalApiError(
    data.error?.message ?? `Сервер вернул HTTP ${response.status}.`,
    response.status,
    data.error?.code ?? 'unknown_error',
    data.error?.current as JournalEventSnapshot | undefined,
    data.error?.state,
    data.error?.operationIndex,
    data.error?.recordId
  );
}

async function mutationRequest<T>(endpoint: string, payload: object): Promise<T> {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    credentials: 'same-origin',
    body: JSON.stringify(payload),
  });
  const body = await jsonResponse(response);
  if (!response.ok) throw apiError(response, body);
  return body as T;
}

export async function loadSnapshot(): Promise<JournalSnapshot> {
  const response = await fetch(SNAPSHOT_ENDPOINT, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  });
  const body = await jsonResponse(response);
  if (!response.ok) throw apiError(response, body);
  const data = body as JournalSnapshot;
  if (data.schemaVersion !== 2 || !Array.isArray(data.records)) {
    throw new Error('Сервер вернул неподдерживаемый формат журнала.');
  }
  return data;
}

export async function loadOperationState(): Promise<JournalOperationState> {
  const response = await fetch(`${OPERATION_ENDPOINT}/state`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  });
  const body = await jsonResponse(response);
  if (!response.ok) throw apiError(response, body);
  const data = body as JournalOperationState;
  if (
    data.schemaVersion !== 1 ||
    typeof data.canUndo !== 'boolean' ||
    typeof data.canRedo !== 'boolean'
  ) {
    throw new Error('Сервер вернул неподдерживаемое состояние отмены.');
  }
  return data;
}

export async function transitionOperation(
  direction: 'undo' | 'redo',
  operationId: string
): Promise<JournalOperationTransitionResponse> {
  const result = await mutationRequest<JournalOperationTransitionResponse>(
    `${OPERATION_ENDPOINT}/${direction}`,
    { operationId }
  );
  if (
    result.schemaVersion !== 1 ||
    result.direction !== direction ||
    result.operationId !== operationId ||
    !Array.isArray(result.records)
  ) {
    throw new Error('Сервер вернул неподдерживаемый результат операции истории.');
  }
  return result;
}

export async function loadPresentation(): Promise<JournalPresentationState> {
  const response = await fetch(PRESENTATION_ENDPOINT, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  });
  const body = await jsonResponse(response);
  if (!response.ok) throw apiError(response, body);
  const data = body as JournalPresentationState;
  if (
    data.schemaVersion !== 1 ||
    typeof data.revision !== 'number' ||
    data.presentation?.schemaVersion !== 1
  ) {
    throw new Error('Сервер вернул неподдерживаемое оформление журнала.');
  }
  return data;
}

export async function savePresentation(
  payload: JournalPresentationSaveRequest
): Promise<JournalPresentationState> {
  const response = await fetch(PRESENTATION_ENDPOINT, {
    method: 'PUT',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    credentials: 'same-origin',
    body: JSON.stringify(payload),
  });
  const body = await jsonResponse(response);
  if (!response.ok) {
    const data = body as JournalApiErrorBody;
    const current = data.error?.current as JournalPresentationState | undefined;
    if (response.status === 409 && current?.presentation?.schemaVersion === 1) {
      throw new JournalPresentationConflictError(
        data.error.message ?? 'Оформление изменено на другом рабочем месте.',
        current
      );
    }
    throw apiError(response, body);
  }
  const result = body as JournalPresentationState;
  if (
    result.schemaVersion !== 1 ||
    typeof result.revision !== 'number' ||
    result.presentation?.schemaVersion !== 1
  ) {
    throw new Error('Сервер вернул неподдерживаемый результат сохранения оформления.');
  }
  return result;
}

export async function patchRecord(
  recordId: number,
  payload: JournalPatchRequest
): Promise<JournalEventSnapshot> {
  const response = await fetch(`${RECORD_ENDPOINT}/${recordId}`, {
    method: 'PATCH',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    credentials: 'same-origin',
    body: JSON.stringify(payload),
  });
  const body = await jsonResponse(response);
  if (!response.ok) throw apiError(response, body);
  const result = body as JournalPatchResponse;
  if (result.schemaVersion !== 2 || typeof result.record?.id !== 'number') {
    throw new Error('Сервер вернул неподдерживаемый результат сохранения.');
  }
  notifyDataMutation();
  return result.record;
}

export async function createRecord(
  payload: JournalCreateRequest
): Promise<JournalCreateResponse> {
  const result = await mutationRequest<JournalCreateResponse>(RECORD_ENDPOINT, payload);
  if (
    result.schemaVersion !== 2 ||
    result.clientId !== payload.clientId ||
    typeof result.record?.id !== 'number'
  ) {
    throw new Error('Сервер вернул неподдерживаемый результат создания записи.');
  }
  notifyDataMutation();
  return result;
}

export async function patchRecordsBatch(
  payload: JournalBatchRequest
): Promise<JournalEventSnapshot[]> {
  const result = await mutationRequest<JournalBatchResponse>(
    `${RECORD_ENDPOINT}/batch`,
    payload
  );
  if (result.schemaVersion !== 2 || !Array.isArray(result.records)) {
    throw new Error('Сервер вернул неподдерживаемый результат пакетной операции.');
  }
  notifyDataMutation();
  return result.records;
}

export async function deleteRecords(
  payload: JournalDeleteRequest
): Promise<number[]> {
  const result = await mutationRequest<JournalDeleteResponse>(
    `${RECORD_ENDPOINT}/delete`,
    payload
  );
  if (result.schemaVersion !== 2 || !Array.isArray(result.deletedRecordIds)) {
    throw new Error('Сервер вернул неподдерживаемый результат удаления строк.');
  }
  notifyDataMutation();
  return result.deletedRecordIds;
}
