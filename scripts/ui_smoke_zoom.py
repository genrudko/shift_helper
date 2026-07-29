from __future__ import annotations

import os

from playwright.sync_api import ConsoleMessage, Page, sync_playwright


def _capture_console_error(message: ConsoleMessage, errors: list[str]) -> None:
    if message.type == "error":
        errors.append(message.text)


def _presentation_zoom(page: Page, base_url: str) -> float:
    response = page.request.get(f"{base_url}/events/api/v2/presentation")
    if not response.ok:
        raise AssertionError(f"Presentation API вернул HTTP {response.status}.")
    payload = response.json()
    presentation = payload.get("presentation", {})
    sheet = presentation.get("sheet", {}) if isinstance(presentation, dict) else {}
    zoom = sheet.get("zoomRatio") if isinstance(sheet, dict) else None
    if not isinstance(zoom, (int, float)):
        raise AssertionError("Presentation API не вернул масштаб листа.")
    return float(zoom)


def _wait_for_zoom(page: Page, base_url: str, expected: float) -> None:
    for _attempt in range(120):
        if abs(_presentation_zoom(page, base_url) - expected) < 0.0001:
            return
        page.wait_for_timeout(100)
    raise AssertionError(f"Масштаб {expected:.2f} не был сохранён presentation API.")


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
            response = page.goto(f"{base_url}/events/v2", wait_until="networkidle")
            if response is None or not response.ok:
                code = response.status if response is not None else "no response"
                raise AssertionError(f"Journal UI V2 не открылся: {code}")

            control = page.locator('[data-testid="journal-zoom"]')
            control.wait_for(state="visible", timeout=30_000)
            if page.locator("html").get_attribute("data-zoom-control") != "active":
                raise AssertionError("Линейный zoom control не активирован.")

            number = page.locator('[data-testid="journal-zoom-number"]')
            slider = page.locator('[data-testid="journal-zoom-range"]')
            if number.input_value() != "100" or slider.input_value() != "100":
                raise AssertionError("Начальный масштаб журнала отличается от 100%.")

            slider.fill("140")
            slider.dispatch_event("input")
            _wait_for_zoom(page, base_url, 1.4)
            if number.input_value() != "140":
                raise AssertionError("Числовое поле не синхронизировалось со slider.")

            page.reload(wait_until="networkidle")
            page.locator('[data-testid="journal-zoom"][data-zoom="140"]').wait_for(
                state="visible",
                timeout=30_000,
            )
            if page.locator('[data-testid="journal-zoom-number"]').input_value() != "140":
                raise AssertionError("Масштаб 140% не восстановился после reload.")

            sheet = page.locator("#univer-sheet")
            box = sheet.bounding_box()
            if box is None:
                raise AssertionError("Не удалось определить геометрию листа для Ctrl+wheel.")
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.keyboard.down("Control")
            page.mouse.wheel(0, -120)
            page.keyboard.up("Control")
            _wait_for_zoom(page, base_url, 1.5)
            page.locator('[data-testid="journal-zoom"][data-zoom="150"]').wait_for(
                state="visible",
                timeout=10_000,
            )

            number = page.locator('[data-testid="journal-zoom-number"]')
            number.fill("999")
            number.dispatch_event("change")
            _wait_for_zoom(page, base_url, 4.0)
            if number.input_value() != "400":
                raise AssertionError("Верхняя граница масштаба не ограничена 400%.")

            number.fill("1")
            number.dispatch_event("change")
            _wait_for_zoom(page, base_url, 0.1)
            if number.input_value() != "10":
                raise AssertionError("Нижняя граница масштаба не ограничена 10%.")

            if page_errors:
                raise AssertionError("Page errors: " + " | ".join(page_errors))
            if console_errors:
                raise AssertionError("Console errors: " + " | ".join(console_errors))
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
