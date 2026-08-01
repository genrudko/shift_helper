# New report field map

## PIVOT-001 output

Only sheet `Аварийные отключения ЛЭП` is in the first implementation slice.
The source journal is never modified.

| Target | Meaning | Source |
|---|---|---|
| `B4:B…` | dispatch name | normalized journal `D` |
| `C4:C…` | outage date/time | numeric `B + C` |
| `D4:D…` | reason | `F` |
| `E4:E…` | protection operation/description | `E` |
| `F4:F…` | return-to-service date/time | numeric `I + J`, optional |

Target headers in `B3:F3` are verified before writing. Existing data rows are
cleared only in this sheet. Other worksheets are retained from the template.

## Selection window

For report date `R`:

- start: `R - 1 day` at 07:00, inclusive;
- end: `R` at 07:00, exclusive.

Every parsed event receives a traceable selection decision in
`event-selection.csv`.

## Validation policy

- structural header errors block report creation;
- the known incorrect `D1 = 40` is surfaced as a warning because the actual
  column semantics have been independently confirmed;
- rows with invalid numeric dates/times, missing asset number, partial return
  timestamp or return before outage are excluded and reported;
- an empty return timestamp is allowed for an outage still open at report time;
- no source text is silently rewritten.
