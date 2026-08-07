"""Build and verify the native Microsoft Excel add-in."""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from shift_helper.core.workbook_contract import APPROVED_REPORT_TEMPLATE_SHA256
from shift_helper.extension_builder_payload import _template_bytes

_CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_RIBBON_REL = "http://schemas.microsoft.com/office/2006/relationships/ui/extensibility"
_TEMPLATE_REL = "https://shift-helper.local/relationships/embedded-report-template"
_TEMPLATE_PART = "shift_helper_report_template.xlsx"
_TEMPLATE_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _utf16_hex(value: str) -> str:
    return "".join(f"{ord(char):04X}" for char in value)


def _contract_source() -> str:
    from shift_helper.core.workbook_contract import (
        INPUT_SHEETS,
        INSPECTION_SHEET,
        JOURNAL_SHEET,
        PREP_SHEET,
        REPORT_DATE_CELL,
        REPORT_OFFSET_CELL,
        REPORT_SHEETS,
        WTG_COUNT,
        WTG_STATUSES,
    )

    lines = [
        'Attribute VB_Name = "modShiftHelperContract"',
        "Option Explicit",
        "",
        f"Public Const SH_WTG_COUNT As Long = {WTG_COUNT}",
        f"Public Const SH_REPORT_SHEET_COUNT As Long = {len(REPORT_SHEETS)}",
        "",
        "Public Function SH_JournalSheetName() As String",
        f'    SH_JournalSheetName = SH_U("{_utf16_hex(JOURNAL_SHEET)}")',
        "End Function",
        "Public Function SH_PrepSheetName() As String",
        f'    SH_PrepSheetName = SH_U("{_utf16_hex(PREP_SHEET)}")',
        "End Function",
        "Public Function SH_InspectionSheetName() As String",
        f'    SH_InspectionSheetName = SH_U("{_utf16_hex(INSPECTION_SHEET)}")',
        "End Function",
        "Public Function SH_ReportDateCell() As String",
        f'    SH_ReportDateCell = "{REPORT_DATE_CELL}"',
        "End Function",
        "Public Function SH_ReportOffsetCell() As String",
        f'    SH_ReportOffsetCell = "{REPORT_OFFSET_CELL}"',
        "End Function",
        "Public Function SH_ReportSheetCount() As Long",
        f"    SH_ReportSheetCount = {len(REPORT_SHEETS)}",
        "End Function",
        "Public Function SH_ReportSheetName(ByVal index As Long) As String",
        "    Select Case index",
    ]
    for index, name in enumerate(REPORT_SHEETS, start=1):
        lines.append(f'        Case {index}: SH_ReportSheetName = SH_U("{_utf16_hex(name)}")')
    lines.extend(["        Case Else: Err.Raise 5", "    End Select", "End Function"])
    lines.extend(
        [
            "Public Function SH_InputSheetName(ByVal index As Long) As String",
            "    Select Case index",
        ]
    )
    for index, name in enumerate(INPUT_SHEETS, start=1):
        lines.append(f'        Case {index}: SH_InputSheetName = SH_U("{_utf16_hex(name)}")')
    lines.extend(["        Case Else: Err.Raise 5", "    End Select", "End Function"])
    lines.extend(
        [
            "Public Function SH_StatusText(ByVal index As Long) As String",
            "    Select Case index",
        ]
    )
    for index, name in enumerate(WTG_STATUSES, start=1):
        lines.append(f'        Case {index}: SH_StatusText = SH_U("{_utf16_hex(name)}")')
    lines.extend(["        Case Else: Err.Raise 5", "    End Select", "End Function", ""])
    result = "\r\n".join(lines)
    if not result.isascii():
        raise RuntimeError("Generated VBA contract must remain ASCII-safe.")
    return result


def _vba_sources(repo_root: Path) -> dict[str, str]:
    source_dir = repo_root / "packaging" / "excel_addin" / "vba"
    sources: dict[str, str] = {"modShiftHelperContract": _contract_source()}
    for path in sorted(source_dir.glob("*.bas")):
        text = path.read_text(encoding="ascii").replace("\r\n", "\n")
        text = text.replace("\r", "\n").replace("\n", "\r\n")
        match = re.search(r'^Attribute VB_Name = "([A-Za-z0-9_]+)"', text, re.MULTILINE)
        if match is None:
            raise RuntimeError(f"VBA module has no VB_Name attribute: {path}")
        sources[match.group(1)] = text
    return sources


def _new_relationship_id(root: ET.Element, preferred: str) -> str:
    existing = {node.attrib.get("Id", "") for node in root}
    candidate = preferred
    counter = 1
    while candidate in existing:
        candidate = f"{preferred}{counter}"
        counter += 1
    return candidate


