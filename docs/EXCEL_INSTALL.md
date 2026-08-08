# Shift-Helper — Microsoft Excel Desktop

## Files

Excel runtime uses the shared journal workbook plus `Shift-Helper-Excel.xlam`. The add-in must not be embedded into the shared journal; the journal remains the common workbook used by Excel and LibreOffice Calc.

## Installation

1. Fully close every Microsoft Excel window.
2. Copy `Shift-Helper-Excel.xlam` to a stable local folder.
3. If Windows file Properties shows **Unblock / Разблокировать**, enable it and apply the change.
4. Start Excel.
5. Open **File → Options → Add-ins**.
6. At the bottom choose **Manage: Excel Add-ins → Go**.
7. Choose **Browse**, select `Shift-Helper-Excel.xlam` and enable it.
8. Reopen the working Shift-Helper journal.
9. Confirm that the **Shift-Helper** Ribbon tab appears.

When replacing an acceptance build, first disable/remove the old XLAM, fully close Excel, replace the file, then start Excel again. Excel can cache Ribbon/VBA state for an already loaded add-in.

## Dual-station generation import

The single **Импортировать генерацию** command supports both station workbooks and detects the actual workbook structure rather than relying only on the attachment name.

### Kochubeevskaya VES form

On sheet `Сумма ВЭС` the accepted legacy contract is:

- daily generation — `G26`;
- own use — `Q26`;
- `Q2:Q25` is additionally checked as the expected numeric source range.

### Kuzminskaya VES form

On sheet `Сумма ВЭС` the KuzVES form is identified by the form headers and uses:

- daily generation — `J26` under `Сумма по ВЭС`;
- own use — `Z26` under `потребление в расчет`.

The source generation workbook is explicitly recalculated by Excel before the totals are read. This is required for the formula-driven KuzVES workbook, whose saved OOXML file may not contain cached values for the final formulas.

When both station messages exist for the same date, Outlook discovery also uses the station indicated by the current journal/title so an attachment from the other station is not selected accidentally. The configured attachment mask remains the first match rule; a constrained station/date XLSX fallback is available. Manual `.xlsx` selection remains available when automatic Outlook discovery does not find a suitable attachment.

If Outlook search misses, the diagnostic message reports the configured/resolved folder, station, effective mask, cutoff date, numbers of scanned messages/attachments/XLSX files and sample XLSX attachment names.

## Report-output repair

The final seven-sheet report is now produced from the already prepared input worksheets rather than copying values only inside the historical embedded-template `UsedRange`. This preserves dynamically expanded rows, widths, row heights, borders, wrapping and number/date formats. Formulas are frozen to their calculated values in the final `.xlsx`.

The service-only `Статус ВЭУ` column remains on `Ввод - Состояние ВЭУ` for calculation/state logic but is removed from the generated `Состояние ВЭУ` sheet.

The embedded approved template remains authoritative for creating missing input forms; the normal operator flow never asks for an external report template.

## Current live-acceptance focus

The current candidate also retains the earlier live-Excel repairs:

- no temporary workbook is used for Calendar or Outlook settings;
- report preparation, generation import, Calendar date application and WTG rotor-limit processing do not use invalid `Workbook.Calculate` calls;
- report input recalculation is bounded to the seven report-input worksheets;
- formula application is performed while Excel calculation/events/screen repaint are temporarily suspended and then restored;
- journal event scans used by report outages and WTG rotor limits read bounded worksheet arrays instead of thousands of cell-by-cell calls;
- Excel Error/Null/Empty values are guarded before text/date/numeric conversion;
- remaining runtime failures include `[#error] Stage [...]` diagnostics;
- WTG rotor-limit refresh uses the same bounded calculation path and exact accepted limit mapping.

## Immediate verification sequence

After loading the newest XLAM:

1. Open **Shift-Helper → Рапорт → Календарь** and select the report date.
2. Run **Подготовить полный контур рапорта**.
3. Run **Импортировать генерацию** with the Kochubeevskaya source and verify the G26/Q26 profile.
4. Run the same command with the Kuzminskaya source and verify the J26/Z26 profile after recalculation.
5. Run **Сформировать полный утренний рапорт** and verify that all prepared dynamic rows are present, date/percentage formats are retained, and the service WTG status column is absent from the final report.
6. Run **Ограничение по оборотам / мощности ВЭУ** and continue the remaining operator-tool acceptance sequence.

If an operation fails, capture the complete Shift-Helper message including the numeric error and `Stage [...]` text or the Outlook search diagnostic block.

## Shared workbook contract

The XLAM may modify values, formulas, formatting and worksheets required by the accepted Shift-Helper workflow, but it must not save VBA, ActiveX or Ribbon parts into the shared journal. The shared journal remains an ordinary `.xlsx` workbook usable by both Microsoft Excel and LibreOffice Calc.
