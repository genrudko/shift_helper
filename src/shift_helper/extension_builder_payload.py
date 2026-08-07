"""Register preserved runtimes and reconstruct the embedded Calc template."""

from __future__ import annotations

import base64
import binascii
import hashlib
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from io import BytesIO
from pathlib import Path

from shift_helper import extension_builder

_TEMPLATE_TARGET = "Templates/report_template.xlsx"
# Byte-for-byte SHA of the owner-approved historical XLSX container.
_TEMPLATE_SHA256 = "cde2d2fb042f27dc514f71ac991676e423dd6a68667fbb6d3f928ab610acbb32"
_TEMPLATE_CHUNK_PREFIX = (
    "packaging/libreoffice_extension/Templates/report_template.b64."
)
_TEMPLATE_CHUNK_COUNT = 8
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
_LOCAL_HEADER = struct.Struct("<4s5H3I2H")
_LOCAL_SIGNATURE = b"PK\x03\x04"
_CENTRAL_SIGNATURE = b"PK\x01\x02"
_END_SIGNATURE = b"PK\x05\x06"


def _template_sheet_names(content: bytes) -> tuple[str, ...]:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    except (KeyError, ET.ParseError, ValueError, zipfile.BadZipFile) as exc:
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
    except (ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        raise extension_builder.ExtensionBuildError(
            "Встроенный шаблон рапорта не является корректной книгой XLSX."
        ) from exc
    if _template_sheet_names(content) != _TEMPLATE_SHEETS:
        raise extension_builder.ExtensionBuildError(
            "Состав или порядок листов встроенного шаблона изменён."
        )


def _raw_template_bytes(repo_root: Path) -> bytes:
    chunks: list[str] = []
    missing: list[str] = []
    for index in range(_TEMPLATE_CHUNK_COUNT):
        path = repo_root / f"{_TEMPLATE_CHUNK_PREFIX}{index:02d}"
        if not path.is_file():
            missing.append(path.name)
            continue
        chunks.append(path.read_text(encoding="ascii"))
    if missing:
        raise extension_builder.ExtensionBuildError(
            f"Не найдены канонические части встроенного шаблона: {missing}."
        )
    try:
        content = base64.b64decode("".join(chunks), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise extension_builder.ExtensionBuildError(
            "Канонические части встроенного шаблона не являются корректным Base64."
        ) from exc
    actual_sha = hashlib.sha256(content).hexdigest()
    if actual_sha != _TEMPLATE_SHA256:
        raise extension_builder.ExtensionBuildError(
            "Канонический контейнер шаблона не совпадает с утверждённым SHA-256: "
            f"{actual_sha}."
        )
    return content


def _decode_member(method: int, compressed: bytes) -> bytes:
    if method == zipfile.ZIP_STORED:
        return compressed
    if method == zipfile.ZIP_DEFLATED:
        try:
            return zlib.decompress(compressed, -zlib.MAX_WBITS)
        except zlib.error as exc:
            raise extension_builder.ExtensionBuildError(
                "Повреждены локальные сжатые данные утверждённого шаблона."
            ) from exc
    raise extension_builder.ExtensionBuildError(
        f"Неподдерживаемый метод сжатия шаблона: {method}."
    )


def _verified_local_members(content: bytes) -> list[tuple[str, int, bytes]]:
    """Read local ZIP records without trusting the historical central directory."""

    offset = 0
    result: list[tuple[str, int, bytes]] = []
    seen: set[str] = set()
    while offset + 4 <= len(content):
        signature = content[offset : offset + 4]
        if signature in {_CENTRAL_SIGNATURE, _END_SIGNATURE}:
            break
        if signature != _LOCAL_SIGNATURE or offset + _LOCAL_HEADER.size > len(content):
            raise extension_builder.ExtensionBuildError(
                "Нарушена последовательность локальных ZIP-записей шаблона."
            )
        (
            _signature,
            _version,
            flags,
            method,
            _mtime,
            _mdate,
            expected_crc,
            compressed_size,
            uncompressed_size,
            name_size,
            extra_size,
        ) = _LOCAL_HEADER.unpack_from(content, offset)
        if flags & 0x08:
            raise extension_builder.ExtensionBuildError(
                "Шаблон использует ZIP data descriptor; безопасное восстановление запрещено."
            )
        name_start = offset + _LOCAL_HEADER.size
        name_end = name_start + name_size
        data_start = name_end + extra_size
        data_end = data_start + compressed_size
        if data_end > len(content):
            raise extension_builder.ExtensionBuildError(
                "Обрезаны локальные данные утверждённого шаблона."
            )
        encoding = "utf-8" if flags & 0x800 else "cp437"
        try:
            name = content[name_start:name_end].decode(encoding)
        except UnicodeDecodeError as exc:
            raise extension_builder.ExtensionBuildError(
                "Повреждено имя файла внутри утверждённого шаблона."
            ) from exc
        if name in seen:
            raise extension_builder.ExtensionBuildError(
                f"Дублируется локальная ZIP-запись шаблона: {name}."
            )
        payload = _decode_member(method, content[data_start:data_end])
        if len(payload) != uncompressed_size:
            raise extension_builder.ExtensionBuildError(
                f"Неверный размер файла внутри шаблона: {name}."
            )
        actual_crc = binascii.crc32(payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise extension_builder.ExtensionBuildError(
                f"Неверная CRC файла внутри шаблона: {name}."
            )
        expected_sha = _TEMPLATE_ENTRY_SHA256.get(name)
        if expected_sha is None:
            raise extension_builder.ExtensionBuildError(
                f"Неизвестный файл внутри утверждённого шаблона: {name}."
            )
        actual_sha = hashlib.sha256(payload).hexdigest()
        if actual_sha != expected_sha:
            raise extension_builder.ExtensionBuildError(
                f"Содержимое файла шаблона отличается от утверждённого: {name}."
            )
        result.append((name, method, payload))
        seen.add(name)
        offset = data_end

    if seen != set(_TEMPLATE_ENTRY_SHA256):
        missing = sorted(set(_TEMPLATE_ENTRY_SHA256) - seen)
        extra = sorted(seen - set(_TEMPLATE_ENTRY_SHA256))
        raise extension_builder.ExtensionBuildError(
            "Локальные ZIP-записи не воспроизводят утверждённый шаблон: "
            f"missing={missing}, extra={extra}."
        )
    return result


def _repair_template_container(content: bytes) -> bytes:
    """Rebuild only ZIP metadata after proving every OOXML member exactly."""

    members = _verified_local_members(content)
    target = BytesIO()
    with zipfile.ZipFile(target, "w") as archive:
        for name, method, payload in members:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = method
            info.create_system = 0
            info.external_attr = 0
            if method == zipfile.ZIP_DEFLATED:
                archive.writestr(info, payload, compress_type=method, compresslevel=9)
            else:
                archive.writestr(info, payload, compress_type=method)
    repaired = target.getvalue()
    _validate_template(repaired)
    return repaired


def _template_bytes(repo_root: Path) -> bytes:
    raw = _raw_template_bytes(repo_root)
    try:
        _validate_template(raw)
        return raw
    except extension_builder.ExtensionBuildError:
        # The owner-approved historical XLSX has a central-directory offset
        # defect. Repair ZIP metadata only; the raw container SHA and every
        # decompressed OOXML member are independently fail-closed above.
        return _repair_template_container(raw)


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