def _add_relationship(data: bytes, rel_type: str, target: str, preferred_id: str) -> bytes:
    ET.register_namespace("", _REL_NS)
    root = ET.fromstring(data)
    for node in root.findall(f"{{{_REL_NS}}}Relationship"):
        if node.attrib.get("Type") == rel_type:
            node.set("Target", target)
            return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    ET.SubElement(
        root,
        f"{{{_REL_NS}}}Relationship",
        Id=_new_relationship_id(root, preferred_id),
        Type=rel_type,
        Target=target,
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _add_template_content_type(data: bytes) -> bytes:
    ET.register_namespace("", _CONTENT_TYPES_NS)
    root = ET.fromstring(data)
    for node in root.findall(f"{{{_CONTENT_TYPES_NS}}}Override"):
        if node.attrib.get("PartName") == f"/{_TEMPLATE_PART}":
            node.set("ContentType", _TEMPLATE_CONTENT_TYPE)
            return ET.tostring(root, encoding="utf-8", xml_declaration=True)
    ET.SubElement(
        root,
        f"{{{_CONTENT_TYPES_NS}}}Override",
        PartName=f"/{_TEMPLATE_PART}",
        ContentType=_TEMPLATE_CONTENT_TYPE,
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _rewrite_zip(path: Path, replacements: dict[str, bytes]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(
        temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as target:
        seen: set[str] = set()
        for info in source.infolist():
            payload = replacements.get(info.filename, source.read(info.filename))
            target.writestr(info, payload)
            seen.add(info.filename)
        for name in sorted(set(replacements) - seen):
            target.writestr(name, replacements[name])
    temp.replace(path)


def build_excel_addin(repo_root: Path, output: Path) -> Path:
    """Create a real XLAM with native VBA, Ribbon and embedded exact template."""

    try:
        from pyopenvba import ExcelFile, VBAModuleKind
    except ImportError as exc:  # pragma: no cover - dedicated build workflow
        raise RuntimeError("Install the 'excel' optional dependency first.") from exc

    repo_root = repo_root.resolve()
    output = output.resolve()
    template = _template_bytes(repo_root)
    if hashlib.sha256(template).hexdigest() != APPROVED_REPORT_TEMPLATE_SHA256:
        raise RuntimeError("Approved embedded report template hash drifted.")
    sources = _vba_sources(repo_root)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with ExcelFile.create_new(str(output)) as workbook:
        project = workbook.vba_project()
        existing = set(workbook.module_names())
        donor = "Module1" if "Module1" in existing else None
        for index, (name, source) in enumerate(sources.items()):
            if index == 0 and donor is not None:
                workbook.set_module(donor, source)
                project.rename_module(donor, name)
                existing.discard(donor)
                existing.add(name)
            elif name in existing:
                workbook.set_module(name, source)
            else:
                project.add_module(name, source, kind=VBAModuleKind.standard)
        workbook.save()

    with zipfile.ZipFile(output, "r") as archive:
        root_rels = archive.read("_rels/.rels")
        content_types = archive.read("[Content_Types].xml")
    replacements = {
        "_rels/.rels": _add_relationship(
            _add_relationship(
                root_rels,
                _RIBBON_REL,
                "customUI/customUI14.xml",
                "rIdShiftHelperRibbon",
            ),
            _TEMPLATE_REL,
            _TEMPLATE_PART,
            "rIdShiftHelperTemplate",
        ),
        "[Content_Types].xml": _add_template_content_type(content_types),
        "customUI/customUI14.xml": (
            repo_root / "packaging" / "excel_addin" / "customUI14.xml"
        ).read_bytes(),
        _TEMPLATE_PART: template,
    }
    _rewrite_zip(output, replacements)
    verify_excel_addin(repo_root, output)
    return output


def verify_excel_addin(repo_root: Path, path: Path) -> dict[str, object]:
    try:
        from pyopenvba import ExcelFile
    except ImportError as exc:  # pragma: no cover - dedicated build workflow
        raise RuntimeError("Install the 'excel' optional dependency first.") from exc

    sources = _vba_sources(repo_root)
    with zipfile.ZipFile(path, "r") as archive:
        names = set(archive.namelist())
        required = {
            "xl/vbaProject.bin",
            "customUI/customUI14.xml",
            _TEMPLATE_PART,
        }
        if not required <= names:
            raise RuntimeError(f"XLAM is missing required parts: {sorted(required - names)}")
        embedded = archive.read(_TEMPLATE_PART)
        if hashlib.sha256(embedded).hexdigest() != APPROVED_REPORT_TEMPLATE_SHA256:
            raise RuntimeError("Embedded report template payload drifted.")
        ribbon = archive.read("customUI/customUI14.xml").decode("utf-8")
        callbacks = set(re.findall(r'onAction="([A-Za-z0-9_]+)"', ribbon))
        implemented = "\n".join(sources.values())
        missing_callbacks = [
            callback
            for callback in sorted(callbacks)
            if re.search(rf"\bSub\s+{re.escape(callback)}\b", implemented, re.I) is None
        ]
        if missing_callbacks:
            raise RuntimeError(f"Ribbon callbacks are missing: {missing_callbacks}")

    with ExcelFile(str(path)) as workbook:
        module_names = set(workbook.module_names())
    missing_modules = set(sources) - module_names
    if missing_modules:
        raise RuntimeError(f"XLAM is missing VBA modules: {sorted(missing_modules)}")
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "modules": sorted(sources),
        "embedded_template_sha256": APPROVED_REPORT_TEMPLATE_SHA256,
    }
