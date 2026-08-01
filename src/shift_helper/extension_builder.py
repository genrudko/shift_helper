"""Build and verify the user-installable LibreOffice Calc extension."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

_EXTENSION_NAME = "Shift-Helper-Calc-UNO-001.oxt"
_FIXED_TIMESTAMP = (2026, 8, 1, 0, 0, 0)
_VERSION = "0.3.1.dev1"

_STATIC_FILES = {
    "description.xml": "packaging/libreoffice_extension/description.xml",
    "META-INF/manifest.xml": "packaging/libreoffice_extension/META-INF/manifest.xml",
    "Addons.xcu": "packaging/libreoffice_extension/Addons.xcu",
    "CalcWindowState.xcu": "packaging/libreoffice_extension/CalcWindowState.xcu",
    "Scripts/python/shift_helper_calc.py": (
        "packaging/libreoffice_extension/Scripts/python/shift_helper_calc.py"
    ),
    "Scripts/python/shift_helper_auto.py": (
        "packaging/libreoffice_extension/Scripts/python/shift_helper_auto.py"
    ),
}
_SOURCE_FILES = {
    "Scripts/python/pythonpath/shift_helper/core/quick_input.py": (
        "src/shift_helper/core/quick_input.py"
    ),
    "Scripts/python/pythonpath/shift_helper/uno_adapter/calc_selection.py": (
        "src/shift_helper/uno_adapter/calc_selection.py"
    ),
}
_GENERATED_FILES = {
    "Scripts/python/pythonpath/shift_helper/__init__.py": (
        '"""Shift-Helper modules bundled for LibreOffice."""\n'
    ),
    "Scripts/python/pythonpath/shift_helper/core/__init__.py": (
        '"""Pure quick-input core bundled for LibreOffice."""\n'
    ),
    "Scripts/python/pythonpath/shift_helper/uno_adapter/__init__.py": (
        '"""Calc adapter bundled for LibreOffice."""\n'
    ),
}


class ExtensionBuildError(RuntimeError):
    """Raised when the OXT payload violates the packaging contract."""


def _safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def _payload(repo_root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for target, source in {**_STATIC_FILES, **_SOURCE_FILES}.items():
        source_path = repo_root / source
        if not source_path.is_file():
            raise ExtensionBuildError(f"Не найден файл расширения: {source}.")
        files[target] = source_path.read_bytes()
    for target, content in _GENERATED_FILES.items():
        files[target] = content.encode("utf-8")
    return files


def _parse_xml(name: str, content: str) -> None:
    try:
        ET.fromstring(content)
    except ET.ParseError as exc:
        raise ExtensionBuildError(f"{name} повреждён: {exc}.") from exc


def verify_calc_extension(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise ExtensionBuildError(f"Расширение не создано: {path}.")

    with zipfile.ZipFile(path) as archive:
        names = tuple(archive.namelist())
        if len(names) != len(set(names)):
            raise ExtensionBuildError("В OXT обнаружены повторяющиеся пути.")
        unsafe = [name for name in names if not _safe_member(name)]
        if unsafe:
            raise ExtensionBuildError(f"В OXT обнаружены опасные пути: {unsafe!r}.")

        required = set(_STATIC_FILES) | set(_SOURCE_FILES) | set(_GENERATED_FILES)
        missing = sorted(required.difference(names))
        if missing:
            raise ExtensionBuildError(f"В OXT отсутствуют файлы: {missing!r}.")
        if "shift_helper_controls.py" in names:
            raise ExtensionBuildError(
                "Устаревший промежуточный UNO-компонент не должен входить в OXT."
            )

        manifest = archive.read("META-INF/manifest.xml").decode("utf-8")
        if "application/vnd.sun.star.framework-script" not in manifest:
            raise ExtensionBuildError("Manifest не регистрирует Python framework scripts.")
        for registered in ("Scripts/python", "Addons.xcu", "CalcWindowState.xcu"):
            if f'manifest:full-path="{registered}"' not in manifest:
                raise ExtensionBuildError(f"Manifest не регистрирует {registered}.")
        if "application/vnd.sun.star.uno-component;type=Python" in manifest:
            raise ExtensionBuildError(
                "Manifest не должен регистрировать промежуточный Python UNO component."
            )

        description = archive.read("description.xml").decode("utf-8")
        if f'<version value="{_VERSION}"/>' not in description:
            raise ExtensionBuildError(
                f"OXT должен иметь runtime-кандидат версии {_VERSION}."
            )

        macro = archive.read("Scripts/python/shift_helper_calc.py").decode("utf-8")
        automatic = archive.read("Scripts/python/shift_helper_auto.py").decode("utf-8")
        addons = archive.read("Addons.xcu").decode("utf-8")
        window_state = archive.read("CalcWindowState.xcu").decode("utf-8")

        compile(macro, "Scripts/python/shift_helper_calc.py", "exec")
        compile(automatic, "Scripts/python/shift_helper_auto.py", "exec")
        _parse_xml("Addons.xcu", addons)
        _parse_xml("CalcWindowState.xcu", window_state)

        if "__file__" in macro or "__file__" in automatic:
            raise ExtensionBuildError(
                "Макрос не должен зависеть от __file__: LibreOffice ScriptProvider его не задаёт."
            )

        for exported in (
            "show_status",
            "normalize_selected_dates",
            "normalize_selected_times",
            "g_exportedScripts",
        ):
            if exported not in macro:
                raise ExtensionBuildError(
                    f"В диагностическом макросе отсутствует {exported}."
                )

        for exported in (
            "enable_automatic_input",
            "disable_automatic_input",
            "automatic_input_status",
            "g_exportedScripts",
        ):
            if exported not in automatic:
                raise ExtensionBuildError(
                    f"В automatic-макросе отсутствует {exported}."
                )

        for runtime_marker in (
            "XSelectionChangeListener",
            "XModifyListener",
            "XCallback",
            "XDispatchProviderInterceptor",
            "XInterceptorInfo",
            "XDispatch",
            "registerDispatchProviderInterceptor",
            "releaseDispatchProviderInterceptor",
            "queryDispatch",
            "com.sun.star.awt.AsyncCallback",
            "com.sun.star.datatransfer.clipboard.SystemClipboard",
            "getTransferData",
            "enterHiddenUndoContext",
            "enterUndoContext",
            '_PASTE_URL = ".uno:Paste"',
            "_BUFFER_ROWS",
            '_TEXT_FORMAT = "@"',
        ):
            if runtime_marker not in automatic:
                raise ExtensionBuildError(
                    f"В автоматическом UNO-кандидате отсутствует {runtime_marker}."
                )

        script_urls = (
            "vnd.sun.star.script:shift_helper_auto.py$enable_automatic_input"
            "?language=Python&amp;location=user",
            "vnd.sun.star.script:shift_helper_auto.py$disable_automatic_input"
            "?language=Python&amp;location=user",
            "vnd.sun.star.script:shift_helper_auto.py$automatic_input_status"
            "?language=Python&amp;location=user",
        )
        required_ui = (
            "com.sun.star.sheet.SpreadsheetDocument",
            "Включить быстрый ввод",
            "Выключить быстрый ввод",
            "Состояние Shift-Helper",
            *script_urls,
        )
        for marker in required_ui:
            if marker not in addons:
                raise ExtensionBuildError(f"В Addons.xcu отсутствует {marker}.")
        if "service:ru.kves.shifthelper.calc.controls" in addons:
            raise ExtensionBuildError(
                "Addons.xcu не должен обращаться к удалённому control component."
            )

        for marker in (
            "private:resource/toolbar/addon_ru.kves.shifthelper.calc.toolbar",
            "<value>true</value>",
            '<value xml:lang="ru-RU">Shift-Helper</value>',
        ):
            if marker not in window_state:
                raise ExtensionBuildError(
                    f"В CalcWindowState.xcu отсутствует {marker}."
                )

        for name in names:
            if name.endswith(".py"):
                compile(archive.read(name).decode("utf-8"), name, "exec")

    return names


def build_calc_extension(*, repo_root: Path, output: Path) -> Path:
    repo_root = repo_root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    payload = _payload(repo_root)
    pending = output.with_suffix(output.suffix + ".pending")
    pending.unlink(missing_ok=True)

    with zipfile.ZipFile(pending, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(payload):
            if not _safe_member(name):
                raise ExtensionBuildError(f"Опасный путь OXT: {name!r}.")
            info = zipfile.ZipInfo(name, date_time=_FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, payload[name])

    verify_calc_extension(pending)
    pending.replace(output)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist") / _EXTENSION_NAME,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_calc_extension(repo_root=args.repo_root, output=args.output)
    names = verify_calc_extension(result)
    print(f"Built: {result}")
    print(f"Entries: {len(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
