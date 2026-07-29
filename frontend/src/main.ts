import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import sheetsCoreRuRU from '@univerjs/preset-sheets-core/locales/ru-RU';
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';

import '@univerjs/preset-sheets-core/lib/index.css';
import './styles.css';

import { loadSnapshot } from './journal/api';
import { buildWorkbookData } from './journal/buildWorkbook';
import { createDraft, startJournalController } from './journal/controller';
import {
  configureEventTypeOptions,
  renderFailure,
  renderShell,
} from './journal/shell';

function requireRoot(): HTMLElement {
  const root = document.querySelector<HTMLElement>('#app');
  if (!root) throw new Error('Не найден контейнер журнала событий.');
  return root;
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
      locale: LocaleType.RU_RU,
      locales: {
        [LocaleType.RU_RU]: mergeLocales(sheetsCoreRuRU),
      },
      presets: [
        UniverSheetsCorePreset({
          container: 'univer-sheet',
        }),
      ],
    });

    startJournalController(univerAPI, snapshot, draft, status, controls);
    univerAPI.createWorkbook(buildWorkbookData(snapshot, draft));
  } catch (error) {
    renderFailure(root, error);
  }
}

void start();
