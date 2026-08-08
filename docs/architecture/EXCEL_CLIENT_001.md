# EXCEL-CLIENT-001 — Microsoft Excel desktop client

## Scope

`EXCEL-CLIENT-001` adds a Microsoft Excel Desktop / Windows x64 runtime without replacing the accepted LibreOffice runtime or changing the shared-workbook principle.

```text
LibreOffice Calc:
  Shift-Helper-Journal.xlsx + Shift-Helper-Calc.oxt

Microsoft Excel Desktop:
  Shift-Helper-Journal.xlsx + Shift-Helper-Excel.xlam
```

The shared journal stays macro-free. VBA, Ribbon callbacks, Excel application events, Outlook COM automation and Windows-only UI live in the XLAM.

`Shift-Helper-Journal-ACCEPTANCE-006.xlsx` remains the accepted visual/structural baseline. Private operational workbooks are not committed to Git; repository gates use source contracts, synthetic workbooks and the approved embedded report-template payload.

## Authority and parity rule

The accepted Calc implementation is the functional reference for the Excel port. Platform-specific APIs may differ, but operator-visible behavior and workbook semantics must remain equivalent where the feature applies to both runtimes.

Shared facts are owned by `src/shift_helper/core/workbook_contract.py`, including:

- exact journal/input/report sheet names and seven-sheet report order;
- report date `Подготовка рапорта!B3`;
- generated-output offset `Подготовка рапорта!B6`;
- previous-day 07:00 inclusive → report-day 07:00 exclusive selection window;
- WTG count `84` and statuses `Работа`, `Останов`, `Авария`, `Ремонт`;
- authoritative WTG status in column L of `Ввод - Состояние ВЭУ`;
- available power `MAX(P уставка - P ремонт, 0)`;
- average previous-day load `daily_generation_kwh / 24000`;
- remaining-power calculation including the report date and `-1` ahead-of-plan sentinel;
- approved report-template identity and exact seven-sheet order.

## Excel add-in packaging

`Shift-Helper-Excel.xlam` is generated from source-controlled VBA plus generated VBA contract/payload modules.

Two copies of the approved report template are intentionally present at package level for different purposes:

1. an OOXML package part `shift_helper_report_template.xlsx`, used by the build verifier to fail closed on exact template content;
2. the same template bytes encoded into generated VBA module `modShiftHelperTemplatePayload`, used by the Excel runtime.

At runtime `modShiftHelperEmbedded` decodes that Base64 payload through Windows MSXML and ADODB Stream directly into `%TEMP%\ShiftHelper\shift_helper_report_template.xlsx`. The runtime does not depend on Explorer/Shell ZIP extraction and never asks the operator to select an external report template.

The build verifies:

- real `xl/vbaProject.bin` presence;
- Office 2007 Ribbon extensibility relationship for `customUI14.xml`;
- Ribbon namespace/callback integrity;
- all source VBA modules/classes are physically present in the emitted XLAM;
- approved embedded template content and seven-sheet identity;
- generated VBA Base64 payload round-trips to the same exact template bytes.

CI does not contain Microsoft Office, so these gates prove package structure and static contracts, not live Excel execution.

## VBA runtime composition

The XLAM contains standard modules for:

- contract and Unicode helpers;
- journal tools;
- calendar/date selection;
- report bootstrap/calculations/generation;
- Outlook generation import/settings;
- WTG rotor-limit processing;
- current-shift inspection navigation;
- operator utilities such as time entry, maintenance text and Outlook draft;
- quick-input state and normalization;
- Ribbon callbacks and icons;
- generated report-template payload.

`CShiftHelperAppEvents` is a class module with `WithEvents Application`. Ribbon `onLoad` initializes it so worksheet selection/change events can provide automatic quick input without inserting VBA into the journal.

## Ribbon

The XLAM exposes one `Shift-Helper` tab. Every top-level command uses an Office-native image callback with a known fallback.

### Журнал

- Сортировать по времени
- Объединить и копировать
- Очистить пробелы
- Автовысота строк
- Вставить дату
- Вставить время

### Рапорт

- Подготовить полный контур
- Дата рапорта
- Сформировать утренний рапорт

### Outlook

- Импортировать генерацию
- Настройки импорта
- Создать черновик письма

### Инструменты

- Текст ТО ВЭУ
- Ограничения ВЭУ
- Осмотры текущей смены

### Быстрый ввод

- Включить
- Состояние
- Выключить

Callbacks always resolve the active Shift-Helper journal and selection ownership before mutation. The XLAM itself is never treated as the journal.

## Journal tools

### Stable sort

The accepted Calc sort semantics are retained:

