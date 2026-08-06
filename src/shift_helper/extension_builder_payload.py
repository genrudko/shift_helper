"""Register preserved runtimes and embedded Calc workbook templates."""

from __future__ import annotations

from shift_helper import extension_builder

_STATIC_PAYLOADS = {
    "Scripts/python/shift_helper_tools_payload.py": (
        "packaging/libreoffice_extension/Scripts/python/"
        "shift_helper_tools_payload.py"
    ),
    "Templates/report_template.xlsx": (
        "packaging/libreoffice_extension/Templates/report_template.xlsx"
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


def install_payload_copy() -> None:
    """Register every non-generated OXT payload before build and verification."""

    extension_builder._STATIC_FILES.update(_STATIC_PAYLOADS)
    extension_builder._SOURCE_FILES.update(_SOURCE_PAYLOADS)
