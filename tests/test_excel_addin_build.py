from __future__ import annotations

import base64
import hashlib
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from shift_helper.excel_builder import (
    _template_payload_source,
    build_excel_addin,
    verify_excel_addin,
)
from shift_helper.extension_builder_payload import (
    _TEMPLATE_ENTRY_SHA256,
    _template_bytes,
    _validate_template,
)

ROOT = Path(__file__).resolve().parents[1]


def test_generated_vba_template_payload_round_trips_exact_template() -> None:
    expected = _template_bytes(ROOT)
    source = _template_payload_source(expected)
    chunks = []
    for line in source.splitlines():
        if line.strip().startswith("payload =") and '"' in line:
            chunks.append(line.rsplit('"', 2)[1])
    assert chunks
    assert base64.b64decode("".join(chunks)) == expected


def test_excel_addin_build_and_verify(tmp_path: Path) -> None:
    pytest.importorskip("pyopenvba")
    output = tmp_path / "Shift-Helper-Excel.xlam"
    build_excel_addin(ROOT, output)
    assert output.is_file()
    evidence = verify_excel_addin(ROOT, output)
    assert evidence["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert evidence["embedded_template_members"] == len(_TEMPLATE_ENTRY_SHA256)
    assert "CShiftHelperAppEvents" in evidence["modules"]
    assert "modShiftHelperTemplatePayload" in evidence["modules"]
    assert "modShiftHelperQuickInput" in evidence["modules"]
    assert "modShiftHelperTools" in evidence["modules"]

    with zipfile.ZipFile(output, "r") as archive:
        names = set(archive.namelist())
        assert "xl/vbaProject.bin" in names
        assert "customUI/customUI14.xml" in names
        assert "shift_helper_report_template.xlsx" in names
        embedded = archive.read("shift_helper_report_template.xlsx")
    _validate_template(embedded)
    with zipfile.ZipFile(BytesIO(embedded)) as template:
        for name, expected in _TEMPLATE_ENTRY_SHA256.items():
            assert hashlib.sha256(template.read(name)).hexdigest() == expected
