"""Package the preserved operator-runtime payload beside its safe bootstrap."""

from __future__ import annotations

from shift_helper import extension_builder

_PAYLOAD_TARGET = "Scripts/python/shift_helper_tools_payload.py"
_PAYLOAD_SOURCE = (
    "packaging/libreoffice_extension/Scripts/python/"
    "shift_helper_tools_payload.py"
)


def install_payload_copy() -> None:
    """Register the payload copy before building the Calc OXT."""

    extension_builder._STATIC_FILES[_PAYLOAD_TARGET] = _PAYLOAD_SOURCE
