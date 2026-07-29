import './zoomControl.css';

const MIN_ZOOM_PERCENT = 10;
const MAX_ZOOM_PERCENT = 400;
const ZOOM_STEP_PERCENT = 10;

function clampZoom(value: number): number {
  if (!Number.isFinite(value)) return 100;
  return Math.min(MAX_ZOOM_PERCENT, Math.max(MIN_ZOOM_PERCENT, Math.round(value)));
}

function button(testId: string, label: string, symbol: string): HTMLButtonElement {
  const control = document.createElement('button');
  control.type = 'button';
  control.className = 'shift-helper-v2__zoom-button';
  control.dataset.testid = testId;
  control.setAttribute('aria-label', label);
  control.title = label;
  control.textContent = symbol;
  return control;
}

export function startZoomControl(univerAPI: any, initialRatio: number): void {
  const header = document.querySelector<HTMLElement>('.shift-helper-v2__header');
  const history = document.querySelector<HTMLElement>('.shift-helper-v2__history-controls');
  const status = document.querySelector<HTMLElement>('.shift-helper-v2__status');
  const sheetContainer = document.querySelector<HTMLElement>('#univer-sheet');
  if (!header || !status || !sheetContainer) {
    throw new Error('Не найден контейнер для управления масштабом.');
  }

  const container = document.createElement('div');
  container.className = 'shift-helper-v2__zoom-control';
  container.dataset.testid = 'journal-zoom';

  const decrease = button('journal-zoom-out', 'Уменьшить масштаб на 10%', '−');
  const slider = document.createElement('input');
  slider.type = 'range';
  slider.className = 'shift-helper-v2__zoom-range';
  slider.dataset.testid = 'journal-zoom-range';
  slider.min = String(MIN_ZOOM_PERCENT);
  slider.max = String(MAX_ZOOM_PERCENT);
  slider.step = String(ZOOM_STEP_PERCENT);
  slider.setAttribute('aria-label', 'Масштаб журнала');

  const number = document.createElement('input');
  number.type = 'number';
  number.className = 'shift-helper-v2__zoom-number';
  number.dataset.testid = 'journal-zoom-number';
  number.min = String(MIN_ZOOM_PERCENT);
  number.max = String(MAX_ZOOM_PERCENT);
  number.step = '1';
  number.inputMode = 'numeric';
  number.setAttribute('aria-label', 'Масштаб журнала в процентах');

  const percent = document.createElement('span');
  percent.className = 'shift-helper-v2__zoom-percent';
  percent.textContent = '%';

  const increase = button('journal-zoom-in', 'Увеличить масштаб на 10%', '+');
  container.append(decrease, slider, number, percent, increase);
  header.insertBefore(container, history ?? status);

  let currentPercent = clampZoom(initialRatio * 100);

  const render = (): void => {
    slider.value = String(currentPercent);
    number.value = String(currentPercent);
    container.dataset.zoom = String(currentPercent);
    container.title = `Масштаб журнала: ${currentPercent}%`;
    decrease.disabled = currentPercent <= MIN_ZOOM_PERCENT;
    increase.disabled = currentPercent >= MAX_ZOOM_PERCENT;
  };

  const apply = (value: number): void => {
    const next = clampZoom(value);
    if (next === currentPercent) {
      render();
      return;
    }
    const worksheet = univerAPI.getActiveWorkbook?.()?.getActiveSheet?.();
    if (!worksheet || typeof worksheet.zoom !== 'function') {
      throw new Error('Univer не предоставил управление масштабом листа.');
    }
    worksheet.zoom(next / 100);
    currentPercent = next;
    render();
  };

  slider.addEventListener('input', () => apply(Number(slider.value)));
  number.addEventListener('change', () => apply(Number(number.value)));
  number.addEventListener('blur', render);
  decrease.addEventListener('click', () => apply(currentPercent - ZOOM_STEP_PERCENT));
  increase.addEventListener('click', () => apply(currentPercent + ZOOM_STEP_PERCENT));
  sheetContainer.addEventListener(
    'wheel',
    (event) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      event.preventDefault();
      apply(
        currentPercent +
          (event.deltaY < 0 ? ZOOM_STEP_PERCENT : -ZOOM_STEP_PERCENT)
      );
    },
    { passive: false }
  );

  render();
  document.documentElement.dataset.zoomControl = 'active';
}
