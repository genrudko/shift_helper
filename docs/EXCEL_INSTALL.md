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
8. Confirm that the **Shift-Helper** Ribbon tab is visible and its commands have icons.

If your organization blocks unsigned VBA add-ins, use the Office Trust Center policy approved by your administrator. Do not weaken system-wide macro security just for testing.

## Runtime UI contract

- **Календарь** opens a compact native Windows month-calendar above Excel. It must show an actual month grid with normal month navigation and must not create a temporary Excel workbook.
- **Настройки Outlook** is an in-Ribbon settings menu. Editing one value may use a standard Excel input dialog, but it must never create a temporary Excel workbook or window.
- **Автовысота строк** applies Excel AutoFit to the selected rows from their cell contents. It must not ask the operator to enter a numeric row height.
- every top-level Shift-Helper Ribbon command has an icon; the add-in obtains Office-native images at runtime and has a safe built-in fallback.
- **Подготовить полный контур рапорта** creates missing Shift-Helper report/input sheets inside the current journal when required.
- journal commands (**Сортировать**, **Объединить и копировать**, **Очистить пробелы**, **Автовысота строк**) operate only in the active Shift-Helper journal context.
- a separate workbook is expected only for a genuine user document, such as the generated final morning report, or a generation source opened read-only during import.

## Acceptance sequence

Prefer the accepted `Shift-Helper-Journal-ACCEPTANCE-006.xlsx` baseline for controlled acceptance, then repeat the relevant checks on the real operational journal.

1. Open the journal and leave its original workbook format unchanged.
2. Verify that the **Shift-Helper** Ribbon shows icons for all commands.
3. On **Shift-Helper → Рапорт**, press **Календарь**. Verify a compact calendar window with a month grid appears, month navigation works, no second workbook appears, and selecting a date changes `Подготовка рапорта!B3`.
4. Open **Настройки Outlook**. Verify the settings stay in the Ribbon, persist after editing, and no `Outlook` workbook appears.
5. Select journal rows with short and wrapped/multiline text and run **Автовысота строк**. Verify row heights fit the contents automatically and no numeric height prompt appears.
6. On a journal without a prepared report contour, run **Подготовить полный контур рапорта**. Verify missing report/input sheets are added to the same journal without a raw VBA `Subscript out of range` error.
7. Run **Импортировать генерацию**. With Outlook unavailable or with no matching message, verify the configured manual `.xlsx` fallback instead of a crash.
8. Verify `Ввод - Основные!C6 = C10 / 24000` and the accepted C15 remaining-power calculation.
9. Verify all 84 WTG rows on `Ввод - Состояние ВЭУ`, the visible `Статус ВЭУ` column, `P расп. = MAX(P уставка - P ремонт, 0)` and GTP sums.
10. Run the WTG rotor/power-limit action and verify only the corresponding state rows change.
11. Check `Ввод - Аварийные отключения` for the selected 07:00→07:00 window.
12. Generate the full morning report. No report-template picker must appear. The output workbook must contain exactly the approved seven sheets.
13. With a non-zero `Подготовка рапорта!B6`, compare source timestamps and generated-report timestamps. The source journal must remain unchanged.
14. Exercise journal sorting, merge-and-copy and whitespace cleanup on real rows. Verify these commands do not affect another open workbook.
15. On `График осмотров КТП`, run **Текущий день / текущая смена** and verify navigation to the real current row. If the sheet is absent, the add-in must report the missing sheet instead of a raw `Subscript out of range` error.
16. Save and close the shared journal. Confirm the shared `.xlsx` still contains no VBA/ActiveX/customUI parts.
17. Open the same saved `.xlsx` in LibreOffice Calc and verify structure, formulas, formats and the existing Calc extension workflow.

A green GitHub build proves package structure and cross-platform contracts. It does **not** replace this live Excel Desktop acceptance gate.
