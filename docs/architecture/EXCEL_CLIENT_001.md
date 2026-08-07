# EXCEL-CLIENT-001 — Microsoft Excel desktop client

## Scope

`EXCEL-CLIENT-001` adds a Microsoft Excel Desktop runtime without replacing the accepted LibreOffice runtime or changing the product's shared-workbook principle.

Target topology:

```text
LibreOffice Calc:
  Shift-Helper-Journal.xlsx
  + Shift-Helper-Calc.oxt

Microsoft Excel Desktop:
  Shift-Helper-Journal.xlsx
  + Shift-Helper-Excel.xlam
```

The journal stays macro-free. VBA, Ribbon callbacks, Outlook automation and Excel-only UI live in the XLAM.

The accepted `Shift-Helper-Journal-ACCEPTANCE-006.xlsx` is the visual/structural journal baseline. It is private operational input and is not committed to Git. Repository tests use contracts, semantic manifests and synthetic workbooks instead of publishing operational data.

## Recovered main boundary

The accepted Calc implementation has three layers that are currently partially interleaved:

1. stable workbook/report rules in `src/shift_helper/core` and `src/shift_helper/uno_adapter/report_generation.py`;
2. UNO-specific document, dialog, toolbar and dispatch code under `packaging/libreoffice_extension`;
3. acceptance repairs in `src/shift_helper/core/acceptance_repairs_006.py` that move authoritative WTG status to the visible state sheet, add outage input, repair calculations and expose Outlook settings.

The Excel port must reuse the stable rules but must not clone UNO APIs, ScriptProvider/dispatch plumbing or Calc-specific clipboard workarounds.

## Canonical cross-platform contract

A small pure-Python contract owns facts that both platform adapters must agree on:

- exact journal/input/report sheet names and report-sheet order;
- report date: `Подготовка рапорта!B3`;
- generated-output time offset: `Подготовка рапорта!B6`;
- report window: previous day 07:00 inclusive through report day 07:00 exclusive;
- journal event source columns and emergency-output mapping;
- exact main-form coordinates;
- WTG count `84` and statuses `Работа`, `Останов`, `Авария`, `Ремонт`;
- visible authoritative WTG status on `Ввод - Состояние ВЭУ`;
- available power rule `MAX(P уставка - P ремонт, 0)`;
- average previous-day load `daily_generation_kwh / 24 / 1000`;
- required remaining mean power from monthly plan, MTD fact and hours remaining from 00:00 of report date through month end;
- the approved embedded report-template SHA-256 and seven-sheet identity.

This contract is intentionally small. Excel/VBA source is generated from it where duplication would otherwise create a second authority.

## Excel add-in packaging

`Shift-Helper-Excel.xlam` is built from source-controlled VBA modules plus the already approved report-template payload.

The approved report sheets are carried inside the add-in workbook itself. Report generation copies those sheets into a new workbook, preserving the original sheet objects and therefore their merges, sizes, styles, number formats and print settings. Normal operator flow never opens a template picker.

The build is required to fail closed if the reconstructed template hash or seven-sheet identity differs from the approved contract.

Because the build environment does not provide Microsoft Office, package-level CI is not treated as runtime acceptance. Structural XLAM/Ribbon/VBA checks and pure contract tests are automated; the owner performs the final real Excel Desktop gate.

## Ribbon

The XLAM exposes one `Shift-Helper` tab with these groups.

### Журнал

- Сортировать по времени
- Объединить и копировать
- Очистить пробелы
- Высота строк

### Рапорт

- Подготовить полный контур рапорта
- Календарь
- Сформировать полный утренний рапорт
- Импортировать генерацию
- Настройки Outlook

### ВЭУ

- Ограничение по оборотам / мощности

### Смена

- Текущий день / текущая смена

Callbacks operate on the active journal workbook. The XLAM never embeds controls or a VBA project into that journal.

## Calendar and settings UI

No Microsoft Date and Time Picker ActiveX dependency is allowed.

The Excel adapter uses dependency-free Excel-native dialog workbooks created at runtime from the XLAM:

- the calendar is a compact temporary workbook/window with a 6x7 month grid and native shapes whose `OnAction` callbacks return the selected date to `Подготовка рапорта!B3`;
- Outlook settings use a compact temporary settings workbook/window with native worksheet cells and buttons, while persistence is shared with the existing `Подготовка рапорта` metadata and may additionally use per-user VBA `SaveSetting`/`GetSetting` as a fallback.

No Excel-only object is persisted into the shared journal.

## Outlook

Classic Outlook Desktop is accessed with late-bound VBA COM automation (`Outlook.Application` / MAPI namespace). No Outlook reference is required in the VBA project.

The operator configures:

- mailbox;
- folder path;
- attachment mask;
- subject substring;
- sender substring;
- search depth in days;
- manual file fallback.

Only expected `.xlsx` attachments are saved to a temporary directory and opened read-only. Attachments are never executed. Generation import validates the expected workbook structure before reading values. Outlook absence, MAPI lookup failure and missing mail are recoverable conditions; configured manual file selection remains available.

## Report generation

Generation follows the accepted Calc semantics:

1. validate the active journal and `Подготовка рапорта` settings;
2. take `B3` as the sole report date;
3. construct a new workbook from the embedded seven approved template sheets;
4. fill main data, emergency outages, external commands, violations, WTG state, planned works and defects;
5. apply `B6` only to timestamps written to the output workbook, never to source journal values or to the event-selection window;
6. save the generated workbook as a separate `.xlsx`;
7. never overwrite the source journal or the XLAM.

## Compatibility gate

Tests must prove that the common journal remains a macro-free OOXML workbook after Excel-side operations. No `xl/vbaProject.bin`, ActiveX part or customUI part may be written to the journal.

Formulas that naturally belong to the workbook remain in the journal and use functions supported by both current Excel and LibreOffice Calc. Platform adapters may reapply the accepted formulas but must not replace them with static values.

## Acceptance boundary

Automated acceptance covers contract calculations, mappings, embedded-template identity, XLAM package shape, Ribbon callbacks, VBA-source static checks and macro-free journal preservation.

Final acceptance requires a real Windows x64 Microsoft 365/Excel Desktop run, followed by reopening the same saved `.xlsx` in LibreOffice. The Draft PR must remain Draft until the owner explicitly accepts and commands the next transition.
