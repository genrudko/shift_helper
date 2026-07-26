"""Wait until a packaged Shift-Helper instance answers its health endpoint."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


def wait_for_health(port: int, *, attempts: int = 60, delay_seconds: float = 0.5) -> None:
    """Fail when the packaged application does not become healthy in time."""
    url = f"http://127.0.0.1:{port}/health"
    last_error: Exception | None = None

    for _attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("application") == "Shift-Helper" and payload.get("status") == "ok":
                print(f"Shift-Helper is healthy at {url}")
                return
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(delay_seconds)

    raise RuntimeError(f"Shift-Helper did not become healthy at {url}: {last_error}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: wait_for_health.py <port>")
    wait_for_health(int(sys.argv[1]))


if __name__ == "__main__":
    main()
