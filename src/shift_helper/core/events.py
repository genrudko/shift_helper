"""Typed records and validation diagnostics for workbook processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    severity: str
    message: str
    row: int | None = None
    column: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.row is not None:
            payload["row"] = self.row
        if self.column is not None:
            payload["column"] = self.column
        return payload


@dataclass(frozen=True, slots=True)
class JournalEvent:
    source_row: int
    started_at: datetime
    asset_number: int
    description: str
    reason: str
    ended_at: datetime | None

    @property
    def dispatch_name(self) -> str:
        return f"ВЭУ №{self.asset_number}"


@dataclass(slots=True)
class JournalReadResult:
    events: list[JournalEvent] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)
    ignored_rows: list[int] = field(default_factory=list)
    source_sha256: str = ""
    source_name: str = ""
    sheet_name: str = "ЖС"
