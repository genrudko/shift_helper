import './commandSafety.css';

type MenuItemConfig = {
  readonly hidden: boolean;
  readonly disabled: boolean;
};

const BLOCKED_COMMAND_MESSAGES = new Map<string, string>([
  ['univer.command.undo', 'Отмена пока недоступна для сохранённых записей.'],
  ['univer.command.redo', 'Повтор пока недоступен для сохранённых записей.'],
  ['sheet.command.cut', 'Вырезание диапазона пока недоступно. Используйте копирование и вставку.'],
  ['sheet.command.clear-selection-content', 'Очистка содержимого диапазона пока недоступна.'],
  ['sheet.command.clear-selection-all', 'Полная очистка диапазона пока недоступна.'],
  ['sheet.command.auto-fill', 'Автозаполнение маркером пока недоступно.'],
  ['sheet.command.copy-down', 'Заполнение вниз пока недоступно.'],
  ['sheet.command.copy-right', 'Заполнение вправо пока недоступно.'],
  ['sheet.command.auto-clear-content', 'Перемещение диапазона пока недоступно.'],
  ['sheet.command.insert-row-before', 'Вставка строк пока недоступна.'],
  ['sheet.command.insert-col-before', 'Вставка колонок пока недоступна.'],
  ['sheet.command.insert-range-move-right-confirm', 'Сдвиг ячеек вправо пока недоступен.'],
  ['sheet.command.insert-range-move-down-confirm', 'Сдвиг ячеек вниз пока недоступен.'],
  ['sheet.command.insert-multi-rows-above', 'Вставка строк пока недоступна.'],
  ['sheet.command.insert-multi-rows-after', 'Вставка строк пока недоступна.'],
  ['sheet.command.insert-multi-cols-before', 'Вставка колонок пока недоступна.'],
  ['sheet.command.insert-multi-cols-right', 'Вставка колонок пока недоступна.'],
  ['sheet.command.remove-row-confirm', 'Удаление строк пока недоступно.'],
  ['sheet.command.remove-col-confirm', 'Удаление колонок пока недоступно.'],
  ['sheet.command.delete-range-move-left-confirm', 'Сдвиг ячеек влево пока недоступен.'],
  ['sheet.command.delete-range-move-up-confirm', 'Сдвиг ячеек вверх пока недоступен.'],
  ['sheet.command.add-worksheet-merge', 'Объединение ячеек журнала запрещено.'],
  ['sheet.command.add-worksheet-merge-all', 'Объединение ячеек журнала запрещено.'],
  ['sheet.command.add-worksheet-merge-vertical', 'Объединение ячеек журнала запрещено.'],
  ['sheet.command.add-worksheet-merge-horizontal', 'Объединение ячеек журнала запрещено.'],
  ['sheet.command.remove-worksheet-merge', 'Изменение объединений журнала запрещено.'],
  ['sheet.command.sort-range-asc', 'Сортировка пока недоступна для связанного журнала.'],
  ['sheet.command.sort-range-asc-ext', 'Сортировка пока недоступна для связанного журнала.'],
  ['sheet.command.sort-range-desc', 'Сортировка пока недоступна для связанного журнала.'],
  ['sheet.command.sort-range-desc-ext', 'Сортировка пока недоступна для связанного журнала.'],
  ['sheet.command.sort-range-custom', 'Сортировка пока недоступна для связанного журнала.'],
  ['sheet.command.sort-range-asc-ctx', 'Сортировка пока недоступна для связанного журнала.'],
  ['sheet.command.sort-range-asc-ext-ctx', 'Сортировка пока недоступна для связанного журнала.'],
  ['sheet.command.sort-range-desc-ctx', 'Сортировка пока недоступна для связанного журнала.'],
  ['sheet.command.sort-range-desc-ext-ctx', 'Сортировка пока недоступна для связанного журнала.'],
  ['sheet.command.sort-range-custom-ctx', 'Сортировка пока недоступна для связанного журнала.'],
  ['sheet.command.paste-values', 'Специальная вставка пока недоступна.'],
  ['sheet.command.paste-format', 'Специальная вставка пока недоступна.'],
  ['sheet.command.paste-col-width', 'Специальная вставка пока недоступна.'],
  ['sheet.command.paste-besides-border', 'Специальная вставка пока недоступна.'],
  ['sheet.command.paste-formula', 'Вставка формул в оперативный журнал запрещена.'],
]);

