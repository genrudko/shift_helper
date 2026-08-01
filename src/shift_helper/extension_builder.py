"""Build and verify the user-installable LibreOffice Calc extension."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

_EXTENSION_NAME = "Shift-Helper-Calc-UNO-001.oxt"
_FIXED_TIMESTAMP = (2026, 8, 2, 0, 0, 0)
_VERSION = "0.3.2.dev0"

_STATIC_FILES = {
    "description.xml": "packaging/libreoffice_extension/description.xml",
    "META-INF/manifest.xml": "packaging/libreoffice_extension/META-INF/manifest.xml",
    "Addons.xcu": "packaging/libreoffice_extension/Addons.xcu",
    "CalcWindowState.xcu": "packaging/libreoffice_extension/CalcWindowState.xcu",
    "shift_helper_controls.py": "packaging/libreoffice_extension/shift_helper_controls.py",
    "Scripts/python/shift_helper_calc.py": (
        "packaging/libreoffice_extension/Scripts/python/shift_helper_calc.py"
    ),
    "Scripts/python/shift_helper_auto.py": (
        "packaging/libreoffice_extension/Scripts/python/shift_helper_auto.py"
    ),
    "Scripts/python/shift_helper_report.py": (
        "packaging/libreoffice_extension/Scripts/python/shift_helper_report.py"
    ),
}
_SOURCE_FILES = {
    "Scripts/python/pythonpath/shift_helper/core/quick_input.py": (
        "src/shift_helper/core/quick_input.py"
    ),
    "Scripts/python/pythonpath/shift_helper/core/events.py": (
        "src/shift_helper/core/events.py"
    ),
    "Scripts/python/pythonpath/shift_helper/core/selection.py": (
        "src/shift_helper/core/selection.py"
    ),
    "Scripts/python/pythonpath/shift_helper/uno_adapter/calc_selection.py": (
        "src/shift_helper/uno_adapter/calc_selection.py"
    ),
    "Scripts/python/pythonpath/shift_helper/uno_adapter/report_generation.py": (
        "src/shift_helper/uno_adapter/report_generation.py"
    ),
}
_GENERATED_FILES = {
    "Scripts/python/pythonpath/shift_helper/__init__.py": (
        '"""Shift-Helper modules bundled for LibreOffice."""\n'
    ),
    "Scripts/python/pythonpath/shift_helper/core/__init__.py": (
        '"""Pure Shift-Helper core bundled for LibreOffice."""\n'
    ),
    "Scripts/python/pythonpath/shift_helper/uno_adapter/__init__.py": (
        '"""Calc adapters bundled for LibreOffice."""\n'
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


def _require_markers(name: str, content: str, markers: tuple[str, ...]) -> None:
    for marker in markers:
        if marker not in content:
            raise ExtensionBuildError(f"В {name} отсутствует {marker}.")


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

        manifest = archive.read("META-INF/manifest.xml").decode("utf-8")
        _require_markers(
            "manifest.xml",
            manifest,
            (
                "application/vnd.sun.star.framework-script",
                "application/vnd.sun.star.uno-component;type=Python",
                'manifest:full-path="Scripts/python"',
                'manifest:full-path="shift_helper_controls.py"',
                'manifest:full-path="Addons.xcu"',
                'manifest:full-path="CalcWindowState.xcu"',
            ),
        )

        description = archive.read("description.xml").decode("utf-8")
        if f'<version value="{_VERSION}"/>' not in description:
            raise ExtensionBuildError(
                f"OXT должен иметь runtime-кандидат версии {_VERSION}."
            )

        macro = archive.read("Scripts/python/shift_helper_calc.py").decode("utf-8")
        automatic = archive.read("Scripts/python/shift_helper_auto.py").decode("utf-8")
        report = archive.read("Scripts/python/shift_helper_report.py").decode("utf-8")
        controls = archive.read("shift_helper_controls.py").decode("utf-8")
        addons = archive.read("Addons.xcu").decode("utf-8")
        window_state = archive.read("CalcWindowState.xcu").decode("utf-8")

        _parse_xml("Addons.xcu", addons)
        _parse_xml("CalcWindowState.xcu", window_state)

        if "__file__" in macro or "__file__" in automatic or "__file__" in report:
            raise ExtensionBuildError(
                "Framework scripts must not depend on __file__ under ScriptProvider."
            )

        _require_markers(
            "shift_helper_calc.py",
            macro,
            (
                "show_status",
                "normalize_selected_dates",
                "normalize_selected_times",
                "g_exportedScripts",
            ),
        )
        _require_markers(
            "shift_helper_auto.py",
            automatic,
            (
                "enable_automatic_input",
                "disable_automatic_input",
                "automatic_input_status",
                "XSelectionChangeListener",
                "XModifyListener",
                "XDispatchProviderInterceptor",
                "registerDispatchProviderInterceptor",
                "releaseDispatchProviderInterceptor",
                '".uno:Paste"',
                "g_exportedScripts",
            ),
        )
        _require_markers(
            "shift_helper_report.py",
            report,
            (
                "generate_emergency_report",
                "UnoControlDialogModel",
                "com.sun.star.ui.dialogs.FilePicker",
                "loadComponentFromURL",
                "select_emergency_events",
                "read_uno_journal",
                "REPORT_SHEET",
                "document.isModified()",
                "os.replace",
                "g_exportedScripts",
            ),
        )
        if "openpyxl" in report:
            raise ExtensionBuildError("Calc report runtime must not vendor or import openpyxl.")

        _require_markers(
            "shift_helper_controls.py",
            controls,
            (
                "XJobExecutor",
                "unohelper.ImplementationHelper",
                "ru.kves.shifthelper.calc.controls",
                '"report": ("_shift_helper_extension_report", "shift_helper_report.py")',
                '"report": ("report", "generate_emergency_report")',
                "importlib.util.spec_from_file_location",
                "runtime.XSCRIPTCONTEXT",
            ),
        )
        for forbidden in ("MasterScriptProviderFactory", "vnd.sun.star.script:"):
            if forbidden in controls:
                raise ExtensionBuildError(
                    f"Control component must not use ScriptProvider: {forbidden}."
                )

        _require_markers(
            "Addons.xcu",
            addons,
            (
                "com.sun.star.sheet.SpreadsheetDocument",
                "service:ru.kves.shifthelper.calc.controls?report",
                "service:ru.kves.shifthelper.calc.controls?enable",
                "service:ru.kves.shifthelper.calc.controls?disable",
                "service:ru.kves.shifthelper.calc.controls?status",
                "Сформировать утренний рапорт",
                "Включить быстрый ввод",
                "Выключить быстрый ввод",
                "Состояние Shift-Helper",
            ),
        )
        if "vnd.sun.star.script:" in addons:
            raise ExtensionBuildError(
                "Addons.xcu must not launch Python through ScriptProvider."
            )

        _require_markers(
            "CalcWindowState.xcu",
            window_state,
            (
                "private:resource/toolbar/addon_ru.kves.shifthelper.calc.toolbar.v031",
                "<value>true</value>",
                '<value xml:lang="ru-RU">Shift-Helper</value>',
            ),
        )

        for name in names:
            if name.endswith(".py"):
                content = archive.read(name).decode("utf-8")
                compile(content, name, "exec")
                if "openpyxl" in content and name.startswith("Scripts/python/"):
                    raise ExtensionBuildError(
                        f"LibreOffice runtime payload unexpectedly imports openpyxl: {name}."
                    )

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
