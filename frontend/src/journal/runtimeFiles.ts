import './runtimeFiles.css';

type RuntimeFileState = {
  status: string;
  generatedAt: string | null;
  lastError: string | null;
  downloadAvailable: boolean;
  downloadUrl: string | null;
};

type RuntimeStatus = {
  schemaVersion: 1;
  eventMirror: RuntimeFileState & { recordCount: number };
  databaseBackup: RuntimeFileState & {
    eventCount: number;
    auditCount: number;
    sha256: string | null;
  };
};

const STATUS_ENDPOINT = '/events/api/v2/runtime-status';
const REFRESH_INTERVAL_MS = 20_000;

function createDownloadLink(testId: string, label: string): HTMLAnchorElement {
  const link = document.createElement('a');
  link.className = 'shift-helper-v2__runtime-link';
  link.dataset.testid = testId;
  link.textContent = label;
  link.setAttribute('aria-disabled', 'true');
  return link;
}

function configureDownload(
  link: HTMLAnchorElement,
  state: RuntimeFileState,
  fallbackTitle: string
): void {
  if (state.downloadAvailable && state.downloadUrl) {
    link.href = state.downloadUrl;
    link.setAttribute('download', '');
    link.setAttribute('aria-disabled', 'false');
    link.title = state.generatedAt
      ? `${fallbackTitle}. Обновлено: ${state.generatedAt}`
      : fallbackTitle;
    return;
  }
  link.removeAttribute('href');
  link.removeAttribute('download');
  link.setAttribute('aria-disabled', 'true');
  link.title = state.lastError ?? `${fallbackTitle} пока недоступна.`;
}

function validRuntimeStatus(value: unknown): value is RuntimeStatus {
  const candidate = value as RuntimeStatus;
  return (
    candidate?.schemaVersion === 1 &&
    typeof candidate.eventMirror?.downloadAvailable === 'boolean' &&
    typeof candidate.databaseBackup?.downloadAvailable === 'boolean'
  );
}

export function startRuntimeFileControls(): void {
  const header = document.querySelector<HTMLElement>('.shift-helper-v2__header');
  const status = document.querySelector<HTMLElement>('.shift-helper-v2__status');
  if (!header || !status) throw new Error('Не найдена шапка журнала для файловых операций.');

  const container = document.createElement('div');
  container.className = 'shift-helper-v2__runtime-files';
  container.dataset.testid = 'runtime-files';
  container.dataset.state = 'loading';

  const indicator = document.createElement('span');
  indicator.className = 'shift-helper-v2__runtime-indicator';
  indicator.dataset.testid = 'runtime-files-indicator';
  indicator.textContent = 'Проверка файлов…';

  const spreadsheetLink = createDownloadLink('download-event-xlsx', 'Excel-копия');
  const backupLink = createDownloadLink('download-latest-backup', 'Резервная копия');
  container.append(indicator, spreadsheetLink, backupLink);
  header.insertBefore(container, status);

  const refresh = async (): Promise<void> => {
    try {
      const response = await fetch(STATUS_ENDPOINT, {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload: unknown = await response.json();
      if (!validRuntimeStatus(payload)) {
        throw new Error('Неподдерживаемый формат состояния файлов.');
      }

      configureDownload(
        spreadsheetLink,
        payload.eventMirror,
        'Скачать актуальную Excel-копию журнала'
      );
      configureDownload(
        backupLink,
        payload.databaseBackup,
        'Скачать последнюю проверенную резервную копию'
      );

      const ready =
        payload.eventMirror.downloadAvailable &&
        payload.databaseBackup.downloadAvailable;
      container.dataset.state = ready ? 'ready' : 'warning';
      indicator.textContent = ready ? 'Файлы готовы' : 'Требуется внимание';
      indicator.title = [
        payload.eventMirror.lastError,
        payload.databaseBackup.lastError,
      ]
        .filter(Boolean)
        .join(' | ');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      container.dataset.state = 'error';
      indicator.textContent = 'Файлы недоступны';
      indicator.title = message;
      configureDownload(
        spreadsheetLink,
        {
          status: 'error',
          generatedAt: null,
          lastError: message,
          downloadAvailable: false,
          downloadUrl: null,
        },
        'Excel-копия недоступна'
      );
      configureDownload(
        backupLink,
        {
          status: 'error',
          generatedAt: null,
          lastError: message,
          downloadAvailable: false,
          downloadUrl: null,
        },
        'Резервная копия недоступна'
      );
    }
  };

  void refresh();
  window.setInterval(() => void refresh(), REFRESH_INTERVAL_MS);
}
