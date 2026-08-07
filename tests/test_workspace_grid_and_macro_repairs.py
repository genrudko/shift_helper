from __future__ import annotations

import ast
import base64
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _literal_payload(path: Path, variable: str = "_PAYLOAD") -> bytes:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == variable
            for target in node.targets
        ):
            payload = ast.literal_eval(node.value)
            assert isinstance(payload, bytes)
            return payload
    raise AssertionError(f"{variable} is missing from {path}")


def _decode_payload(path: Path, variable: str, *, base85: bool) -> str:
    payload = _literal_payload(path, variable)
    compressed = base64.b85decode(payload) if base85 else base64.b64decode(payload)
    decoded = zlib.decompress(compressed).decode("utf-8")
    compile(decoded, f"decoded:{path.name}", "exec")
    return decoded


def _decode_operator_payload() -> str:
    path = (
        ROOT
        / "packaging/libreoffice_extension/Scripts/python/"
        "shift_helper_tools_payload.py"
    )
    payload = _literal_payload(path)
    repaired = payload[:7392] + b")" + payload[7392:]
    decoded = zlib.decompress(base64.b85decode(repaired)).decode("utf-8")
    compile(decoded, "decoded:shift_helper_tools_payload.py", "exec")
    return decoded


def test_operator_runtime_contains_nonblocking_clipboard_and_stable_sort() -> None:
    bootstrap = _decode_payload(
        ROOT
        / "packaging/libreoffice_extension/Scripts/python/shift_helper_tools.py",
        "_PAYLOAD",
        base85=True,
    )
    assert "payload[:7392]" in bootstrap
    assert "payload[7392:]" in bootstrap
    assert 'b")"' in bootstrap
    source = _decode_operator_payload()
    for marker in (
        "Set-Clipboard -Value ([Console]::In.ReadToEnd())",
        "sheet.copyRange(destination, source_row)",
        "__SH_SORT_TEMP",
        "controller.select(selected)",
        "show_report_date_calendar",
    ):
        assert marker in source
    assert "target.createSortDescriptor()" not in source
    assert "clipboard.setContents(_CLIPBOARD_TRANSFERABLE, None)" not in source


def test_exact_forms_replace_legacy_compact_grid_repair() -> None:
    controls = (
        ROOT / "packaging/libreoffice_extension/shift_helper_controls.py"
    ).read_text(encoding="utf-8")
    migration = (
        ROOT / "src/shift_helper/core/exact_migration_contract.py"
    ).read_text(encoding="utf-8")
    assert "install_calc_workspace_repairs" not in controls
    assert "install_exact_migration_contract" in controls
    assert "_copy_row_style" in migration
    assert "_restore_works" in migration


def test_uno_component_routes_report_date_calendar() -> None:
    source = (
        ROOT / "packaging/libreoffice_extension/shift_helper_controls.py"
    ).read_text(encoding="utf-8")
    assert (
        '"calendarprep": ("report", "show_report_date_calendar")'
        in source
    )
    assert (
        '"generationsettings": ("report", "show_generation_import_settings")'
        in source
    )
