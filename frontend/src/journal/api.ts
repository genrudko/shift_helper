import type {
  JournalApiErrorBody,
  JournalBatchRequest,
  JournalBatchResponse,
  JournalCreateRequest,
  JournalCreateResponse,
  JournalEventSnapshot,
  JournalPatchRequest,
  JournalPatchResponse,
  JournalSnapshot,
  JournalTransitionRequest,
} from './types';

const SNAPSHOT_ENDPOINT = '/events/api/v2/snapshot';
const RECORD_ENDPOINT = '/events/api/v2/records';

export class JournalApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly current?: JournalEventSnapshot,
    readonly operationIndex?: number,
    readonly recordId?: number
  ) {
    super(message);
  }
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
    data.error?.current,
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
  if (
    data.schemaVersion !== 1 ||
    !Array.isArray(data.eventTypes) ||
    !Array.isArray(data.records)
  ) {
    throw new Error('Сервер вернул неподдерживаемый формат журнала.');
  }
  return data;
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
  if (result.schemaVersion !== 1 || typeof result.record?.id !== 'number') {
    throw new Error('Сервер вернул неподдерживаемый результат сохранения.');
  }
  return result.record;
}

export async function closeRecord(
  recordId: number,
  payload: JournalTransitionRequest
): Promise<JournalEventSnapshot> {
  const result = await mutationRequest<JournalPatchResponse>(
    `${RECORD_ENDPOINT}/${recordId}/close`,
    payload
  );
  if (result.schemaVersion !== 1 || typeof result.record?.id !== 'number') {
    throw new Error('Сервер вернул неподдерживаемый результат завершения события.');
  }
  return result.record;
}

export async function createRecord(
  payload: JournalCreateRequest
): Promise<JournalCreateResponse> {
  const result = await mutationRequest<JournalCreateResponse>(RECORD_ENDPOINT, payload);
  if (
    result.schemaVersion !== 1 ||
    result.clientId !== payload.clientId ||
    typeof result.record?.id !== 'number'
  ) {
    throw new Error('Сервер вернул неподдерживаемый результат создания записи.');
  }
  return result;
}

export async function patchRecordsBatch(
  payload: JournalBatchRequest
): Promise<JournalEventSnapshot[]> {
  const result = await mutationRequest<JournalBatchResponse>(
    `${RECORD_ENDPOINT}/batch`,
    payload
  );
  if (result.schemaVersion !== 1 || !Array.isArray(result.records)) {
    throw new Error('Сервер вернул неподдерживаемый результат пакетной операции.');
  }
  return result.records;
}
