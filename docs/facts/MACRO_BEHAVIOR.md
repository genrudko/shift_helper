# Confirmed VBA behaviour

This document records behaviour extracted from the supplied VBA project. It is
not a design inferred from memory.

## Fast date/time input

The `ЖС` worksheet handler applies only to a single changed cell. Its first guard
returns when `Target.CountLarge > 1`; therefore the old implementation does not
support multi-cell paste.

Handled columns:

- dates: `B` and `I`;
- times: `C` and `J`.

Confirmed tokens:

### Date

- `.` — previous date above;
- `!` — current date;
- `+N` — previous date plus N days;
- compact numeric date formats;
- full date values accepted by Excel/VBA.

VBA uses `DateSerial`, which can normalize an impossible date into another
calendar date. The replacement parser intentionally rejects impossible input.
The product contract additionally requires one-digit day input such as `7`;
this is supported by the new parser even though the recovered VBA branch only
handled compact lengths 2, 4 and 6.

### Time

- `.` — previous time above;
- `!` — current time without seconds;
- `+N` — previous time plus N minutes;
- 1/2 digits — hour;
- 3 digits — `HMM`;
- 4 digits — `HHMM`;
- colon-separated time.

The VBA checks hours up to 23 and minutes up to 59. The replacement also reports
midnight rollover explicitly for `+N`.

## Report event selection

For a requested report date:

```text
startInclusive = previous day 07:00
endExclusive   = report day 07:00
```

Selection uses the event start from `B + C` and the exact boundary condition
`start <= event < end`.

Legacy skip order:

1. skip when `F` is empty or `-`;
2. skip when `E` is `-`;
3. skip when `E` contains `остановлена`, `для работ`, `работы по`, `работ по`
   or `переключений`;
4. explicitly retain `ошибка в работе`;
5. otherwise skip when `E` contains `в работе`.

The old macro searched only a 150-row window around an anchor. That is an
implementation limitation, not a business rule, and is not reproduced.

## Legacy report transfer

The old macro copied derived `N:R`. The factual direct mapping is:

| New report field | Journal source |
|---|---|
| dispatch name | `D` normalized as `ВЭУ №N` |
| outage date/time | `B + C` |
| reason | `F` |
| protection operation/description | `E` |
| return date/time | `I + J` |

## Generation import macro

Recovered legacy contract:

- expected attachment name:
  `Генерация КВЭС за вчера_dd_mm_yyyy.xlsx`;
- Outlook display path:
  `НСС Кочубеевская ВЭС/Входящие`;
- sheet: `Сумма ВЭС`;
- imported values: `G26` and `Q26`;
- validation range: `Q2:Q25`, numeric values from 0 through 10,000;
- duplicate check was based only on one destination value and is insufficient
  for the new import adapter.
