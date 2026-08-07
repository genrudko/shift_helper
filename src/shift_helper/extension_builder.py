"""Build and verify the user-installable LibreOffice Calc extension."""

from __future__ import annotations

import argparse
import ast
import base64
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path, PurePosixPath

_EXTENSION_NAME = "Shift-Helper-Calc-FULL-TEST-001.oxt"
_FIXED_TIMESTAMP = (2026, 8, 6, 0, 0, 0)
_VERSION = "0.4.0.dev0"

_STATIC_FILES = {
    "description.xml": "packaging/libreoffice_extension/description.xml",
    "META-INF/manifest.xml": "packaging/libreoffice_extension/META-INF/manifest.xml",
    "Addons.xcu": "packaging/libreoffice_extension/Addons.xcu",
    "CalcWindowState.xcu": "packaging/libreoffice_extension/CalcWindowState.xcu",
    "shift_helper_controls.py": (
        "packaging/libreoffice_extension/shift_helper_controls.py"
    ),
    "Scripts/python/shift_helper_calc.py": (
        "packaging/libreoffice_extension/Scripts/python/shift_helper_calc.py"
    ),
    "Scripts/python/shift_helper_auto.py": (
        "packaging/libreoffice_extension/Scripts/python/shift_helper_auto.py"
    ),
    "Scripts/python/shift_helper_report.py": (
        "packaging/libreoffice_extension/Scripts/python/shift_helper_report.py"
    ),
    "Scripts/python/shift_helper_tools.py": (
        "packaging/libreoffice_extension/Scripts/python/shift_helper_tools.py"
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
    "Scripts/python/pythonpath/shift_helper/core/operator_tools.py": (
        "src/shift_helper/core/operator_tools.py"
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


def _decode_compressed_runtime(
    loader: str,
    *,
    loader_name: str,
    source_name: str,
) -> str:
    try:
        tree = ast.parse(loader, loader_name)
        payload = None
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(
                isinstance(target, ast.Name) and target.id == "_PAYLOAD"
                for target in node.targets
            ):
                payload = ast.literal_eval(node.value)
                break
        if not isinstance(payload, bytes):
            raise ValueError("_PAYLOAD is missing")
        source = zlib.decompress(base64.b85decode(payload)).decode("utf-8")
        compile(source, source_name, "exec")
        return source
    except Exception as exc:
        raise ExtensionBuildError(
            f"Не удалось проверить {loader_name}: {exc}."
        ) from exc


def _decode_integrated_report(loader: str) -> str:
    return _decode_compressed_runtime(
        loader,
        loader_name="Scripts/python/shift_helper_report.py",
        source_name="shift_helper_report_full.py",
    )


def _decode_operator_tools(loader: str) -> str:
    return _decode_compressed_runtime(
        loader,
        loader_name="Scripts/python/shift_helper_tools.py",
        source_name="shift_helper_tools_full.py",
    )


def verify_calc_extension(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise ExtensionBuildError(f"Расширение не создано: {path}.")

    with zipfile.ZipFile(path) as archive:
        names = tuple(archive.namelist())
        if len(names) != len(set(names)):
            raise ExtensionBuildError("В OXT обнаружены повторяющиеся пути.")
        unsafe = [name for name in names if not _safe_member(name)]
        if unsafe:
            raise ExtensionBuildError(
                f"В OXT обнаружены опасные пути: {unsafe!r}."
            )

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
            raise ExtensionBuildError(f"OXT должен иметь версию {_VERSION}.")

        macro = archive.read("Scripts/python/shift_helper_calc.py").decode("utf-8")
        automatic = archive.read("Scripts/python/shift_helper_auto.py").decode(
            "utf-8"
        )
        report_loader = archive.read(
            "Scripts/python/shift_helper_report.py"
        ).decode("utf-8")
        tools_loader = archive.read(
            "Scripts/python/shift_helper_tools.py"
        ).decode("utf-8")
        tools = _decode_operator_tools(tools_loader)
        helpers = archive.read(
            "Scripts/python/pythonpath/shift_helper/core/operator_tools.py"
        ).decode("utf-8")
        report = _decode_integrated_report(report_loader)
        controls = archive.read("shift_helper_controls.py").decode("utf-8")
        addons = archive.read("Addons.xcu").decode("utf-8")
        window_state = archive.read("CalcWindowState.xcu").decode("utf-8")

        _parse_xml("Addons.xcu", addons)
        _parse_xml("CalcWindowState.xcu", window_state)
        compile(macro, "shift_helper_calc.py", "exec")
        compile(automatic, "shift_helper_auto.py", "exec")
        compile(controls, "shift_helper_controls.py", "exec")
        compile(report_loader, "shift_helper_report.py", "exec")
        compile(tools_loader, "shift_helper_tools.py", "exec")
        compile(helpers, "operator_tools.py", "exec")

        for script_name, script in (
            ("shift_helper_calc.py", macro),
            ("shift_helper_auto.py", automatic),
            ("shift_helper_tools.py", tools),
        ):
            if "__file__" in script:
                raise ExtensionBuildError(
                    f"{script_name} не должен зависеть от __file__."
                )

        _require_markers(
            "shift_helper_auto.py",
            automatic,
            (
                "enable_automatic_input",
                "disable_automatic_input",
                "automatic_input_status",
                "XDispatchProviderInterceptor",
                '".uno:Paste"',
            ),
        )
        _require_markers(
            "shift_helper_report.py loader",
            report_loader,
            ("base64.b85decode", "zlib.decompress", "shift_helper_report_full.py"),
        )
        _require_markers(
            "integrated report runtime",
            report,
            (
                '_VERSION = "0.4.0.dev0"',
                "prepare_report_input_sheets",
                "import_generation_from_outlook",
                "generate_full_report",
                "generate_emergency_report",
                "select_emergency_events",
                "read_uno_journal",
                "os.replace",
                "Ввод - Основные",
                "Ввод - Команды",
                "Ввод - Нарушения",
                "Ввод - Состояние ВЭУ",
                "Ввод - Работы",
                "Ввод - Дефекты",
                "Сумма ВЭС",
                "G26",
                "Q26",
                "g_exportedScripts",
            ),
        )
        if "openpyxl" in report:
            raise ExtensionBuildError(
                "Calc runtime не должен импортировать openpyxl."
            )

        _require_markers(
            "shift_helper_tools.py loader",
            tools_loader,
            ("base64.b85decode", "zlib.decompress", "shift_helper_tools_full.py"),
        )
        _require_markers(
            "operator tools runtime",
            tools,
            (
                "show_calendar",
                "show_time_picker",
                "auto_fit_selected_rows",
                "clean_selected_spaces",
                "merge_and_copy_selection",
                "sort_selected_rows_by_time",
                "insert_wtg_maintenance_text",
                "show_today_inspections",
                "update_rotor_limits_from_log",
                "create_outlook_mail_draft",
                "g_exportedScripts",
            ),
        )
        _require_markers(
            "operator_tools.py",
            helpers,
            (
                "normalize_spaces",
                "maintenance_text",
                "active_rotor_limits",
                "rotor_repair_power",
                "absolute_a1_references",
            ),
        )
        _require_markers(
            "shift_helper_controls.py",
            controls,
            (
                '"prepare": ("report", "prepare_report_input_sheets")',
                '"generation": ("report", "import_generation_from_outlook")',
                '"report": ("report", "generate_full_report")',
                '"calendar": ("tools", "show_calendar")',
                '"time": ("tools", "show_time_picker")',
                '"rotor": ("tools", "update_rotor_limits_from_log")',
                '"mail": ("tools", "create_outlook_mail_draft")',
                "runtime.XSCRIPTCONTEXT",
            ),
        )
        addon_urls = (
            "prepare",
            "generation",
            "report",
            "calendar",
            "time",
            "autofit",
            "clean",
            "mergecopy",
            "sorttime",
            "maintenance",
            "inspections",
            "rotor",
            "mail",
        )
        _require_markers(
            "Addons.xcu",
            addons,
            tuple(
                f"service:ru.kves.shifthelper.calc.controls?{action}"
                for action in addon_urls
            ),
        )
        _require_markers(
            "CalcWindowState.xcu",
            window_state,
            (
                "private:resource/toolbar/addon_ru.kves.shifthelper.calc.toolbar.v033",
                "private:resource/toolbar/addon_ru.kves.shifthelper.calc.tools.v040",
                "<value>true</value>",
            ),
        )

        for name in names:
            if name.endswith(".py"):
                content = archive.read(name).decode("utf-8")
                compile(content, name, "exec")
                if "openpyxl" in content and name.startswith("Scripts/python/"):
                    raise ExtensionBuildError(
                        f"Runtime неожиданно импортирует openpyxl: {name}."
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
