from __future__ import annotations

import os

from playwright.sync_api import ConsoleMessage, sync_playwright


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
            snapshot_response = page.request.get(
                f"{base_url}/events/api/v3/snapshot"
            )
            if not snapshot_response.ok:
                raise AssertionError(
                    f"Snapshot v3 вернул HTTP {snapshot_response.status}."
                )
            snapshot = snapshot_response.json()
            records = snapshot.get("records")
            if not isinstance(records, list) or not records:
                raise AssertionError(
                    "Runtime-files smoke должен получить хотя бы одну рабочую запись."
                )
            expected_count = len(records)

            status_response = page.request.get(
                f"{base_url}/events/api/v2/runtime-status"
            )
            if not status_response.ok:
                raise AssertionError(
                    f"Runtime status вернул HTTP {status_response.status}."
                )
            status = status_response.json()
            event_mirror = status.get("eventMirror", {})
            database_backup = status.get("databaseBackup", {})
            if event_mirror.get("recordCount") != expected_count:
                raise AssertionError(
                    "Excel-копия не совпадает с числом рабочих записей: "
                    f"{event_mirror.get('recordCount')!r} != {expected_count}."
                )
            if database_backup.get("eventCount") != expected_count:
                raise AssertionError(
                    "Резервная копия не совпадает с числом рабочих записей: "
                    f"{database_backup.get('eventCount')!r} != {expected_count}."
                )
            if not event_mirror.get("downloadAvailable"):
                raise AssertionError("Excel-копия недоступна для скачивания.")
            if not database_backup.get("downloadAvailable"):
                raise AssertionError("Резервная копия недоступна для скачивания.")
            if any("/home/" in str(value) for value in status.values()):
                raise AssertionError("Runtime status раскрыл локальный путь runner-а.")

            spreadsheet = page.request.get(f"{base_url}/events/export.xlsx")
            if not spreadsheet.ok or not spreadsheet.body().startswith(b"PK"):
                raise AssertionError("Скачанная Excel-копия не является XLSX ZIP-пакетом.")

            backup = page.request.get(f"{base_url}/backups/latest.zip")
            if not backup.ok or not backup.body().startswith(b"PK"):
                raise AssertionError("Скачанная резервная копия не является ZIP-пакетом.")

            response = page.goto(f"{base_url}/events/v2", wait_until="networkidle")
            if response is None or not response.ok:
                code = response.status if response is not None else "no response"
                raise AssertionError(f"Journal UI V2 не открылся: {code}")

            container = page.locator('[data-testid="runtime-files"]')
            container.wait_for(state="visible", timeout=30_000)
            page.locator('[data-testid="runtime-files"][data-state="ready"]').wait_for(
                state="visible", timeout=30_000
            )
            spreadsheet_link = page.locator('[data-testid="download-event-xlsx"]')
            backup_link = page.locator('[data-testid="download-latest-backup"]')
            if spreadsheet_link.get_attribute("href") != "/events/export.xlsx":
                raise AssertionError("Ссылка на Excel-копию настроена неверно.")
            if backup_link.get_attribute("href") != "/backups/latest.zip":
                raise AssertionError("Ссылка на резервную копию настроена неверно.")
            if spreadsheet_link.get_attribute("aria-disabled") != "false":
                raise AssertionError("Ссылка на Excel-копию осталась заблокированной.")
            if backup_link.get_attribute("aria-disabled") != "false":
                raise AssertionError("Ссылка на backup осталась заблокированной.")

            if page_errors:
                raise AssertionError("Page errors: " + " | ".join(page_errors))
            if console_errors:
                raise AssertionError("Console errors: " + " | ".join(console_errors))
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()
