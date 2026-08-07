# Shift-Helper for Microsoft Excel — installation and acceptance

## Target

- Windows x64;
- desktop Microsoft Excel from Microsoft 365 / a current perpetual release;
- classic Outlook Desktop is optional and is used only for generation import.

The shared journal remains an ordinary macro-free `.xlsx`. Do not convert it to `.xlsm`.

## Install the add-in

1. Keep `Shift-Helper-Excel.xlam` in a stable local folder, for example `Documents\Shift-Helper`.
2. In Excel open **File → Options → Add-ins**.
3. At the bottom select **Manage: Excel Add-ins → Go… → Browse…**.
4. Choose `Shift-Helper-Excel.xlam` and enable it.
5. Reopen the accepted `Shift-Helper-Journal.xlsx` if it was already open.
6. Confirm that the **Shift-Helper** Ribbon tab is visible.

If your organization blocks unsigned VBA add-ins, use the Office Trust Center policy approved by your administrator. Do not weaken system-wide macro security just for testing.

## Acceptance sequence

Use the accepted `Shift-Helper-Journal-ACCEPTANCE-006.xlsx` baseline (it may be renamed to `Shift-Helper-Journal.xlsx`).

1. Open the journal and leave it as `.xlsx`.
2. On **Shift-Helper → Рапорт**, open **Календарь** and choose a date. Verify `Подготовка рапорта!B3` changes.
3. Open **Настройки Outlook**, save mailbox/folder/mask/filter/search-depth/fallback settings, close and reopen the dialog, and verify persistence.
4. Run **Импортировать генерацию**. With Outlook unavailable or with no matching message, verify the configured manual `.xlsx` fallback instead of a crash.
5. Verify `Ввод - Основные!C6 = C10 / 24000` and the accepted C15 remaining-power calculation.
6. Verify all 84 WTG rows on `Ввод - Состояние ВЭУ`, the visible `Статус ВЭУ` column, `P расп. = MAX(P уставка - P ремонт, 0)` and GTP sums.
7. Run the WTG rotor/power-limit action and verify only the corresponding state rows change.
8. Check `Ввод - Аварийные отключения` for the selected 07:00→07:00 window.
9. Generate the full morning report. No report-template picker must appear. The output workbook must contain exactly the approved seven sheets.
10. With a non-zero `Подготовка рапорта!B6`, compare source timestamps and generated-report timestamps. The source journal must remain unchanged.
11. Exercise journal sorting, merge-and-copy, whitespace cleanup and row-height commands on real rows.
12. On `График осмотров КТП`, run **Текущий день / текущая смена** and verify navigation to the real current row.
13. Save and close the journal. Confirm it is still `.xlsx` and contains no VBA/ActiveX/customUI parts.
14. Open the same saved `.xlsx` in LibreOffice Calc and verify structure, formulas, formats and the existing Calc extension workflow.

A green GitHub build proves package structure and cross-platform contracts. It does **not** replace this live Excel Desktop acceptance gate.
