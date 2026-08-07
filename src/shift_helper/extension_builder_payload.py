"""Register preserved runtimes and reconstruct the embedded Calc template."""

from __future__ import annotations

import base64
import hashlib
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path

from shift_helper import extension_builder

_TEMPLATE_TARGET = "Templates/report_template.xlsx"
_TEMPLATE_SHA256 = "cde2d2fb042f27dc514f71ac991676e423dd6a68667fbb6d3f928ab610acbb32"
_TEMPLATE_GLOB = (
    "packaging/libreoffice_extension/Templates/report_template.b64.*"
)
_TEMPLATE_SHEETS = (
    "Основные данные",
    "Аварийные отключения ЛЭП",
    "Команды по внешней инициативе",
    "Нарушения ОТиПБ + Экология",
    "Состояние ВЭУ",
    "Запланированные работы",
    "Дефекты оборудования",
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
    "Scripts/python/pythonpath/shift_helper/core/exact_storage_contract.py": (
        "src/shift_helper/core/exact_storage_contract.py"
    ),
    "Scripts/python/pythonpath/shift_helper/core/exact_migration_contract.py": (
        "src/shift_helper/core/exact_migration_contract.py"
    ),
    "Scripts/python/pythonpath/shift_helper/core/exact_tools_contract.py": (
        "src/shift_helper/core/exact_tools_contract.py"
    ),
    "Scripts/python/pythonpath/shift_helper/core/acceptance_repairs_006.py": (
        "src/shift_helper/core/acceptance_repairs_006.py"
    ),
}
_ORIGINAL_PAYLOAD = extension_builder._payload
_ORIGINAL_VERIFY = extension_builder.verify_calc_extension


def _template_sheet_names(content: bytes) -> tuple[str, ...]:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise extension_builder.ExtensionBuildError(
            "Встроенный шаблон рапорта не является корректной книгой XLSX."
        ) from exc
    namespace = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    }
    sheets = workbook.find("m:sheets", namespace)
    if sheets is None:
        raise extension_builder.ExtensionBuildError(
            "Во встроенном шаблоне отсутствует список листов."
        )
    return tuple(item.attrib["name"] for item in sheets)


def _validate_template(content: bytes) -> None:
    digest = hashlib.sha256(content).hexdigest()
    if digest != _TEMPLATE_SHA256:
        raise extension_builder.ExtensionBuildError(
            "Контрольная сумма встроенного шаблона рапорта не совпадает."
        )
    if _template_sheet_names(content) != _TEMPLATE_SHEETS:
        raise extension_builder.ExtensionBuildError(
            "Состав или порядок листов встроенного шаблона изменён."
        )


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
    _validate_template(content)
    return content


def _payload_with_template(repo_root: Path) -> dict[str, bytes]:
    files = _ORIGINAL_PAYLOAD(repo_root)
    files[_TEMPLATE_TARGET] = _template_bytes(repo_root)
    return files


def _verify_with_template(path: Path) -> tuple[str, ...]:
    names = _ORIGINAL_VERIFY(path)
    with zipfile.ZipFile(path) as archive:
        if _TEMPLATE_TARGET not in names:
            raise extension_builder.ExtensionBuildError(
                "В OXT отсутствует встроенный шаблон рапорта."
            )
        _validate_template(archive.read(_TEMPLATE_TARGET))
    return names


def install_payload_copy() -> None:
    """Register every exact-form OXT payload before build and verification."""

    extension_builder._STATIC_FILES.update(_STATIC_PAYLOADS)
    extension_builder._SOURCE_FILES.update(_SOURCE_PAYLOADS)
    if not getattr(extension_builder, "_EXACT_TEMPLATE_PAYLOAD_INSTALLED", False):
        extension_builder._payload = _payload_with_template
        extension_builder.verify_calc_extension = _verify_with_template
        extension_builder._EXACT_TEMPLATE_PAYLOAD_INSTALLED = True
