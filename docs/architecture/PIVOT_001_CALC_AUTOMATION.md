# PIVOT-001 — Calc-based automation foundation

Status: **IMPLEMENTED IN DRAFT**  
Date: 2026-08-01  
Base: `main` / `fafd3a520ddf7109d502510040ee0941cf1bb041`

## Decision

Shift-Helper stops developing a separate spreadsheet UI.

```text
LibreOffice Calc workbook
        │ read-only input in PIVOT-001
        ▼
Python Shift-Helper Core
        │ validation + normalization + selection
        ▼
copy of approved .xlsx report template
        └─ event-selection.csv + validation.json
```

Calc is the operator-facing table. Python is the automation core. A generated
`.xlsx` report is the deliverable for manual upload to the closed site.

Not part of PIVOT-001: UNO, GUI, Evolution UI automation, IMAP, SQLite, the work
journal, the full report, loss pricing, and mutation of the source workbook.

## PR #6 salvage matrix

### KEEP

- privacy exclusions for real workbooks and operational data;
- Windows/Linux quality gates and portable packaging discipline;
- atomic publication through a verified pending file;
- SHA-256 and machine-readable diagnostics;
- explicit validation failures;
- bulk-operation regression scenarios;
- synthetic and sanitised fixtures only.

`KEEP` means preserving the engineering principle, not copying a component that
is coupled to SQLite or Univer.

### REWRITE

| PR #6 component | Workbook-oriented replacement |
|---|---|
| SQLite `.xlsx` mirror | read-only journal parser and report-template writer |
| browser batch API | pure Python bulk date/time normalizer |
| database backup manifest | source/output workbook integrity diagnostics |
| Flask launcher | command-line core; later UNO adapter |
| Chromium acceptance | workbook integration tests |
| ORM event model | immutable normalized journal row |
| UI field map | versioned `ЖС → report` contract |

### DROP

- `frontend/**`, Univer, Vite and Node runtime;
- browser spreadsheet, ribbon, zoom and formatting behaviour;
- UI smoke workflow;
- Flask editing API and LAN editing;
- SQLite as source of truth;
- audit/history/undo/presentation database layers;
- web templates for direct journal editing.

## Runtime boundary

The pre-pivot Flask/SQLite modules remain temporarily present only to keep the
old regression suite executable while the repository is being migrated. They
are frozen and are not called by the active `shift-helper` entry point.

The active executable exposes the workbook command-line core. Removal of frozen
legacy modules is a later, separately reviewed cleanup and must not be mixed
with the first factual parser slice.

## PIVOT-001 guarantees

- source journal opened read-only at the package-part level;
- source SHA-256 checked before and after processing;
- report template never overwritten;
- only `Аварийные отключения ЛЭП` is cleared and populated;
- output is reopened and checked before atomic publication;
- bad source rows remain visible in `validation.json`;
- event selection is traceable row-by-row in `event-selection.csv`.
