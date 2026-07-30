from __future__ import annotations

import os
from urllib.parse import urlsplit

from playwright.sync_api import ConsoleMessage, sync_playwright

PRIMARY_PATH = "/events/v2"


def _capture_console_error(message: ConsoleMessage, errors: list[str]) -> None:
    if message.type == "error":
        errors.append(message.text)


def main() -> None:
    base_url = os.environ.get("SHIFT_HELPER_BASE_URL", "http://127.0.0.1:17944")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            device_scale_factor=1,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )
        page = context.new_page()
        page_errors: list[str] = []
        console_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("console", lambda message: _capture_console_error(message, console_errors))

        try:
            for path in ("", "/events", "/events/new", "/events/999/edit"):
                response = page.goto(f"{base_url}{path}", wait_until="networkidle")
                if response is None or not response.ok:
                    status = response.status if response is not None else "no response"
                    raise AssertionError(f"Маршрут {path or '/'} не открылся: {status}")
                if urlsplit(page.url).path != PRIMARY_PATH:
                    raise AssertionError(
                        f"Маршрут {path or '/'} оставил пользователя на {page.url}."
                    )
                page.locator("#app").wait_for(state="visible", timeout=30_000)
                page.locator("#univer-sheet").wait_for(state="visible", timeout=30_000)
                if page.locator("text=Создать событие").count() > 0:
                    raise AssertionError("В primary runtime отображается legacy-кнопка.")

            if page_errors:
                raise AssertionError("Page errors: " + " | ".join(page_errors))
            if console_errors:
                raise AssertionError("Console errors: " + " | ".join(console_errors))
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