const HIDDEN_ONLY_COMMANDS = [
  'formula-ui.operation.insert-function',
  'formula-ui.operation.more-functions',
  'sheet.menu.sheets-sort',
  'sheet.menu.sheets-sort-ctx',
  'sheet.menu.image',
  'sheet.command.insert-float-image',
  'sheet.command.insert-cell-image',
  'sheet.command.numfmt.set.currency',
  'sheet.command.numfmt.add.decimal.command',
  'sheet.command.numfmt.subtract.decimal.command',
  'sheet.command.numfmt.set.percent',
  'sheet.operation.open.numfmt.panel',
  'sheet.menu.data-validation',
  'data-validation.operation.open-validation-panel',
  'data-validation.command.addRuleAndOpen',
  'sheet.operation.open-pivot-table-range-selector-panel',
  'data-connector.operation.sidebar',
  'sheets-exchange-client.operation.exchange',
  'exchange-client.operation.import-xlsx',
  'exchange-client.operation.export-xlsx',
  'sheet.command.menu-insert-chart',
  'univer.operation.toggle-edit-history',
  'sheet.operation.toggle-comment-panel',
  'sheet.operation.show-comment-modal',
  'sheet.operation.insert-hyper-link-toolbar',
  'sheet.operation.insert-hyper-link',
  'sheet.menu.copy-special',
  'sheet.menu.paste-special',
  'sheet.command.copy-formula-only',
  'sheet.menu.clear-selection',
  'sheet.menu.cell-insert',
  'sheet.menu.delete',
];

const menuIds = new Set([
  ...BLOCKED_COMMAND_MESSAGES.keys(),
  ...HIDDEN_ONLY_COMMANDS,
]);

export const JOURNAL_MENU_CONFIG: Record<string, MenuItemConfig> = Object.fromEntries(
  [...menuIds].map((id) => [id, { hidden: true, disabled: true }])
);

function createSafetyToast(): HTMLElement {
  const workspace = document.querySelector<HTMLElement>('.shift-helper-v2');
  if (!workspace) throw new Error('Не найден контейнер для уведомлений журнала.');
  const toast = document.createElement('div');
  toast.className = 'shift-helper-v2__safety-toast';
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'polite');
  toast.hidden = true;
  workspace.append(toast);
  return toast;
}

export function startJournalCommandSafety(univerAPI: any): void {
  const toast = createSafetyToast();
  let hideTimer: number | null = null;

  const showBlocked = (message: string): void => {
    if (hideTimer !== null) window.clearTimeout(hideTimer);
    toast.textContent = `${message} Данные не изменены.`;
    toast.hidden = false;
    toast.dataset.state = 'visible';
    hideTimer = window.setTimeout(() => {
      toast.hidden = true;
      toast.dataset.state = 'hidden';
      hideTimer = null;
    }, 4_000);
  };

  const blockEvent = (event: any, message: string): void => {
    event.cancel = true;
    showBlocked(message);
  };

  const blockShortcut = (event: KeyboardEvent, message: string): void => {
    event.preventDefault();
    event.stopImmediatePropagation();
    showBlocked(message);
  };

  document.addEventListener(
    'keydown',
    (event) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
      const key = event.key.toLowerCase();
      if (key === 'x') {
        blockShortcut(
          event,
          'Вырезание диапазона пока недоступно. Используйте копирование и вставку.'
        );
      } else if (key === 'z' && event.shiftKey) {
        blockShortcut(event, 'Повтор пока недоступен для сохранённых записей.');
      } else if (key === 'z') {
        blockShortcut(event, 'Отмена пока недоступна для сохранённых записей.');
      } else if (key === 'y') {
        blockShortcut(event, 'Повтор пока недоступен для сохранённых записей.');
      }
    },
    true
  );

  univerAPI.addEvent(univerAPI.Event.BeforeCommandExecute, (event: any) => {
    const message = BLOCKED_COMMAND_MESSAGES.get(event.id);
    if (message) blockEvent(event, message);
  });
  univerAPI.addEvent(univerAPI.Event.BeforeUndo, (event: any) => {
    blockEvent(event, 'Отмена пока недоступна для сохранённых записей.');
  });
  univerAPI.addEvent(univerAPI.Event.BeforeRedo, (event: any) => {
    blockEvent(event, 'Повтор пока недоступен для сохранённых записей.');
  });
  univerAPI.addEvent(univerAPI.Event.BeforeSheetCreate, (event: any) => {
    blockEvent(event, 'Создание дополнительных листов журнала запрещено.');
  });
  univerAPI.addEvent(univerAPI.Event.BeforeSheetDelete, (event: any) => {
    blockEvent(event, 'Удаление листа журнала запрещено.');
  });
  univerAPI.addEvent(univerAPI.Event.BeforeSheetMove, (event: any) => {
    blockEvent(event, 'Перемещение листа журнала запрещено.');
  });
  univerAPI.addEvent(univerAPI.Event.BeforeSheetNameChange, (event: any) => {
    blockEvent(event, 'Переименование листа журнала запрещено.');
  });
  univerAPI.addEvent(univerAPI.Event.BeforeSheetTabColorChange, (event: any) => {
    blockEvent(event, 'Изменение служебного цвета вкладки запрещено.');
  });

  document.documentElement.dataset.commandSafety = 'active';
}