- sort selected journal rows as whole A:R records;
- time key is column C;
- formula columns K and N:R are converted to absolute A1 references before row movement;
- a temporary very-hidden worksheet carries an original-order helper column so equal-time rows remain stable;
- temporary content is deleted before returning control to the operator.

### Merge/copy and whitespace cleanup

Unicode merge/copy uses the Windows clipboard API and never creates a dialog workbook. Whitespace cleanup affects only selected non-formula text cells. Both commands restore row height with native AutoFit where appropriate.

### AutoFit

Row height is content-driven through Excel `EntireRow.AutoFit`. There is no arbitrary numeric-height prompt.

## Date/time UI

No Microsoft Date and Time Picker ActiveX dependency and no temporary workbook-as-dialog are allowed.

Calendar commands host Windows `SysMonthCal32` in a small owned popup above Excel. The implementation deliberately avoids Win32 window-procedure subclassing because that proved too fragile in the first live Excel acceptance attempt.

Two date use cases are distinct:

- **Дата рапорта** updates only `Подготовка рапорта!B3` plus B4/B5 07:00 boundaries; it does not bootstrap the whole report merely to show a calendar;
- **Вставить дату** writes the selected date into the selected cells.

Time insertion writes one validated `ЧЧ:ММ` value to selected cells using ordinary Excel input UI.

## Automatic quick input

Application-level events provide the accepted compact journal input behavior on `ЖС` columns B/C/I/J without modifying the journal VBA project.

Supported compact forms include repeat (`.`), current date/time (`!`), relative `+N`, compact numeric date/time tokens and ordinary separators. Relative time crossing midnight changes the paired date cell when a valid paired date exists. Invalid tokens remain visible and generate diagnostics rather than silently changing factual journal data.

Quick-input enable state is stored per user through VBA settings and is controlled from the Ribbon.

## Report workspace and formulas

`SH_EnsureReportContour` first ensures the preparation sheet, then checks whether any approved input form is missing. The embedded template is reconstructed/opened only when a missing form actually needs to be copied. Repeated preparation of an already prepared workbook therefore does not perform unnecessary template extraction.

Critical formulas are re-applied explicitly, including:

- dynamic report title/date captions;
- C6 average load;
- elapsed-month plan, deviation, ratio and C15 remaining power;
- monthly/year-to-date plan/fact totals;
- WTG available power and commercial-group sums;
- status counts in accepted visible order: Останов / Работа / Авария / Ремонт;
- planned-work available-power formulas.

Emergency outage selection retains the accepted legacy 07:00→07:00 filtering rules.

## Report generation

Generation:

1. validates the active journal and report contour;
2. takes B3 as the sole report date;
3. reconstructs and opens the embedded approved template;
4. verifies exact seven-sheet order;
5. transfers prepared values to the template sheets;
6. applies B6 only to output timestamp columns;
7. saves a separate `.xlsx` chosen by the operator;
8. never overwrites source journal values or the XLAM.

## WTG rotor/power limits

The latest matching add/remove event before report time wins, independent of journal row order. Repair-power mapping matches the accepted discrete Calc contract exactly:

- `< 0.70 → 2.50 MW`;
- `0.70 → 1.40`;
- `0.75 → 1.20`;
- `0.80 → 1.00`;
- `0.85 → 0.75`;
- `0.90 → 0.55`;
- `>= 0.95 → 0`;
- any other intermediate value → `0.45 MW`.

## Current-shift inspections

Excel follows the accepted Calc schedule shape rather than searching for a full Excel date. It scans the schedule rows, carries the day number from column A, compares the current Д/Н shift in column B and selects through the last assigned inspection column.

## Outlook

Classic Outlook Desktop is accessed only through late-bound COM; the VBA project has no Outlook reference dependency.

Generation import supports saved mailbox/folder/attachment mask, optional subject/sender filters, search depth, `.xlsx` attachment validation and manual-file fallback. The source generation workbook is opened read-only.

The Outlook draft tool reads the accepted active-sheet fields, creates an Outlook mail item and displays it. Shift-Helper never calls `Send` automatically.

## Shared-workbook compatibility

No Excel command is allowed to persist `xl/vbaProject.bin`, ActiveX or customUI parts into the shared journal. Formulas that belong in the workbook remain formulas and use functions supported by current Excel and Calc.

The same saved `.xlsx` must remain usable by the accepted Calc OXT workflow after Excel-side operation.

## Acceptance boundary

Automated gates cover calculations, mappings, Ribbon callback topology, event-class/payload packaging, embedded-template integrity, operator-tool parity contracts and Calc regression.

Final acceptance still requires live Microsoft Excel Desktop Windows x64, because only Office can prove actual VBA compilation/runtime behavior, native calendar rendering, Outlook COM behavior and event handling. PR #17 remains Draft until the owner explicitly accepts it and commands the next transition.
