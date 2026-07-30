export interface JournalRowSnapshot {
  startAt: string;
  endAt: string | null;
  assetLabel: string;
  eventType: string;
  description: string;
  reason: string | null;
  actions: string | null;
  performer: string | null;
  errorCodes: string | null;
  rotorLimit: string | null;
  repairPowerMw: string | null;
  status: string;
  includeInReport: boolean;
  enteredBy: string;
  downtimeMinutes: number | null;
  losses: string | null;
}

export interface JournalEventSnapshot extends JournalRowSnapshot {
  id: number;
  revision: number;
}

export interface JournalDraftSnapshot extends JournalRowSnapshot {
  clientId: string;
}

export interface JournalSnapshot {
  schemaVersion: 2;
  generatedAt: string;
  records: JournalEventSnapshot[];
}

export type EditableJournalField =
  | 'assetLabel'
  | 'description'
  | 'reason'
  | 'actions'
  | 'performer';

export type JournalPatchField =
  | EditableJournalField
  | 'startAt'
  | 'endAt'
  | 'eventType'
  | 'includeInReport'
  | 'rotorLimit';

export type JournalPatchValue = string | null | boolean;

export interface JournalPatchRequest {
  revision: number;
  changes: Partial<Record<JournalPatchField, JournalPatchValue>>;
}

export interface JournalPatchResponse {
  schemaVersion: 2;
  record: JournalEventSnapshot;
}

export interface JournalCreateValues {
  startAt: string;
  endAt: string | null;
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
  schemaVersion: 2;
  clientId: string;
  record: JournalEventSnapshot;
}

export interface JournalBatchOperation {
  recordId: number;
  revision: number;
  changes: Partial<Record<JournalPatchField, JournalPatchValue>>;
}

export interface JournalBatchRequest {
  operations: JournalBatchOperation[];
}

export interface JournalBatchResponse {
  schemaVersion: 2;
  records: JournalEventSnapshot[];
}

export interface JournalDeleteOperation {
  recordId: number;
  revision: number;
}

export interface JournalDeleteRequest {
  operations: JournalDeleteOperation[];
}

export interface JournalDeleteResponse {
  schemaVersion: 2;
  deletedRecordIds: number[];
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
