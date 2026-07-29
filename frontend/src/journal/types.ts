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

export interface JournalSnapshot {
  schemaVersion: 1;
  generatedAt: string;
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

export interface JournalPatchRequest {
  revision: number;
  changes: Partial<Record<EditableJournalField, string | null>>;
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
