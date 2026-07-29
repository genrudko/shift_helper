import './operationHistory.css';

import {
  JOURNAL_DATA_MUTATED_EVENT,
  JournalApiError,
  loadOperationState,
  transitionOperation,
} from './api';
import type {
  JournalOperationState,
  JournalOperationSummary,
} from './types';

function operationTitle(
  action: 'Отменить' | 'Повторить',
  operation: JournalOperationSummary | null
): string {
  if (!operation) return `${action}: операция отсутствует.`;
  const records = operation.recordCount === 1
    ? '1 запись'
    : `${operation.recordCount} записей`;
  return `${action}: ${operation.label.toLowerCase()}, ${records}.`;
}

function historyButton(testId: string, label: string, path: string): HTMLButtonElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'shift-helper-v2__history-button';
  button.dataset.testid = testId;
  button.setAttribute('aria-label', label);
  button.disabled = true;
  button.innerHTML = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="${path}" />
    </svg>
    <span>${label}</span>
  `;
  return button;
}

export function startOperationHistoryControls(): void {
  const header = document.querySelector<HTMLElement>('.shift-helper-v2__header');
  const runtimeFiles = document.querySelector<HTMLElement>('.shift-helper-v2__runtime-files');
  const status = document.querySelector<HTMLElement>('.shift-helper-v2__status');
  if (!header || !status) throw new Error('Не найдена шапка журнала для истории операций.');

  const container = document.createElement('div');
  container.className = 'shift-helper-v2__history-controls';
  container.dataset.testid = 'operation-history';
  container.dataset.state = 'loading';

  const undoButton = historyButton(
    'journal-undo',
    'Отменить',
    'M9 7H5v-4M5 7l4-4M5 7h7a7 7 0 1 1-6.2 10.3'
  );
  const redoButton = historyButton(
    'journal-redo',
    'Повторить',
    'M15 7h4v-4M19 7l-4-4M19 7h-7a7 7 0 1 0 6.2 10.3'
  );
  container.append(undoButton, redoButton);
  header.insertBefore(container, runtimeFiles ?? status);

  let state: JournalOperationState | null = null;
  let busy = false;

  const render = (): void => {
    const canUndo = Boolean(state?.canUndo) && !busy;
    const canRedo = Boolean(state?.canRedo) && !busy;
    undoButton.disabled = !canUndo;
    redoButton.disabled = !canRedo;
    undoButton.title = canUndo
      ? operationTitle('Отменить', state?.undo ?? null)
      : state?.undoReason ?? 'Нет операций для отмены.';
    redoButton.title = canRedo
      ? operationTitle('Повторить', state?.redo ?? null)
      : 'Нет операций для повтора.';
    container.dataset.state = busy ? 'busy' : 'ready';
    container.dataset.canUndo = String(Boolean(state?.canUndo));
    container.dataset.canRedo = String(Boolean(state?.canRedo));
  };

  const showError = (message: string): void => {
    container.dataset.state = 'error';
    container.dataset.error = message;
    container.title = message;
  };

  const refresh = async (): Promise<void> => {
    try {
      state = await loadOperationState();
      container.removeAttribute('data-error');
      container.removeAttribute('title');
      render();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      undoButton.disabled = true;
      redoButton.disabled = true;
      showError(`История операций недоступна: ${message}`);
    }
  };

  const execute = async (direction: 'undo' | 'redo'): Promise<void> => {
    if (busy || !state) return;
    const operation = direction === 'undo' ? state.undo : state.redo;
    const allowed = direction === 'undo' ? state.canUndo : state.canRedo;
    if (!allowed || !operation) {
      render();
      return;
    }

    busy = true;
    render();
    try {
      await transitionOperation(direction, operation.operationId);
      window.location.reload();
    } catch (error) {
      if (error instanceof JournalApiError && error.operationState) {
        state = error.operationState;
      }
      const message = error instanceof Error ? error.message : String(error);
      busy = false;
      render();
      showError(message);
    }
  };

  undoButton.addEventListener('click', () => void execute('undo'));
  redoButton.addEventListener('click', () => void execute('redo'));
  window.addEventListener(JOURNAL_DATA_MUTATED_EVENT, () => void refresh());
  document.addEventListener(
    'keydown',
    (event) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
      const key = event.key.toLowerCase();
      const direction = key === 'y' || (key === 'z' && event.shiftKey)
        ? 'redo'
        : key === 'z'
          ? 'undo'
          : null;
      if (direction === null) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      void execute(direction);
    },
    true
  );

  render();
  void refresh();
}
