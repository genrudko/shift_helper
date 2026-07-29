export interface JournalEventSnapshot {
  id: number;
  revision: number;
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

export interface JournalApiErrorBody {
  error: {
    code: string;
    message: string;
    current?: JournalEventSnapshot;
  };
}
