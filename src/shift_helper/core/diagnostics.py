"""Deterministic CSV/JSON diagnostics for PIVOT-001."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .events import JournalReadResult
from .selection import SelectionResult


def write_event_selection(path: Path, selection: SelectionResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        writer.writerow(
            (
                "source_row",
                "started_at",
                "dispatch_name",
                "reason",
                "description",
                "ended_at",
                "selected",
                "decision",
            )
        )
        for decision in selection.decisions:
            event = decision.event
            writer.writerow(
                (
                    event.source_row,
                    event.started_at.isoformat(timespec="minutes"),
                    event.dispatch_name,
                    event.reason,
                    event.description,
                    event.ended_at.isoformat(timespec="minutes") if event.ended_at else "",
                    "yes" if decision.selected else "no",
                    decision.code,
                )
            )


def write_validation(
    path: Path,
    *,
    journal: JournalReadResult,
    selection: SelectionResult,
    output_name: str | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    severity_counts: dict[str, int] = {}
    for issue in journal.issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
    payload = {
        "schemaVersion": 1,
        "source": {
            "filename": journal.source_name,
            "sha256": journal.source_sha256,
            "sheet": journal.sheet_name,
        },
        "reportDate": selection.report_date.isoformat(),
        "window": {
            "startInclusive": selection.window_start.isoformat(timespec="minutes"),
            "endExclusive": selection.window_end.isoformat(timespec="minutes"),
        },
        "summary": {
            "validEventCount": len(journal.events),
            "ignoredRowCount": len(set(journal.ignored_rows)),
            "selectedEventCount": len(selection.selected_events),
            "issuesBySeverity": severity_counts,
        },
        "outputFilename": output_name,
        "issues": [issue.as_dict() for issue in journal.issues],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
