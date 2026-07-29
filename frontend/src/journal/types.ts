export interface JournalRowSnapshot {
  startAt: string;
  endAt: string | null;
  assetLabel: string;
  eventType: string;
  eventTypeLabel: string;
  description: string;
  reason: string | null;
  actions: string | null;
  performer: string | null;
  errorCodes: string | null;
  rotorLimit: string | null;
  repairPowerMw: string | null;
  status: 'open' | 'closed';
  includeInReport: boolean;
}

export interface JournalEventSnapshot extends JournalRowSnapshot {
  id: number;
  revision: number;
}

export interface JournalDraftSnapshot extends JournalRowSnapshot {
  clientId: string;
}

export interface JournalEventTypeOption {
  value: string;
  label: string;
}

export interface JournalSnapshot {
  schemaVersion: 1;
  generatedAt: string;
  eventTypes: JournalEventTypeOption[];
  records: JournalEventSnapshot[];
}

export type EditableJournalField =
  | 'assetLabel'
  | 'description'
  | 'reason'
  | 'actions'
  | 'performer'
  | 'errorCodes'
  | 'rotorLimit';

export type JournalPatchField =
  | EditableJournalField
  | 'startAt'
  | 'eventType'
  | 'includeInReport';

export type JournalPatchValue = string | null | boolean;

export interface JournalPatchRequest {
  revision: number;
  changes: Partial<Record<JournalPatchField, JournalPatchValue>>;
}

export interface JournalTransitionRequest {
  revision: number;
}

export interface JournalPatchResponse {
  schemaVersion: 1;
  record: JournalEventSnapshot;
}

export interface JournalCreateValues {
  startAt: string;
  assetLabel: string;
  eventType: string;
  description: string;
  reason: string | null;
  actions: string | null;
  performer: string | null;
  errorCodes: string | null;
  rotorLimit: string | null;
  includeInReport: boolean;
}

export interface JournalCreateRequest {
  clientId: string;
  values: JournalCreateValues;
}

export interface JournalCreateResponse {
  schemaVersion: 1;
  clientId: string;
  record: JournalEventSnapshot;
}

export interface JournalBatchOperation {
  recordId: number;
  revision: number;
  changes: Partial<Record<EditableJournalField, string | null>>;
}

export interface JournalBatchRequest {
  operations: JournalBatchOperation[];
}

export interface JournalBatchResponse {
  schemaVersion: 1;
  records: JournalEventSnapshot[];
}

export interface JournalOperationSummary {
  operationId: string;
  kind: string;
  label: string;
  reversible: boolean;
  actor: string | null;
  clientIp: string | null;
  createdAt: string;
  recordIds: number[];
  recordCount: number;
}

export interface JournalOperationState {
  schemaVersion: 1;
  canUndo: boolean;
  canRedo: boolean;
  undo: JournalOperationSummary | null;
  redo: JournalOperationSummary | null;
  undoReason: string | null;
}

export interface JournalOperationTransitionResponse {
  schemaVersion: 1;
  direction: 'undo' | 'redo';
  operationId: string;
  records: JournalEventSnapshot[];
  state: JournalOperationState;
}

export type JournalPresentationStyle = string | Record<string, unknown>;

export interface JournalPresentationDimension {
  w?: number;
  h?: number;
  hd?: 0 | 1;
}

export interface JournalPresentationPayload {
  schemaVersion: 1;
  workbookStyles: Record<string, unknown>;
  sheet: {
    zoomRatio: number;
    freeze: {
      startRow: number;
      startColumn: number;
      ySplit: number;
      xSplit: number;
    };
    columnData: Record<string, JournalPresentationDimension>;
    rowData: Record<string, JournalPresentationDimension>;
    cellStyles: Record<string, Record<string, JournalPresentationStyle>>;
  };
}

export interface JournalPresentationState {
  schemaVersion: 1;
  revision: number;
  updatedAt: string | null;
  presentation: JournalPresentationPayload;
}

export interface JournalPresentationSaveRequest {
  revision: number;
  presentation: JournalPresentationPayload;
}

export interface JournalApiErrorBody {
  error: {
    code: string;
    message: string;
    current?: unknown;
    state?: JournalOperationState;
    operationIndex?: number;
    recordId?: number;
  };
}
