# Generation import contract

Status: documented for a later slice; no mail adapter is implemented in
PIVOT-001.

## Preferred adapter

Direct IMAP access to the same mailbox used by Evolution:

1. search by sender, subject and operational date;
2. choose the latest matching `.xlsx` attachment;
3. download to a controlled import area;
4. verify filename, sheet and cell/range contract;
5. calculate a content SHA-256;
6. reject or explicitly report duplicate import;
7. import values independently of the mail transport.

Evolution UI must not be automated.

## Fallback adapter

The operator saves the attachment to a watched folder. The same workbook parser
processes it; only the acquisition adapter differs.

## Recovered workbook contract

Legacy source:

- filename pattern: `Генерация КВЭС за вчера_dd_mm_yyyy.xlsx`;
- sheet: `Сумма ВЭС`;
- values: `G26` and `Q26`;
- control range: `Q2:Q25` numeric and between 0 and 10,000.

Before implementation this contract must be checked against a current real
attachment. Duplicate protection must use at least attachment SHA-256, source
identity and operational date; comparing a single imported cell is not enough.
