"""Portable local launcher for Windows and Linux builds."""

from __future__ import annotations

import json
import os
import threading
import urllib.request
import webbrowser

from waitress import serve

from .app import create_app
from .security import MINIMUM_LAN_TOKEN_LENGTH, is_loopback_bind_host

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 17843
PRIMARY_APPLICATION_PATH = "/events/v2"


def application_url(host: str, port: int) -> str:
    display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"http://{display_host}:{port}"


def primary_application_url(host: str, port: int) -> str:
    """Return the only user-facing runtime entry point."""

    return f"{application_url(host, port)}{PRIMARY_APPLICATION_PATH}"


def browser_host(bind_host: str) -> str:
    if bind_host == "0.0.0.0":
        return "127.0.0.1"
    if bind_host == "::":
        return "::1"
    return bind_host


def is_shift_helper_running(host: str, port: int, lan_token: str | None = None) -> bool:
    """Return True only when the existing listener is another Shift-Helper instance."""

    request = urllib.request.Request(f"{application_url(host, port)}/health")
    if lan_token:
        request.add_header("X-Shift-Helper-LAN-Token", lan_token)
    try:
        with urllib.request.urlopen(request, timeout=0.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("application") == "Shift-Helper" and payload.get("status") == "ok"
    except (OSError, ValueError):
        return False


def open_application(url: str) -> None:
    webbrowser.open(url, new=1, autoraise=True)


def main() -> None:
    host = os.environ.get("SHIFT_HELPER_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    port = int(os.environ.get("SHIFT_HELPER_PORT", str(DEFAULT_PORT)))
    if port < 1 or port > 65535:
        raise SystemExit("SHIFT_HELPER_PORT должен быть в диапазоне 1–65535.")

    lan_mode = not is_loopback_bind_host(host)
    lan_token = os.environ.get("SHIFT_HELPER_LAN_TOKEN") if lan_mode else None
    if lan_mode and (not lan_token or len(lan_token) < MINIMUM_LAN_TOKEN_LENGTH):
        raise SystemExit(
            "Для LAN-режима задайте SHIFT_HELPER_LAN_TOKEN длиной не менее "
            f"{MINIMUM_LAN_TOKEN_LENGTH} символов."
        )

    local_host = browser_host(host)
    local_url = primary_application_url(local_host, port)
    probe_token = lan_token if local_host == host and lan_mode else None
    if is_shift_helper_running(local_host, port, probe_token):
        open_application(local_url)
        return

    app = create_app(lan_mode=lan_mode, lan_token=lan_token)
    if lan_mode:
        print(
            f"Shift-Helper LAN mode: bind={host}:{port}; "
            "remote clients must open /lan/login."
        )
    threading.Timer(0.8, open_application, args=(local_url,)).start()
    serve(app, host=host, port=port, threads=4, clear_untrusted_proxy_headers=True)


if __name__ == "__main__":
    main()
