from __future__ import annotations

import argparse
import urllib.error
import urllib.parse
import urllib.request

PRIMARY_PATH = "/events/v2"
REQUIRED_ASSETS = (
    "/static/univer-v2/journal-v2.css",
    "/static/univer-v2/journal-v2.js",
)
LEGACY_MARKERS = (
    "Создать событие",
    "Новое событие",
    "events/list.html",
)


def _open(url: str) -> tuple[str, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.geturl(), response.read()
    except urllib.error.URLError as exc:
        raise SystemExit(f"Не удалось открыть {url}: {exc}") from exc


def _assert_primary_redirect(base_url: str, path: str) -> str:
    final_url, body = _open(f"{base_url}{path}")
    final_path = urllib.parse.urlsplit(final_url).path
    if final_path != PRIMARY_PATH:
        raise SystemExit(
            f"Маршрут {path or '/'} открыл {final_path}, ожидался {PRIMARY_PATH}."
        )

    html = body.decode("utf-8")
    if 'id="app"' not in html:
        raise SystemExit(f"Маршрут {path or '/'} не открыл host Univer.")
    for asset in REQUIRED_ASSETS:
        if asset not in html:
            raise SystemExit(f"Host Univer не содержит asset {asset}.")
    for marker in LEGACY_MARKERS:
        if marker in html:
            raise SystemExit(f"В primary runtime обнаружен legacy marker: {marker}")
    return html


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("port", type=int)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    display_host = f"[{args.host}]" if ":" in args.host else args.host
    base_url = f"http://{display_host}:{args.port}"

    for path in ("", "/events", "/events/new", "/events/999/edit"):
        _assert_primary_redirect(base_url, path)

    for asset in REQUIRED_ASSETS:
        final_url, body = _open(f"{base_url}{asset}")
        if urllib.parse.urlsplit(final_url).path != asset or not body:
            raise SystemExit(f"Packaged Univer asset недоступен: {asset}")

    print(f"Verified primary Univer runtime at {base_url}{PRIMARY_PATH}")


if __name__ == "__main__":
    main()
