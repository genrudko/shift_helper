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
