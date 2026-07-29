from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def _seed_event(page: Page, base_url: str) -> None:
    response = page.request.post(
        f"{base_url}/events/new",
        form={
            "start_at": "2026-07-29T11:30",
            "asset_label": "ВЭУ №17",
            "event_type": "rotor_limit",
            "description": "Проверка чистого Univer UI V2",
            "reason": "Chromium acceptance contract",
            "actions": "Отображение записи в журнале",
            "performer": "Иванов И.И.",
            "error_codes": "214",
            "rotor_limit": "0,80",
            "include_in_report": "on",
        },
    )
    if not response.ok:
        raise AssertionError(f"Не удалось создать тестовую запись: HTTP {response.status}")


def main() -> None:
    base_url = os.environ.get("SHIFT_HELPER_BASE_URL", "http://127.0.0.1:17944")
    screenshot_path = Path(
        os.environ.get("SHIFT_HELPER_UI_SCREENSHOT", "ui-v2-smoke/univer-v2.png")
    )
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
        page_errors: list[str] = []
        console_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "console",
            lambda message: console_errors.append(message.text) if message.type == "error" else None,
        )

        try:
            _seed_event(page, base_url)
            response = page.goto(f"{base_url}/events/v2", wait_until="networkidle")
            if response is None or not response.ok:
                status = response.status if response is not None else "no response"
                raise AssertionError(f"Journal UI V2 не открылся: {status}")

            page.locator(".shift-helper-v2__status").filter(
                has_text="Загружено записей: 1"
            ).wait_for(state="visible", timeout=30_000)
            page.locator(".shift-helper-v2__error").wait_for(state="detached", timeout=5_000)

            canvas_count = page.locator("canvas").count()
            if canvas_count < 1:
                raise AssertionError("Univer не создал ни одного canvas.")

            visible_canvas = False
            for index in range(canvas_count):
                canvas = page.locator("canvas").nth(index)
                box = canvas.bounding_box()
                if box and box["width"] > 500 and box["height"] > 300:
                    visible_canvas = True
                    break
            if not visible_canvas:
                raise AssertionError("Univer canvas не получил рабочую геометрию журнала.")

            if page_errors:
                raise AssertionError("Page errors: " + " | ".join(page_errors))
            if console_errors:
                raise AssertionError("Console errors: " + " | ".join(console_errors))

            page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            page.screenshot(path=str(screenshot_path), full_page=True)
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
