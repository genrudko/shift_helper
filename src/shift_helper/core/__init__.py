"""Workbook-oriented Shift-Helper core."""

from .journal_reader import JournalReadResult, read_event_journal
from .selection import SelectionResult, select_emergency_events

__all__ = [
    "JournalReadResult",
    "SelectionResult",
    "read_event_journal",
    "select_emergency_events",
]
