# UNO-003 — Calc-native morning report generation

## Goal

Expose the complete morning-report workflow inside the existing Shift-Helper Calc
extension while keeping the event journal as the primary working document and never
requiring an external executable.

## Operator flow

1. Keep the event journal open in LibreOffice Calc.
2. Invoke `Подготовить полный контур рапорта`.
3. On `Подготовка рапорта`, set:
   - B3 — report date;
   - B6 — output time offset in hours, initially `-3`.
4. Fill or verify the six `Ввод - …` sheets.
5. Invoke `Импортировать генерацию`; use the classic Outlook attachment or select an
   `.xlsx` file manually.
6. Invoke `Сформировать полный утренний рапорт`.
7. Select the approved new-report template and a separate output path.
8. Inspect all seven generated report sheets before uploading the file to the closed
   site.

Cancellation at a file dialog creates no published output.

## Workspace contract

`Подготовить полный контур рапорта` creates or repairs these sheets without clearing
operator data:

- `Подготовка рапорта`;
- `Ввод - Основные`;
- `Ввод - Команды`;
- `Ввод - Нарушения`;
- `Ввод - Состояние ВЭУ`;
- `Ввод - Работы`;
- `Ввод - Дефекты`.

The preparation pass reapplies real Calc table borders, column widths, headers,
wrapping and input/derived-cell fills to existing sheets. It also restores formulas
for all 84 WTG rows and planned-work rows.

`Подготовка рапорта!B3` is the sole editable report date. The legacy date cell on
`Ввод - Основные` is a formula reference to B3. Importing a previous report updates
B3 and the displayed 07:00–07:00 window.

## Power and status contract

For each WTG:

```text
P располагаемая = MAX(P уставка - P ремонт; 0)
```

`P уставка` cannot exceed installed power and `P ремонт` cannot exceed the setpoint.
Commercial GTP rows in the report sum their child WTGs. The overall available power
is the sum of normalized WTG available powers.

WTG counts are mutually exclusive and evaluated in this order:

1. accident;
2. repair;
3. stopped, including zero available power;
4. working, including a non-zero constrained state.

Thus one WTG cannot simultaneously inflate `останов`, `авария` and `ремонт`.

## Plan contract

For report date `D`, plan-to-date uses only fully elapsed days:

```text
elapsed_days = D.day - 1
plan_to_date = month_plan * elapsed_days / days_in_month
```

Deviation is `month_generation - plan_to_date`; completion is the ratio to the same
plan-to-date value. Required average power uses the ungenerated monthly balance and
the hours remaining from the beginning of the report date through month end.

## Time-offset contract

`Подготовка рапорта!B6` accepts a numeric value from `-24` to `+24` hours. The value
is applied only while writing the generated report to:

- emergency event timestamps;
- external-command timestamps;
- violation timestamps;
- WTG stop and planned-return timestamps;
- planned-work timestamps;
- defect timestamps.

The setting does not modify the source journal and does not shift the accepted
07:00–07:00 selection window. The initial `-3` value compensates for the closed site
adding three hours after upload.

## Data boundary

- The currently open journal is read through UNO and is not saved by the report
  command.
- Emergency events are read from columns B, C, D, E, F, I and J of `ЖС`.
- The known D1 mismatch (`40` instead of `№ ВЭУ`) remains a warning.
- The known leading row-2 chronology outlier is excluded exactly as in PIVOT-001.
- Rows with structural value errors are ignored and counted.
- Event selection reuses `shift_helper.core.selection` unchanged.

## Report boundary

- The approved template is copied to a hidden pending `.xlsx` file.
- LibreOffice fills all seven required report sheets.
- The hidden result is stored, closed, reopened read-only and structurally verified.
- Only after successful verification is the pending file atomically moved to the
  requested output path.
- The source journal and template cannot be selected as the output path.

## Dependency boundary

The OXT does not vendor or import `openpyxl`. The Calc runtime uses only UNO,
Python standard-library modules and bundled pure Shift-Helper modules.

## Acceptance gate

CI verifies package structure, deterministic build, decoded runtime syntax and
contract markers. Merge still requires a real Windows LibreOffice run and visual
inspection because CI cannot prove UNO table-border rendering, formula recalculation
or `.xlsx` round-trip fidelity.
