# Shift-Helper for Microsoft Excel — installation and acceptance

## Target

- Windows x64;
- desktop Microsoft Excel from Microsoft 365 / a current perpetual release;
- classic Outlook Desktop is optional and is used for generation import and mail-draft creation.

The shared Shift-Helper journal remains an ordinary macro-free `.xlsx`. Do not convert it to `.xlsm` just to use the add-in. VBA, application events, Ribbon code and Windows-specific UI remain inside `Shift-Helper-Excel.xlam`.

## Install or replace the add-in

1. Close **all** Excel windows before replacing an existing Shift-Helper build.
2. Keep `Shift-Helper-Excel.xlam` in a stable local folder, for example `Documents\Shift-Helper`.
3. If Windows shows **Разблокировать / Unblock** in the file properties, apply it.
4. Open Excel → **Файл → Параметры → Надстройки**.
5. At the bottom select **Управление: Надстройки Excel → Перейти… → Обзор…**.
6. Choose `Shift-Helper-Excel.xlam` and enable it.
7. Reopen the journal if it was already open.
8. Confirm that the **Shift-Helper** Ribbon tab is visible and its commands have icons.

If organizational policy blocks unsigned VBA add-ins, use the Office Trust Center policy approved by the administrator. Do not weaken system-wide macro security just for Shift-Helper testing.

## Ribbon contract

### Журнал

- **Сортировать по времени** — stable sort of selected journal rows A:R by time in column C; accepted formula columns are made absolute before movement.
- **Объединить и копировать** — joins selected non-empty cells and puts Unicode text into the Windows clipboard.
- **Очистить пробелы** — normalizes tabs, line breaks, NBSP and repeated spaces in selected text cells.
- **Автовысота строк** — native Excel AutoFit from cell contents; no numeric row-height prompt.
- **Вставить дату** — opens the calendar and inserts the selected date into the selected cells.
- **Вставить время** — enters one `ЧЧ:ММ` value into the selected cells.

### Рапорт

- **Подготовить полный контур** — creates missing Shift-Helper input/report workspace sheets in the current journal.
- **Дата рапорта** — opens the month calendar and updates `Подготовка рапорта!B3` and the accepted 07:00→07:00 window.
- **Сформировать утренний рапорт** — generates the approved seven-sheet report into a separate `.xlsx` without asking for an external template.

The approved report template is compiled into the XLAM VBA payload and is reconstructed directly in `%TEMP%` through Base64 decode. Runtime report preparation does **not** depend on Explorer/Shell ZIP extraction.

### Outlook

- **Импортировать генерацию** — searches classic Outlook Desktop using saved mailbox/folder/mask/filter settings and falls back to manual `.xlsx` selection when configured.
- **Настройки импорта** — edits mailbox, folder, attachment mask, subject/sender filters, search depth and manual fallback.
- **Создать черновик письма** — creates and displays an Outlook draft from the accepted active-sheet fields; Shift-Helper never sends the message automatically.

### Инструменты

- **Текст ТО ВЭУ** — inserts the accepted maintenance wording for selected WTGs, including 6-month or annual maintenance and optional bolt-contact torque check.
- **Ограничения ВЭУ** — resolves the latest active rotor/power limitation before report time and applies the accepted exact repair-power mapping.
- **Осмотры текущей смены** — selects the current day/current shift row on `График осмотров КТП` using the accepted day-number and Д/Н schedule contract.

### Быстрый ввод

Automatic quick input works only on `ЖС` columns B, C, I and J and is enabled by default. The Ribbon provides **Включить / Состояние / Выключить**.

Accepted compact tokens include:

- date: `.`, `!`, `+N`, day-only, `ДДММ`, `ДДММГГ`, `ДДММГГГГ` and normal date separators;
- time: `.`, `!`, `+N`, hour-only, `ЧММ`, `ЧЧММ` and `ЧЧ:ММ`;
- `+N` time input performs midnight rollover into the paired date column when possible.

Invalid compact tokens stay visible instead of silently replacing source data.

## Runtime UI rules

- Calendar is a compact owned Windows month-calendar above Excel; it must not create another Excel workbook.
- Outlook settings must not create a fake settings workbook.
- AutoFit must not ask for a row height.
- Journal selection tools must not mutate a different open workbook.
- Separate workbooks are legitimate only for real user documents such as the generated final report or a generation source opened read-only.
- Report-output time offset is applied only to generated report timestamps and never rewrites source journal timestamps.

## Acceptance sequence

Prefer `Shift-Helper-Journal-ACCEPTANCE-006.xlsx` for controlled acceptance, then repeat relevant checks on the real operational journal.

1. Open the journal and keep its original workbook format unchanged.
2. Confirm all five Ribbon groups and their icons are visible.
3. Run **Дата рапорта**. Verify an actual month grid appears, month navigation works, no second workbook appears and selecting a date updates `Подготовка рапорта!B3`.
4. Select ordinary cells and run **Вставить дату** and **Вставить время**.
5. Select wrapped/multiline rows and run **Автовысота строк**. Verify no height InputBox appears.
6. On a disposable journal missing the report workspace, run **Подготовить полный контур**. No external report-template picker and no `File not found`/raw VBA error may appear.
7. Verify `Ввод - Основные!C6 = C10 / 24000`, the accepted C15 remaining-power calculation and dynamic date/title captions.
8. Verify 84 WTGs on `Ввод - Состояние ВЭУ`, visible status in column L, `P расп. = MAX(P уставка - P ремонт, 0)` and commercial-group sums.
9. Run **Ограничения ВЭУ** and verify only the corresponding state rows change, including the accepted discrete limitation mapping.
10. Verify `Ввод - Аварийные отключения` contains only accepted events in the selected 07:00→07:00 window.
11. Run **Импортировать генерацию**. With Outlook unavailable or no matching attachment, verify configured manual `.xlsx` fallback rather than a crash.
12. Exercise **Настройки импорта** and verify settings persist.
13. On a disposable sheet configured for the accepted draft fields, run **Создать черновик письма** and verify Outlook displays a draft but does not send it.
14. Run **Текст ТО ВЭУ** on a disposable selected cell/range and verify accepted wording and automatic row fit.
15. On `ЖС`, test quick input in B/C/I/J, including `.`, `!`, `+N`, compact date/time and midnight rollover. Toggle quick input off/on and verify the state persists.
16. Select at least two real journal rows and run **Сортировать по времени**. Verify A:R move together and dependent formulas remain tied to their original row data.
17. Exercise **Объединить и копировать** and **Очистить пробелы**.
18. On `График осмотров КТП`, run **Осмотры текущей смены** and verify navigation to the current day/current Д/Н row.
19. Generate the full morning report. No template picker may appear; the output must contain exactly the approved seven report sheets.
20. With non-zero `Подготовка рапорта!B6`, compare source and generated timestamps. Source journal timestamps must remain unchanged.
21. Save and close the shared journal. Confirm the shared `.xlsx` still contains no VBA/ActiveX/customUI parts.
22. Open the same saved `.xlsx` in LibreOffice Calc and verify structure, formulas, formats and the accepted Calc extension workflow.

A green GitHub build proves package structure, VBA/Ribbon presence and shared cross-platform contracts. It does **not** replace the live Microsoft Excel Desktop acceptance gate.
