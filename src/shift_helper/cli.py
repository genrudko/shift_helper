"""Command-line entry point for the Calc-based Shift-Helper automation core."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .core.diagnostics import write_event_selection, write_validation
from .core.journal_reader import file_sha256, read_event_journal
from .core.report_writer import build_emergency_report
from .core.selection import select_emergency_events


def _report_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Используйте дату в формате YYYY-MM-DD.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shift-helper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser(
        "build-emergency-report",
        help="Заполнить только лист аварийных отключений в копии нового шаблона.",
    )
    build.add_argument("--journal", required=True, type=Path)
    build.add_argument("--template", required=True, type=Path)
    build.add_argument("--report-date", required=True, type=_report_date)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--diagnostics", required=True, type=Path)
    return parser


def _build_emergency_report(args: argparse.Namespace) -> int:
    source_before = file_sha256(args.journal)
    journal = read_event_journal(args.journal)
    selection = select_emergency_events(journal.events, args.report_date)
    diagnostics = args.diagnostics.resolve()
    diagnostics.mkdir(parents=True, exist_ok=True)
    write_event_selection(diagnostics / "event-selection.csv", selection)

    blocking_header_errors = [
        issue
        for issue in journal.issues
        if issue.severity == "error" and issue.row == 1
    ]
    output_name: str | None = None
    if not blocking_header_errors:
        output = build_emergency_report(
            template_path=args.template,
            output_path=args.output,
            report_date=args.report_date,
            events=selection.selected_events,
        )
        output_name = output.name

    source_after = file_sha256(args.journal)
    if source_before != source_after:
        raise RuntimeError("Исходный журнал изменился во время read-only обработки.")

    write_validation(
        diagnostics / "validation.json",
        journal=journal,
        selection=selection,
        output_name=output_name,
    )
    if blocking_header_errors:
        print(
            "Генерация остановлена: структура листа ЖС не соответствует контракту.",
            file=sys.stderr,
        )
        return 2
    print(f"Сформировано строк: {len(selection.selected_events)}")
    print(f"Результат: {args.output.resolve()}")
    print(f"Диагностика: {diagnostics}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "build-emergency-report":
        return _build_emergency_report(args)
    parser.error("Неизвестная команда.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
