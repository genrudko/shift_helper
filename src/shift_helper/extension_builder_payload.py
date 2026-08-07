"""Register preserved runtimes and reconstruct the embedded Calc template."""

from __future__ import annotations

import base64
import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path

from shift_helper import extension_builder

_TEMPLATE_TARGET = "Templates/report_template.xlsx"
# Historical byte-for-byte SHA of the owner-approved XLSX container. XLSX ZIP
# metadata can change without changing workbook contents, so acceptance is
# also enforced below with per-member hashes for every file inside the workbook.
_TEMPLATE_SHA256 = "cde2d2fb042f27dc514f71ac991676e423dd6a68667fbb6d3f928ab610acbb32"
_TEMPLATE_GLOB = "packaging/libreoffice_extension/Templates/report_template.b64.*"
_TEMPLATE_CHUNK_RE = re.compile(r"report_template\.b64\.(\d{2})$")
_TEMPLATE_ZERO_SPLIT_RE = re.compile(r"report_template\.b64\.00([a-z]+)$")
_TEMPLATE_SHEETS = (
    "Основные данные",
    "Аварийные отключения ЛЭП",
    "Команды по внешней инициативе",
    "Нарушения ОТиПБ + Экология",
    "Состояние ВЭУ",
    "Запланированные работы",
    "Дефекты оборудования",
)
_TEMPLATE_ENTRY_SHA256 = {
    "[Content_Types].xml": "b2ffd7170af2c15392053a4845e071e84e15b97316b13346048ccb1bf7596eb1",
    "_rels/.rels": "73e5a29f48d5ab979eeda062493bc7e679265c1344ef936978b8becec5549497",
    "docProps/app.xml": "860cb97fb2919e350002c6f6d4dfb22a8c501652f8aeabc0342002a5cd5dddad",
    "docProps/core.xml": "4305d9941e41e155c6ebd22df64f54e6113475f6c59592607855bce00078a502",
    "xl/_rels/workbook.xml.rels": "cba88cc6c179af47ac5f375796dfa0d25cd299ea284b82c1a386db7fc454c342",
    "xl/calcChain.xml": "cf4915a187379023497c43d06c13c5c231dcb11bdf52426172ced1e137be19ce",
    "xl/printerSettings/printerSettings1.bin": "e9d7ada1f52b5893834a03932274e72084541655237b77f843bbcdda32d8c940",
    "xl/sharedStrings.xml": "96ac18e2137e56be3ea261bc95ec295e9ce194224885c0cce47288bfdc90d8b4",
    "xl/styles.xml": "3681e53a9768d7bd7982c0e136f3bf36c56a375ba28ed6e5b595b290699d4d94",
    "xl/theme/theme1.xml": "156137ac2d7fae74e0286df47c4d1c75e65d5ef1455ff74c4d46176aef06fe56",
    "xl/workbook.xml": "0b6c0bed216af244fc7f52db9a3efe932ad523fb2e5d1bd9487f6d66228df72a",
    "xl/worksheets/_rels/sheet5.xml.rels": "65cefb6727e21f882eb83bb6c10370afa59aafda7f007f531df0c30026dc4684",
    "xl/worksheets/sheet1.xml": "1def38961c9b8218e9ab0f5e64ff19adacfd05bdfe57d4e484aa57b2682d8fd8",
    "xl/worksheets/sheet2.xml": "38df0073ddcf6183dfa7c14fbbb2b2293ae2b6458dedb8369a43a7709da79390",
    "xl/worksheets/sheet3.xml": "46563b1fc91ed0397f635670cde2999a6b2ff79830d9f3ef1de61bc5f5b0587f",
    "xl/worksheets/sheet4.xml": "c25824c4e75a47485e27af297369c52f0dfcb19870389ebb278138ac0a794c2f",
    "xl/worksheets/sheet5.xml": "502f80a4b25a8bc5be8a47b44e57f124dc4f1c2fada9b86db9334d9ffd9b8565",
    "xl/worksheets/sheet6.xml": "8ad81b26e8e9b7099fb01d7e6986ac29297a54c77af8459a1cfffece099118bd",
    "xl/worksheets/sheet7.xml": "e16dc7cc65e7ccf76abb45f97e6ebdaef6a115189ec2b9ec6fa365c57a4b634a",
}
_STATIC_PAYLOADS = {
    "Scripts/python/shift_helper_tools_payload.py": (
        "packaging/libreoffice_extension/Scripts/python/shift_helper_tools_payload.py"
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
    namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    sheets = workbook.find("m:sheets", namespace)
    if sheets is None:
        raise extension_builder.ExtensionBuildError(
            "Во встроенном шаблоне отсутствует список листов."
        )
    return tuple(item.attrib["name"] for item in sheets)


def _validate_template(content: bytes) -> None:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            names = tuple(sorted(archive.namelist()))
            expected_names = tuple(sorted(_TEMPLATE_ENTRY_SHA256))
            if names != expected_names:
                raise extension_builder.ExtensionBuildError(
                    "Состав файлов встроенного шаблона рапорта изменён."
                )
            bad = archive.testzip()
            if bad is not None:
                raise extension_builder.ExtensionBuildError(
                    f"Повреждён файл встроенного шаблона: {bad}."
                )
            for name, expected in _TEMPLATE_ENTRY_SHA256.items():
                actual = hashlib.sha256(archive.read(name)).hexdigest()
                if actual != expected:
                    raise extension_builder.ExtensionBuildError(
                        f"Содержимое встроенного шаблона изменено: {name}."
                    )
    except zipfile.BadZipFile as exc:
        raise extension_builder.ExtensionBuildError(
            "Встроенный шаблон рапорта не является корректной книгой XLSX."
        ) from exc
    if _template_sheet_names(content) != _TEMPLATE_SHEETS:
        raise extension_builder.ExtensionBuildError(
            "Состав или порядок листов встроенного шаблона изменён."
        )


def _template_encoded(repo_root: Path) -> str:
    """Return numbered 00..NN stream and validate historical split aliases."""

    paths = sorted(repo_root.glob(_TEMPLATE_GLOB))
    if not paths:
        raise extension_builder.ExtensionBuildError(
            "Не найдены части встроенного шаблона рапорта."
        )

    numbered: dict[int, Path] = {}
    zero_split: list[Path] = []
    unknown: list[str] = []
    for path in paths:
        numbered_match = _TEMPLATE_CHUNK_RE.fullmatch(path.name)
        if numbered_match is not None:
            index = int(numbered_match.group(1))
            if index in numbered:
                raise extension_builder.ExtensionBuildError(
                    f"Дублируется часть встроенного шаблона: {index:02d}."
                )
            numbered[index] = path
            continue
        if _TEMPLATE_ZERO_SPLIT_RE.fullmatch(path.name) is not None:
            zero_split.append(path)
            continue
        unknown.append(path.name)

    if unknown:
        raise extension_builder.ExtensionBuildError(
            f"Неизвестные части встроенного шаблона: {sorted(unknown)}."
        )
    if not numbered or 0 not in numbered:
        raise extension_builder.ExtensionBuildError(
            "Отсутствует нулевая часть встроенного шаблона рапорта."
        )

    indexes = sorted(numbered)
    if indexes != list(range(indexes[-1] + 1)):
        raise extension_builder.ExtensionBuildError(
            f"Нарушена последовательность частей шаблона: {indexes}."
        )
    canonical = "".join(numbered[index].read_text(encoding="ascii") for index in indexes)

    # PR #15 retained an older three-file split (00a/00b/00c) of the beginning
    # of the very same Base64 stream. It overlaps 00 and the start of 01, so it
    # must never be concatenated as an additional payload. Keep it only as
    # fail-closed evidence that the historical split still matches the prefix.
    if zero_split:
        split_prefix = "".join(
            path.read_text(encoding="ascii") for path in sorted(zero_split)
        )
        if not canonical.startswith(split_prefix):
            raise extension_builder.ExtensionBuildError(
                "Историческое разбиение 00a/00b/00c расходится с каноническим шаблоном."
            )
    return canonical


def _template_bytes(repo_root: Path) -> bytes:
    encoded = _template_encoded(repo_root)
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
