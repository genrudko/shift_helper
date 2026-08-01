"""Minimal streaming OOXML reader for large operational workbooks."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"m": MAIN_NS, "r": REL_NS, "p": PKG_REL_NS}
BUILTIN_DATE_FORMATS = (
    set(range(14, 23))
    | set(range(27, 37))
    | set(range(45, 48))
    | set(range(50, 59))
)
_CELL_REF_RE = re.compile(r"^(?P<column>[A-Z]+)(?P<row>\d+)$")
_DATE_FORMAT_RE = re.compile(r"(?i)(?:^|[^a-z])(?:d+|m+|y+|h+|s+|\[h\])(?:[^a-z]|$)")


class OOXMLReadError(ValueError):
    """Raised when an OOXML workbook cannot be read safely."""


def _resolve_part(base: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return str(PurePosixPath(base).parent.joinpath(target))


def _column(reference: str) -> str:
    match = _CELL_REF_RE.fullmatch(reference)
    if match is None:
        raise OOXMLReadError(f"Некорректная ссылка на ячейку: {reference!r}.")
    return match.group("column")


def _excel_datetime(serial: float, *, date1904: bool) -> datetime:
    base = datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)
    return base + timedelta(days=serial)


class StreamingWorkbook:
    """Read only required cells from an OOXML workbook without loading all sheets."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.archive = ZipFile(self.path)
        self.shared_strings = self._read_shared_strings()
        self.date1904, self.sheet_parts = self._read_workbook()
        self.style_formats = self._read_styles()

    def close(self) -> None:
        self.archive.close()

    def __enter__(self) -> "StreamingWorkbook":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _read_shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self.archive.namelist():
            return []
        root = ET.fromstring(self.archive.read("xl/sharedStrings.xml"))
        return [
            "".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t"))
            for item in root.findall("m:si", NS)
        ]

    def _read_workbook(self) -> tuple[bool, dict[str, str]]:
        workbook_part = "xl/workbook.xml"
        root = ET.fromstring(self.archive.read(workbook_part))
        properties = root.find("m:workbookPr", NS)
        date1904 = properties is not None and properties.get("date1904") in {"1", "true"}
        relationships = ET.fromstring(self.archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target") for rel in relationships}
        parts: dict[str, str] = {}
        sheets = root.find("m:sheets", NS)
        if sheets is None:
            return date1904, parts
        for sheet in sheets:
            relationship_id = sheet.get(f"{{{REL_NS}}}id")
            target = targets.get(relationship_id)
            if target:
                parts[str(sheet.get("name"))] = _resolve_part(workbook_part, target)
        return date1904, parts

    def _read_styles(self) -> list[tuple[int, str]]:
        if "xl/styles.xml" not in self.archive.namelist():
            return []
        root = ET.fromstring(self.archive.read("xl/styles.xml"))
        custom: dict[int, str] = {}
        num_formats = root.find("m:numFmts", NS)
        if num_formats is not None:
            for item in num_formats:
                custom[int(item.get("numFmtId", "0"))] = item.get("formatCode", "")
        formats: list[tuple[int, str]] = []
        cell_formats = root.find("m:cellXfs", NS)
        if cell_formats is not None:
            for item in cell_formats:
                format_id = int(item.get("numFmtId", "0"))
                formats.append((format_id, custom.get(format_id, "")))
        return formats

    def _cell_value(self, cell: ET.Element, *, expected_kind: str | None) -> object:
        cell_type = cell.get("t")
        if cell_type == "inlineStr":
            inline = cell.find("m:is", NS)
            if inline is None:
                return ""
            return "".join(node.text or "" for node in inline.iter(f"{{{MAIN_NS}}}t"))
        value_node = cell.find("m:v", NS)
        if value_node is None:
            return None
        raw = value_node.text or ""
        if cell_type == "s":
            try:
                return self.shared_strings[int(raw)]
            except (ValueError, IndexError) as exc:
                raise OOXMLReadError("Некорректная ссылка sharedStrings.") from exc
        if cell_type in {"str", "e"}:
            return raw
        if cell_type == "b":
            return raw == "1"
        try:
            number = float(raw)
        except ValueError:
            return raw

        if expected_kind == "date":
            return _excel_datetime(number, date1904=self.date1904).date()
        if expected_kind == "time":
            total_seconds = round((number % 1) * 24 * 60 * 60)
            total_seconds %= 24 * 60 * 60
            return time(total_seconds // 3600, (total_seconds % 3600) // 60, total_seconds % 60)

        style_index = int(cell.get("s", "0"))
        if style_index < len(self.style_formats):
            format_id, format_code = self.style_formats[style_index]
            is_date_format = format_id in BUILTIN_DATE_FORMATS or _DATE_FORMAT_RE.search(
                format_code.replace("\\", "")
            )
            if is_date_format:
                converted = _excel_datetime(number, date1904=self.date1904)
                if abs(number) < 1:
                    return converted.time()
                return converted
        return int(number) if number.is_integer() else number

    def rows(
        self,
        sheet_name: str,
        *,
        columns: set[str],
        expected_kinds: dict[str, str] | None = None,
    ):
        part = self.sheet_parts.get(sheet_name)
        if part is None:
            raise OOXMLReadError(f"В книге отсутствует лист {sheet_name!r}.")
        expected_kinds = expected_kinds or {}
        with self.archive.open(part) as stream:
            for _event, element in ET.iterparse(stream, events=("end",)):
                if element.tag != f"{{{MAIN_NS}}}row":
                    continue
                row_number = int(element.get("r", "0"))
                values: dict[str, object] = {}
                for cell in element.findall("m:c", NS):
                    reference = cell.get("r")
                    if not reference:
                        continue
                    column = _column(reference)
                    if column in columns:
                        values[column] = self._cell_value(
                            cell,
                            expected_kind=expected_kinds.get(column),
                        )
                yield row_number, values
                element.clear()
