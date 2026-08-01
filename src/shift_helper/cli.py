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


def _configure_console_stream(stream: object) -> None:
    """Use UTF-8 for Russian diagnostics in packaged Windows consoles."""

    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")


def _configure_console() -> None:
    _configure_console_stream(sys.stdout)
    _configure_console_stream(sys.stderr)


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
    journal_path = args.journal.resolve()
    template_path = args.template.resolve()
    output_path = args.output.resolve()
    if output_path == journal_path:
        print(
            "Путь результата совпадает с исходным журналом; операция запрещена.",
            file=sys.stderr,
        )
        return 2
    if output_path == template_path:
        print(
            "Путь результата совпадает с шаблоном рапорта; операция запрещена.",
            file=sys.stderr,
        )
        return 2

    source_before = file_sha256(journal_path)
    journal = read_event_journal(journal_path)
    selection = select_emergency_events(journal.events, args.report_date)
    diagnostics = args.diagnostics.resolve()
    diagnostics.mkdir(parents=True, exist_ok=True)
    write_event_selection(diagnostics / "event-selection.csv", selection)

    blocking_structure_errors = [
        issue
        for issue in journal.issues
        if issue.severity == "error" and (issue.row is None or issue.row == 1)
    ]
    output_name: str | None = None
    if not blocking_structure_errors:
        output = build_emergency_report(
            template_path=template_path,
            output_path=output_path,
            report_date=args.report_date,
            events=selection.selected_events,
        )
        output_name = output.name

    source_after = file_sha256(journal_path)
    if source_before != source_after:
        raise RuntimeError("Исходный журнал изменился во время read-only обработки.")

    write_validation(
        diagnostics / "validation.json",
        journal=journal,
        selection=selection,
        output_name=output_name,
    )
    if blocking_structure_errors:
        print(
            "Генерация остановлена: структура книги ЖС не соответствует контракту.",
            file=sys.stderr,
        )
        return 2
    print(f"Сформировано строк: {len(selection.selected_events)}")
    print(f"Результат: {output_path}")
    print(f"Диагностика: {diagnostics}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "build-emergency-report":
        return _build_emergency_report(args)
    parser.error("Неизвестная команда.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
