from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from shift_helper.core.workbook_contract import APPROVED_REPORT_TEMPLATE_SHA256
from shift_helper.excel_builder import build_excel_addin, verify_excel_addin

ROOT = Path(__file__).resolve().parents[1]


def test_excel_addin_build_and_verify(tmp_path: Path) -> None:
    pytest.importorskip("pyopenvba")
    output = tmp_path / "Shift-Helper-Excel.xlam"
    build_excel_addin(ROOT, output)
    assert output.is_file()
    evidence = verify_excel_addin(ROOT, output)
    assert evidence["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert evidence["embedded_template_sha256"] == APPROVED_REPORT_TEMPLATE_SHA256

    with zipfile.ZipFile(output, "r") as archive:
        names = set(archive.namelist())
        assert "xl/vbaProject.bin" in names
        assert "customUI/customUI14.xml" in names
        assert "shift_helper_report_template.xlsx" in names
        assert (
            hashlib.sha256(archive.read("shift_helper_report_template.xlsx")).hexdigest()
            == APPROVED_REPORT_TEMPLATE_SHA256
        )
