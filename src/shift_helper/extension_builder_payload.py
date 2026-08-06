"""Register preserved runtimes and reconstruct the embedded Calc template."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from shift_helper import extension_builder

_TEMPLATE_TARGET = "Templates/report_template.xlsx"
_TEMPLATE_SHA256 = "cde2d2fb042f27dc514f71ac991676e423dd6a68667fbb6d3f928ab610acbb32"
_TEMPLATE_GLOB = (
    "packaging/libreoffice_extension/Templates/report_template.b64.*"
)
_STATIC_PAYLOADS = {
    "Scripts/python/shift_helper_tools_payload.py": (
        "packaging/libreoffice_extension/Scripts/python/"
        "shift_helper_tools_payload.py"
    ),
}
_SOURCE_PAYLOADS = {
    "Scripts/python/pythonpath/shift_helper/core/exact_report_contract.py": (
        "src/shift_helper/core/exact_report_contract.py"
    ),
    "Scripts/python/pythonpath/shift_helper/core/exact_tools_contract.py": (
        "src/shift_helper/core/exact_tools_contract.py"
    ),
}
_ORIGINAL_PAYLOAD = extension_builder._payload


def _template_bytes(repo_root: Path) -> bytes:
    chunks = sorted(repo_root.glob(_TEMPLATE_GLOB))
    if not chunks:
        raise extension_builder.ExtensionBuildError(
            "Не найдены части встроенного шаблона рапорта."
        )
    encoded = "".join(path.read_text(encoding="ascii") for path in chunks)
    try:
        content = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise extension_builder.ExtensionBuildError(
            "Встроенный шаблон рапорта повреждён."
        ) from exc
    digest = hashlib.sha256(content).hexdigest()
    if digest != _TEMPLATE_SHA256:
        raise extension_builder.ExtensionBuildError(
            "Контрольная сумма встроенного шаблона рапорта не совпадает."
        )
    return content


def _payload_with_template(repo_root: Path) -> dict[str, bytes]:
    files = _ORIGINAL_PAYLOAD(repo_root)
    files[_TEMPLATE_TARGET] = _template_bytes(repo_root)
    return files


def install_payload_copy() -> None:
    """Register every exact-form OXT payload before build and verification."""

    extension_builder._STATIC_FILES.update(_STATIC_PAYLOADS)
    extension_builder._SOURCE_FILES.update(_SOURCE_PAYLOADS)
    if not getattr(extension_builder, "_EXACT_TEMPLATE_PAYLOAD_INSTALLED", False):
        extension_builder._payload = _payload_with_template
        extension_builder._EXACT_TEMPLATE_PAYLOAD_INSTALLED = True
