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

export interface JournalApiErrorBody {
  error: {
    code: string;
    message: string;
    current?: JournalEventSnapshot;
  };
}
