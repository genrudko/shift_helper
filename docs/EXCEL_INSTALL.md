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

## Report station profile

The Excel add-in supports one shared macro-free journal contract with two report profiles:

- `Кочубеевская ВЭС` — 84 WTGs and the accepted Kochubeevskaya report structure;
- `Кузьминская ВЭС` — 64 WTGs / 7 GTP groups and the station-specific main/report-state structure from the owner-provided 08.08.2026 reference report.

Use **Shift-Helper → Рапорт → Станция** to select the report profile for the current station journal. The choice is stored in hidden Shift-Helper metadata in that workbook. Report preparation, report-date handling, generation import, WTG rotor-limit refresh and final report generation use the selected profile.

Kuzminskaya WTG group order is:

1. WTG 1–16 — `GVIE0531`;
2. WTG 33–40 — `GVIE0543`;
3. WTG 57–64 — `GVIE0545`;
4. WTG 25–32 — `GVIE0546`;
5. WTG 41–48 — `GVIE0547`;
6. WTG 49–56 — `GVIE0549`;
7. WTG 17–24 — `GVIE0555`.

The service-only WTG status column remains on the prepared input sheet for calculation/state logic and is removed from the final report.

Generation import supports both source workbook contracts. Kuzminskaya Outlook lookup is constrained to a Kuz-named same-day XLSX while retaining manual-file fallback.

## Current live-acceptance focus

The current candidate retains the live-Excel repairs found during owner testing:

- no temporary workbook is used for Calendar or Outlook settings;
- report preparation, generation import, Calendar date application and WTG rotor-limit processing do not use invalid `Workbook.Calculate` calls;
- report input recalculation is bounded to the seven report-input worksheets;
- formula application is performed while Excel calculation/events/screen repaint are temporarily suspended and then restored;
- journal event scans used by report outages and WTG rotor limits read bounded worksheet arrays instead of thousands of cell-by-cell calls;
- Excel Error/Null/Empty values are guarded before text/date/numeric conversion;
- remaining runtime failures include `[#error] Stage [...]` diagnostics;
- WTG rotor-limit refresh uses the same bounded calculation path and exact accepted limit mapping;
- final report is built from the prepared station sheets, preserving dynamic rows and formatting.

## Immediate verification sequence

After loading the newest XLAM:

1. Select **Shift-Helper → Рапорт → Станция → Кузьминская ВЭС**.
2. Run **Подготовить полный контур**.
3. Verify `Ввод - Основные`: installed power 160 MW and Kuzminskaya 2026 monthly plan.
4. Verify `Ввод - Состояние ВЭУ`: 64 WTGs, seven GTP blocks in the listed order, merged station/GTP columns, service status column present.
5. Select report date and run **Импортировать генерацию** with a Kuzminskaya source workbook/Outlook attachment.
6. Run **Сформировать утренний рапорт**.
7. Verify the final `Состояние ВЭУ` ends at the visible report columns (service status is absent), contains the 64-WTG/7-GTP layout, and the main sheet is titled for Kuzminskaya.
8. Repeat the accepted Kochubeevskaya path to confirm no regression.

If any operation fails, capture the complete Shift-Helper message including the numeric error and `Stage [...]` text.

## Shared workbook contract

The XLAM may modify values, formulas, formatting and worksheets required by the accepted Shift-Helper workflow, but it must not save VBA, ActiveX or Ribbon parts into the shared journal. Report generation creates a separate `.xlsx` output workbook. The normal operator flow never asks for an external report template.
