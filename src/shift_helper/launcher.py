"""Portable local launcher for Windows and Linux builds."""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
import webbrowser

from waitress import serve

from .app import create_app

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 17843


def application_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def is_shift_helper_running(host: str, port: int) -> bool:
    """Return True only when the existing listener is another Shift-Helper instance."""
    try:
        with urllib.request.urlopen(
            f"{application_url(host, port)}/health",
            timeout=0.5,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("application") == "Shift-Helper" and payload.get("status") == "ok"
    except (OSError, ValueError, urllib.error.URLError):
        return False


def open_application(url: str) -> None:
    webbrowser.open(url, new=1, autoraise=True)


def main() -> None:
    host = DEFAULT_HOST
    port = int(os.environ.get("SHIFT_HELPER_PORT", str(DEFAULT_PORT)))
    url = application_url(host, port)

    if is_shift_helper_running(host, port):
        open_application(url)
        return

    app = create_app()
    threading.Timer(0.8, open_application, args=(url,)).start()
    serve(app, host=host, port=port, threads=4, clear_untrusted_proxy_headers=True)


if __name__ == "__main__":
    main()
