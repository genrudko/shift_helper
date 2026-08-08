# Shift-Helper for Microsoft Excel — installation and acceptance

## Target

- Windows x64;
- desktop Microsoft Excel from Microsoft 365 / a current perpetual release;
- classic Outlook Desktop is optional and is used only for generation import.

The shared journal remains an ordinary macro-free `.xlsx`. Do not convert it to `.xlsm`.

## Install or replace the add-in

1. Close Excel completely before replacing an existing acceptance build.
2. Keep `Shift-Helper-Excel.xlam` in a stable local folder, for example `Documents\Shift-Helper`.
3. Replace the previous acceptance XLAM with the new file.
4. If Windows shows **Unblock / Разблокировать** in the file properties, apply it.
5. In Excel open **File → Options → Add-ins**.
6. At the bottom select **Manage: Excel Add-ins → Go… → Browse…**.
7. Choose `Shift-Helper-Excel.xlam` and enable it.
8. Reopen the journal if it was already open.
9. Confirm that the **Shift-Helper** Ribbon tab is visible and its commands have icons.

If your organization blocks unsigned VBA add-ins, use the Office Trust Center policy approved by your administrator. Do not weaken system-wide macro security just for testing.

## Live runtime repair checkpoint

The acceptance build after the first real Excel parity test contains a dedicated repair for the previously observed long wait followed by **Type mismatch** in both **Подготовить полный контур** and **Импортировать генерацию**.

The repaired path now:

- switches Excel calculation to manual while report formulas are being reapplied, then restores the user's previous calculation mode;
- disables application events and screen repaint only for the bounded operation and always restores them;
- reads the journal event block `B:J` into one in-memory VBA array instead of thousands of per-cell Excel COM calls;
- safely ignores empty/error date, time and text cells instead of converting Excel error variants through `CStr`, `CDbl` or `IsDate` unsafely;
- calculates only the seven report input sheets rather than issuing `Workbook.Calculate` for the complete operational workbook;
- uses a separate hardened generation-import runtime with safe metadata conversion and a received-time-bounded Outlook search;
- preserves the original error number before cleanup;
- reports the exact failing stage in any remaining runtime error.

For this build, test these two commands first:

1. **Подготовить полный контур рапорта**. On an already prepared acceptance journal it should finish promptly and must not reconstruct the embedded template unnecessarily.
2. **Импортировать генерацию**. Outlook search is sorted by received time and stops when the configured search horizon is crossed; if no matching attachment exists and manual fallback is enabled, the file picker should appear.

If either operation still fails, record the complete Shift-Helper dialog. It now contains an error number and `Stage [...]` marker, which identifies the exact runtime section.

## Runtime UI contract

- **Календарь** opens a compact native Windows month-calendar above Excel. It must show an actual month grid with normal month navigation and must not create a temporary Excel workbook.
- **Настройки Outlook** is an in-Ribbon settings menu. Editing one value may use a standard Excel input dialog, but it must never create a temporary Excel workbook or window.
- **Автовысота строк** applies Excel AutoFit to the selected rows from their cell contents. It must not ask the operator to enter a numeric row height.
- every top-level Shift-Helper Ribbon command has an icon; the add-in obtains Office-native images at runtime and has a safe built-in fallback.
- **Подготовить полный контур рапорта** creates missing Shift-Helper report/input sheets inside the current journal when required.
- journal commands operate only in the active Shift-Helper journal context.
- automatic quick input is limited to `ЖС` columns B/C/I/J and does not insert VBA into the journal.
- a separate workbook is expected only for a genuine user document, such as the generated final morning report, or a generation source opened read-only during import.

## Full acceptance sequence

Prefer the accepted `Shift-Helper-Journal-ACCEPTANCE-006.xlsx` baseline for controlled acceptance, then repeat the relevant checks on the real operational journal.

1. Open the journal and leave its original workbook format unchanged.
2. Run **Подготовить полный контур рапорта** and verify that it completes without a long hang or Type mismatch.
3. Run **Импортировать генерацию** and verify Outlook search/manual fallback behavior.
4. Verify that the **Shift-Helper** Ribbon shows icons for all commands.
5. Press **Календарь** and verify a compact calendar window with a month grid, normal month navigation and no second workbook.
6. Open **Настройки Outlook**. Verify settings stay in the Ribbon, persist after editing, and no Outlook workbook appears.
7. Select journal rows with short and wrapped/multiline text and run **Автовысота строк**. Verify native AutoFit and no numeric prompt.
8. Verify automatic quick input on `ЖС` B/C/I/J, including `.`, `!`, `+N`, compact dates/times and midnight rollover.
9. Verify `Ввод - Основные!C6 = C10 / 24000` and the accepted C15 remaining-power calculation.
10. Verify all 84 WTG rows on `Ввод - Состояние ВЭУ`, visible `Статус ВЭУ`, `P расп. = MAX(P уставка - P ремонт, 0)` and GTP sums.
11. Run the WTG rotor/power-limit action and verify only corresponding WTG state rows change, including the accepted discrete repair-power mapping.
12. Check `Ввод - Аварийные отключения` for the selected 07:00→07:00 window.
13. Generate the full morning report. No report-template picker must appear. The output workbook must contain exactly the approved seven sheets.
14. With a non-zero `Подготовка рапорта!B6`, compare source and output timestamps; the source journal must remain unchanged.
15. Exercise A:R time sorting, merge-and-copy, whitespace cleanup, date/time insertion and maintenance text on real rows.
16. Create an Outlook draft and verify Shift-Helper displays it rather than sending automatically.
17. On `График осмотров КТП`, run **Текущий день / текущая смена** and verify navigation to the current schedule row.
18. Save and close the shared journal. Confirm the `.xlsx` still contains no VBA/ActiveX/customUI parts.
19. Open the same saved `.xlsx` in LibreOffice Calc and verify structure, formulas, formats and the existing Calc extension workflow.

A green GitHub build proves package structure and cross-platform contracts. It does **not** replace the live Excel Desktop acceptance gate.
