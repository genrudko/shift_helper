# Shift-Helper — Microsoft Excel Desktop

## Files

Excel runtime uses:

- the shared journal workbook (`.xlsx` or an existing working copy opened by the operator);
- `Shift-Helper-Excel.xlam` as the Excel add-in.

The add-in must not be embedded into the shared journal. The journal remains the common workbook used by Excel and LibreOffice Calc.

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

## Current live-acceptance focus

The current candidate contains the live-Excel repairs found during owner testing:

- no temporary workbook is used for Calendar or Outlook settings;
- report preparation, generation import and Calendar date application no longer use invalid `Workbook.Calculate` calls;
- report input recalculation is bounded to the seven report-input worksheets;
- formula application is performed while Excel calculation/events/screen repaint are temporarily suspended and then restored;
- journal event scans used by report outages and WTG rotor limits read bounded worksheet arrays instead of thousands of cell-by-cell calls;
- Excel Error/Null/Empty values are guarded before text/date/numeric conversion;
- remaining runtime failures include `[#error] Stage [...]` diagnostics;
- WTG rotor-limit refresh uses the same bounded calculation path and exact accepted limit mapping.

## Immediate verification sequence

After loading the newest XLAM:

1. Open **Shift-Helper → Рапорт → Календарь**.
2. Select a different report date and verify that `Подготовка рапорта!B3` changes with no error 438.
3. Run **Подготовить полный контур рапорта** and confirm that it completes without the previous multi-minute wait / `Type mismatch`.
4. Run **Импортировать генерацию**. If Outlook cannot supply the expected file, verify the configured manual `.xlsx` fallback instead of a crash.
5. Run **Ограничение по оборотам / мощности ВЭУ** and verify that it completes without `Object doesn't support this property or method`.
6. Continue the full report-generation and operator-tool acceptance sequence.

If any of these operations still fails, capture the complete Shift-Helper message including the numeric error and `Stage [...]` text. That diagnostic identifies the remaining runtime boundary directly.

## Ribbon scope

The add-in exposes operator functions for:

- journal time sorting;
- merge-and-copy;
- whitespace cleanup;
- automatic row height;
- date and time input;
- full report-contour preparation;
- report-date Calendar;
- full morning report generation;
- classic-Outlook generation import and settings;
- Outlook draft creation;
- WTG maintenance text;
- WTG rotor/power-limit refresh;
- current-day/current-shift inspection navigation;
- automatic quick-input enable/status/disable.

## Shared workbook contract

The XLAM may modify values, formulas, formatting and worksheets required by the accepted Shift-Helper workflow, but it must not save VBA, ActiveX or Ribbon parts into the shared journal. Report generation creates a separate `.xlsx` output workbook from the embedded approved seven-sheet report template. The normal operator flow never asks for an external report template.