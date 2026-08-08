# Shift-Helper for Microsoft Excel — installation and acceptance

## Target

- Windows x64;
- desktop Microsoft Excel from Microsoft 365 / a current perpetual release;
- classic Outlook Desktop is optional and is used only for generation import.

The shared journal remains an ordinary macro-free `.xlsx`. Do not convert it to `.xlsm`.

## Install or replace the add-in

1. Close Excel completely before replacing an existing acceptance build.
2. Keep `Shift-Helper-Excel.xlam` in a stable local folder, for example `Documents\Shift-Helper`.
3. If Windows shows **Unblock / Разблокировать** in the file properties, apply it.
4. In Excel open **File → Options → Add-ins**.
5. At the bottom select **Manage: Excel Add-ins → Go… → Browse…**.
6. Choose `Shift-Helper-Excel.xlam` and enable it.
7. Reopen the journal if it was already open.
8. Confirm that the **Shift-Helper** Ribbon tab is visible.

If your organization blocks unsigned VBA add-ins, use the Office Trust Center policy approved by your administrator. Do not weaken system-wide macro security just for testing.

## Runtime UI contract

- **Календарь** is an in-Ribbon date menu. It must never create a temporary Excel workbook or window.
- **Настройки Outlook** is an in-Ribbon settings menu. Editing one value may use a standard Excel input dialog, but it must never create a temporary Excel workbook or window.
- **Подготовить полный контур рапорта** creates missing Shift-Helper report/input sheets inside the current journal when required.
- journal commands (**Сортировать**, **Объединить и копировать**, **Очистить пробелы**, **Высота строк**) operate only in the active Shift-Helper journal context.
- a separate workbook is expected only for a genuine user document, such as the generated final morning report, or a generation source opened read-only during import.

## Acceptance sequence

Prefer the accepted `Shift-Helper-Journal-ACCEPTANCE-006.xlsx` baseline for controlled acceptance, then repeat the relevant checks on the real operational journal.

1. Open the journal and leave its original workbook format unchanged.
2. On **Shift-Helper → Рапорт**, open **Календарь**. Verify the date selector stays in the Ribbon and no second workbook appears. Choose a date and verify `Подготовка рапорта!B3` changes.
3. Open **Настройки Outlook**. Verify the settings stay in the Ribbon, persist after editing, and no `Outlook` workbook appears.
4. On a journal without a prepared report contour, run **Подготовить полный контур рапорта**. Verify missing report/input sheets are added to the same journal without a raw VBA `Subscript out of range` error.
5. Run **Импортировать генерацию**. With Outlook unavailable or with no matching message, verify the configured manual `.xlsx` fallback instead of a crash.
6. Verify `Ввод - Основные!C6 = C10 / 24000` and the accepted C15 remaining-power calculation.
7. Verify all 84 WTG rows on `Ввод - Состояние ВЭУ`, the visible `Статус ВЭУ` column, `P расп. = MAX(P уставка - P ремонт, 0)` and GTP sums.
8. Run the WTG rotor/power-limit action and verify only the corresponding state rows change.
9. Check `Ввод - Аварийные отключения` for the selected 07:00→07:00 window.
10. Generate the full morning report. No report-template picker must appear. The output workbook must contain exactly the approved seven sheets.
11. With a non-zero `Подготовка рапорта!B6`, compare source timestamps and generated-report timestamps. The source journal must remain unchanged.
12. Exercise journal sorting, merge-and-copy, whitespace cleanup and row-height commands on real rows. Verify these commands do not affect another open workbook.
13. On `График осмотров КТП`, run **Текущий день / текущая смена** and verify navigation to the real current row. If the sheet is absent, the add-in must report the missing sheet instead of a raw `Subscript out of range` error.
14. Save and close the shared journal. Confirm the shared `.xlsx` still contains no VBA/ActiveX/customUI parts.
15. Open the same saved `.xlsx` in LibreOffice Calc and verify structure, formulas, formats and the existing Calc extension workflow.

A green GitHub build proves package structure and cross-platform contracts. It does **not** replace this live Excel Desktop acceptance gate.
