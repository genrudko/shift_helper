"""Register preserved runtimes and reconstruct the embedded Calc template."""

from __future__ import annotations

import base64
import hashlib
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from io import BytesIO
from pathlib import Path

from shift_helper import extension_builder

_TEMPLATE_TARGET = "Templates/report_template.xlsx"
# Historical byte-for-byte SHA of the owner-approved XLSX container. XLSX ZIP
# metadata can change without changing workbook contents, so acceptance is
# enforced below with per-member hashes for every file inside the workbook.
_TEMPLATE_SHA256 = "cde2d2fb042f27dc514f71ac991676e423dd6a68667fbb6d3f928ab610acbb32"
_TEMPLATE_GLOB = "packaging/libreoffice_extension/Templates/report_template.b64.*"
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
_LOCAL_HEADER = struct.Struct("<IHHHHHIIIHH")
_LOCAL_FILE_SIGNATURE = 0x04034B50


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


def _recover_template_archive(content: bytes) -> bytes:
    """Rebuild a valid ZIP central directory from verified local ZIP members."""

    position = 0
    members: dict[str, bytes] = {}
    while position + _LOCAL_HEADER.size <= len(content):
        fields = _LOCAL_HEADER.unpack_from(content, position)
        signature = fields[0]
        if signature != _LOCAL_FILE_SIGNATURE:
            break
        flags = fields[2]
        method = fields[3]
        crc32_expected = fields[6]
        compressed_size = fields[7]
        uncompressed_size = fields[8]
        name_length = fields[9]
        extra_length = fields[10]
        if flags & 0x08:
            raise extension_builder.ExtensionBuildError(
                "Невозможно восстановить шаблон с ZIP data descriptor."
            )
        name_start = position + _LOCAL_HEADER.size
        name_end = name_start + name_length
        data_start = name_end + extra_length
        data_end = data_start + compressed_size
        if data_end > len(content):
            raise extension_builder.ExtensionBuildError(
                "Повреждена локальная запись встроенного шаблона."
            )
        encoding = "utf-8" if flags & 0x0800 else "cp437"
        name = content[name_start:name_end].decode(encoding)
        compressed = content[data_start:data_end]
        if method == zipfile.ZIP_STORED:
            raw = compressed
        elif method == zipfile.ZIP_DEFLATED:
            raw = zlib.decompress(compressed, -zlib.MAX_WBITS)
        else:
            raise extension_builder.ExtensionBuildError(
                f"Неподдерживаемый метод ZIP-сжатия шаблона: {method}."
            )
        if len(raw) != uncompressed_size:
            raise extension_builder.ExtensionBuildError(
                f"Размер файла шаблона не совпадает: {name}."
            )
        if zlib.crc32(raw) & 0xFFFFFFFF != crc32_expected:
            raise extension_builder.ExtensionBuildError(
                f"CRC файла шаблона не совпадает: {name}."
            )
        if name in members:
            raise extension_builder.ExtensionBuildError(
                f"Дублируется файл встроенного шаблона: {name}."
            )
        members[name] = raw
        position = data_end

    expected_names = set(_TEMPLATE_ENTRY_SHA256)
    if set(members) != expected_names:
        missing = sorted(expected_names - set(members))
        extra = sorted(set(members) - expected_names)
        raise extension_builder.ExtensionBuildError(
            f"Не удалось восстановить состав шаблона; missing={missing}, extra={extra}."
        )
    for name, expected in _TEMPLATE_ENTRY_SHA256.items():
        actual = hashlib.sha256(members[name]).hexdigest()
        if actual != expected:
            raise extension_builder.ExtensionBuildError(
                f"Восстановленный файл шаблона изменён: {name}."
            )

    rebuilt = BytesIO()
    with zipfile.ZipFile(
        rebuilt,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, members[name])
    return rebuilt.getvalue()


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
    try:
        _validate_template(content)
    except extension_builder.ExtensionBuildError:
        content = _recover_template_archive(content)
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
