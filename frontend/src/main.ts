import { UniverSheetsCorePreset } from '@univerjs/preset-sheets-core';
import sheetsCoreRuRU from '@univerjs/preset-sheets-core/locales/ru-RU';
import { createUniver, LocaleType, mergeLocales } from '@univerjs/presets';

import '@univerjs/preset-sheets-core/lib/index.css';
import './styles.css';

import { loadPresentation, loadSnapshot } from './journal/api';
import { buildWorkbookData, DISPLAY_COLUMNS } from './journal/buildWorkbook';
import { startJournalClearSelection } from './journal/clearSelection';
import {
  JOURNAL_MENU_CONFIG,
  startJournalCommandSafety,
} from './journal/commandSafety';
import { startJournalController } from './journal/controller';
import { startOperationHistoryControls } from './journal/operationHistory';
import {
  applyPresentation,
  startPresentationPersistence,
} from './journal/presentation';
import { startRuntimeFileControls } from './journal/runtimeFiles';
import { renderFailure, renderShell } from './journal/shell';
import { startZoomControl } from './journal/zoomControl';

function requireRoot(): HTMLElement {
  const root = document.querySelector<HTMLElement>('#app');
  if (!root) throw new Error('Не найден контейнер журнала событий.');
  return root;
}

async function start(): Promise<void> {
  document.documentElement.lang = 'ru';
  const root = requireRoot();
  const { status, controls } = renderShell(root);
  startRuntimeFileControls();
  startOperationHistoryControls();

  try {
    const [snapshot, presentation] = await Promise.all([
      loadSnapshot(),
      loadPresentation(),
    ]);
    const { univerAPI } = createUniver({
      locale: LocaleType.RU_RU,
      locales: {
        [LocaleType.RU_RU]: mergeLocales(sheetsCoreRuRU),
      },
      presets: [
        UniverSheetsCorePreset({
          container: 'univer-sheet',
          menu: JOURNAL_MENU_CONFIG,
          sheets: {
            disableForceStringAlert: true,
            disableForceStringMark: true,
          },
          footer: {
            sheetBar: true,
            statisticBar: true,
            menus: true,
            zoomSlider: false,
            addSheetButtonConfig: {
              show: false,
            },
          },
        }),
      ],
    });

    const workbookData = applyPresentation(
      buildWorkbookData(snapshot),
      presentation,
      DISPLAY_COLUMNS.length
    );
    const workbook = univerAPI.createWorkbook(workbookData);
    document.documentElement.dataset.journalForm = 'approved-js-12';
    document.documentElement.dataset.journalColumns = DISPLAY_COLUMNS
      .map((column) => column.title)
      .join('|');
    startJournalController(univerAPI, snapshot, status, controls);
    startZoomControl(
      univerAPI,
      presentation.presentation.sheet.zoomRatio
    );
    startJournalClearSelection(univerAPI, status);
    startJournalCommandSafety(univerAPI);
    startPresentationPersistence(
      univerAPI,
      workbook,
      presentation,
      DISPLAY_COLUMNS.length,
      status
    );
  } catch (error) {
    renderFailure(root, error);
  }
}

void start();
