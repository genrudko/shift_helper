# Privacy boundary

The repository is public. Production inputs contain personal, contact and
operational information.

## Forbidden in GitHub

- source `.xls`, `.xlsx`, `.xlsm`, `.xlsb` workbooks;
- mail messages and attachments;
- names, addresses, phone numbers and account identifiers;
- real operational event rows;
- private databases, logs, imports, exports and backups;
- screenshots or diagnostics containing production data;
- extracted VBA source when it contains sensitive workbook-specific data.

## Allowed

- SHA-256 of private inputs;
- factual workbook structure and cell contracts;
- documented business rules;
- minimal synthetic fixtures;
- anonymised equipment examples where identity is not sensitive;
- generated diagnostics from synthetic tests.

## Runtime safeguards

- source workbook is read-only in PIVOT-001;
- source SHA-256 is checked before and after processing;
- output is a new file and cannot equal the template path;
- a pending output is verified before atomic publication;
- diagnostic files are written beside the operator-selected output, not into
  the repository;
- CI tests use generated workbooks only.
