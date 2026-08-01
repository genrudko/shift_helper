# Workbook facts

All hashes are SHA-256. Source files are private inputs and are not stored in
GitHub.

## Source inventory

| Source | SHA-256 | Fact |
|---|---|---|
| `Журнал событий актуальный 2026!.zip` | `c0cb93ce48ae93f1f9daf4ed4103f45a2fff75894aa959ac080427ad166a1ff4` | archive supplied for preflight |
| inner `Журнал событий актуальный 2026!.xlsx` | `a7ffcf84c1676ccac1bea89d95d32b08f5b12d6ff3aa6bf8f9a16daf4289c151` | current macro-free workbook |
| `Журнал событий актуальный 2026.xlsm` | `2a288127aa42b2307016c5cf80177ca0b46be4f0758708fc1422def5089e9c21` | same journal data plus VBA project |
| `Макросы.zip` | `8846499bf0d16c01a3f23b3475e26cf6bf55fc097358f0304c15688a5c27641b` | exported VBA modules |
| old report | `c7f860ecf71ec1131b1e70589778919e058967967026397e8867a0832dbc0975` | previous 07:00 form |
| new report | `cde2d2fb042f27dc514f71ac991676e423dd6a68667fbb6d3f928ab610acbb32` | approved target workbook supplied for analysis |

The `.xlsx` from the ZIP and the `.xlsm` contain identical values in source
columns `B,C,D,E,F,I,J` over all physical rows inspected.

## Journal workbook

Required sheets confirmed:

- `ЖС`;
- `Код ошибки`;
- `Замена ПН`;
- `Рассылка`;
- `Рапорт утро`;
- `Нагрузка Т`;
- `График осмотров КТП`;
- hidden `Day` and `WEC`.

`Перечень работ` is present but is not the current source of planned work.

### `ЖС`

- 5,877 physical worksheet rows;
- current operational chronology ends at row 3,794 on 2026-07-26;
- `D1` is actually `40`; the required label is `№ ВЭУ`;
- row 2 is dated 2026-02-20 while normal chronology starts on row 3 at
  2026-01-01, confirming the accidental leading outlier;
- columns `N:R` are derived helpers, not primary data:
  - `N = "ВЭУ №" & D`;
  - `O = B + C`;
  - `P = F`;
  - `Q = E`;
  - `R = I + J`.

PIVOT-001 reads only primary columns `B,C,D,E,F,I,J` and does not write the
journal.

## New report target

Sheet: `Аварийные отключения ЛЭП`.

- title: merged range `B1:F1`;
- headers: `B3:F3`;
- first data row: 4.

Exact field order:

1. dispatch name;
2. outage date/time;
3. reason;
4. protection operation/description;
5. return-to-service date/time.

## Factual dry run

Using the supplied journal:

- report date 2026-07-27 selected two valid rows;
- report date 2026-07-30 selected zero rows because the source chronology ends
  on 2026-07-26;
- source SHA-256 was unchanged before and after both runs;
- 3,697 rows were normalized as valid events;
- 96 rows were ignored due to explicit validation or the known outlier;
- all historical warnings and errors were retained in `validation.json` rather
  than silently corrected.
