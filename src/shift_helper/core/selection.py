"""Selection rules for emergency outages in the morning report."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from .events import JournalEvent


@dataclass(frozen=True, slots=True)
class EventDecision:
    event: JournalEvent
    selected: bool
    code: str


@dataclass(slots=True)
class SelectionResult:
    report_date: date
    window_start: datetime
    window_end: datetime
    decisions: list[EventDecision] = field(default_factory=list)

    @property
    def selected_events(self) -> list[JournalEvent]:
        return [decision.event for decision in self.decisions if decision.selected]


def report_window(report_date: date) -> tuple[datetime, datetime]:
    end = datetime.combine(report_date, time(7, 0))
    return end - timedelta(days=1), end


def event_filter_code(description: str, reason: str) -> str | None:
    """Return the legacy factual skip reason, preserving VBA rule order."""

    e_text = description.strip().casefold()
    f_text = reason.strip().casefold()
    if not f_text or f_text == "-":
        return "skip.empty_reason"
    if e_text == "-":
        return "skip.placeholder_description"
    repair_markers = ("остановлена", "для работ", "работы по", "работ по", "переключений")
    if any(marker in e_text for marker in repair_markers):
        return "skip.maintenance_context"
    if "ошибка в работе" in e_text:
        return None
    if "в работе" in e_text:
        return "skip.in_operation_context"
    return None


def select_emergency_events(events: list[JournalEvent], report_date: date) -> SelectionResult:
    start, end = report_window(report_date)
    result = SelectionResult(report_date=report_date, window_start=start, window_end=end)
    for event in sorted(events, key=lambda item: (item.started_at, item.source_row)):
        if event.started_at < start:
            result.decisions.append(EventDecision(event, False, "skip.before_window"))
            continue
        if event.started_at >= end:
            result.decisions.append(EventDecision(event, False, "skip.after_window"))
            continue
        filter_code = event_filter_code(event.description, event.reason)
        if filter_code is not None:
            result.decisions.append(EventDecision(event, False, filter_code))
            continue
        result.decisions.append(EventDecision(event, True, "selected"))
    return result
