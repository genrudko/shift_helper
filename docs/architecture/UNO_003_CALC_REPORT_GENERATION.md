# UNO-003 — Calc-native morning report generation

## Goal

Expose the accepted emergency-outage report slice in the existing docked
Shift-Helper Calc toolbar without requiring CLI commands or an external executable.

## Operator flow

1. Keep the event journal open in LibreOffice Calc.
2. Invoke `Сформировать утренний рапорт`.
3. Enter the report date (`ДД.ММ.ГГГГ`). The date is the end of the accepted
   previous-day 07:00 to report-day 07:00 window.
4. Select the approved new-report `.xlsx` template.
5. Select a separate `.xlsx` output path.
6. Inspect the generated workbook before uploading it to the closed site.

Cancellation at any dialog creates no published output.

## Data boundary

- The currently open journal is read through UNO and is never stored or modified by
  the report command.
- Only columns B, C, D, E, F, I and J of sheet `ЖС` are read.
- The known D1 mismatch (`40` instead of `№ ВЭУ`) remains a warning.
- The known leading row-2 chronology outlier is excluded exactly as in PIVOT-001.
- Rows with structural value errors are ignored and counted.
- Event selection reuses `shift_helper.core.selection` unchanged.

## Report boundary

- The template is copied to a hidden pending `.xlsx` file.
- LibreOffice opens the pending copy hidden and verifies sheet
  `Аварийные отключения ЛЭП` and headers B3:F3.
- Only B:F data rows and the date in B1 are changed.
- The hidden result is stored, closed, reopened read-only and structurally verified.
- Only after successful verification is the pending file atomically moved to the
  requested output path.

## Dependency boundary

The OXT does not vendor or import `openpyxl`. The Calc runtime uses only UNO,
Python standard library modules and bundled pure Shift-Helper modules.

## Acceptance gate

CI can verify package structure, pure selection/normalization logic and Python/XML
syntax. Merge still requires a real Windows LibreOffice run and visual inspection of
all report sheets because UNO round-trip fidelity cannot be proven in CI.
