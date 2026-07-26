import json
import re
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from shift_helper import create_app
from shift_helper.models import Event


def _event_form(**overrides: str) -> dict[str, str]:
    values = {
        "start_at": "2026-07-26T18:10",
        "asset_label": "ВЭУ №17",
        "event_type": "rotor_limit",
        "description": "Установлено ограничение по оборотам",
        "reason": "Повышенная вибрация",
        "actions": "Информация передана сменному персоналу",
        "performer": "Иванов И.И.",
        "error_codes": "214",
        "rotor_limit": "0,80",
        "include_in_report": "on",
    }
    values.update(overrides)
    return values


def _journal_row(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "start_date": "26.07.2026",
        "start_time": "18:10",
        "asset_label": "ВЭУ №17",
        "description": "Останов ВЭУ",
        "reason": "Повышенная вибрация",
        "actions": "Передано дежурному инженеру",
        "performer": "Иванов И.И.",
        "end_date": "",
        "end_time": "",
        "author": "Петров П.П.",
        "revision": 0,
    }
    values.update(overrides)
    return values


def _embedded_json(page: str, element_id: str) -> object:
    pattern = rf'<script id="{re.escape(element_id)}" type="application/json">(.*?)</script>'
    match = re.search(pattern, page, re.DOTALL)
    assert match is not None, f"Embedded JSON element not found: {element_id}"
    return json.loads(match.group(1))


def test_event_create_edit_and_close(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    create_response = client.post("/events/new", data=_event_form(), follow_redirects=True)
    assert create_response.status_code == 200
    page = create_response.get_data(as_text=True)
    assert "Событие зарегистрировано" in page
    rows = _embedded_json(page, "event-journal-data")
    assert isinstance(rows, list)
    assert any(row["asset_label"] == "ВЭУ №17" for row in rows)

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        event = session.scalar(select(Event))
        assert event is not None
        event_id = event.id
        assert str(event.rotor_limit) == "0.80"
        assert str(event.repair_power_mw) == "1.00"
        assert event.status == "open"
        assert event.include_in_report is True

    edit_response = client.post(
        f"/events/{event_id}/edit",
        data=_event_form(reason="Причина уточнена", rotor_limit="0.90"),
        follow_redirects=True,
    )
    assert edit_response.status_code == 200
    assert "Изменения сохранены" in edit_response.get_data(as_text=True)

    with Session(engine) as session:
        event = session.get(Event, event_id)
        assert event is not None
        assert event.reason == "Причина уточнена"
        assert str(event.repair_power_mw) == "0.55"
        assert event.revision == 2

    close_response = client.post(f"/events/{event_id}/close", follow_redirects=True)
    assert close_response.status_code == 200
    assert "Событие завершено" in close_response.get_data(as_text=True)

    with Session(engine) as session:
        event = session.get(Event, event_id)
        assert event is not None
        assert event.status == "closed"
        assert event.end_at is not None
        assert event.revision == 3


def test_invalid_rotor_limit_is_rejected(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    response = client.post("/events/new", data=_event_form(rotor_limit="1,20"))

    assert response.status_code == 200
    assert "не больше 1" in response.get_data(as_text=True)

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        assert session.scalar(select(Event)) is None


def test_spreadsheet_workspace_uses_one_offline_controller(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    response = client.get("/events")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="event-journal"' in page
    assert 'id="event-journal-data"' in page
    assert 'id="event-journal-suggestions"' in page
    assert "vendor/tabulator/tabulator.min.css" in page
    assert "vendor/tabulator/tabulator.min.js" in page
    assert "event_journal_excel_patch.css" in page
    assert "event_journal_excel_patch.js" not in page
    assert "event_journal_menu_guard.js" not in page
    assert "event_journal_row_context.js" not in page
    assert 'data-status-filter="all"' in page
    assert 'id="journal-search"' in page
    assert 'id="cell-fill-color"' in page
    assert 'id="format-rules-dialog"' in page
    assert "+ Новое событие" not in page
    assert ">Создать событие<" not in page

    grid_script = client.get("/static/event_journal.js")
    grid_styles = client.get("/static/event_journal_excel_patch.css")
    assert grid_script.status_code == 200
    assert grid_styles.status_code == 200
    script_text = grid_script.get_data(as_text=True)
    style_text = grid_styles.get_data(as_text=True)
    assert "new window.Tabulator" in script_text
    assert 'title: "Дата останова"' in script_text
    assert 'title: "№ ВЭУ / оборудование"' in script_text
    assert "selectableRange: 1" in script_text
    assert "function journalEditor" in script_text
    assert 'event.key === "Enter"' in script_text
    assert "multiline && event.shiftKey" in script_text
    assert 'document.addEventListener("keydown"' in script_text
    assert 'document.addEventListener("copy"' in script_text
    assert 'document.addEventListener("paste"' in script_text
    assert "rowHeaderMenu" in script_text
    assert "contextMenu: rowHeaderMenu" in script_text
    assert "contextMenu: cellMenu" in script_text
    assert "downtime_losses_rub" in script_text
    assert ".journal-stable-editor" in style_text
    assert "position: fixed" not in style_text

    vendor_script = client.get("/static/vendor/tabulator/tabulator.min.js")
    vendor_styles = client.get("/static/vendor/tabulator/tabulator.min.css")
    assert vendor_script.status_code == 200
    assert vendor_styles.status_code == 200
    assert len(vendor_script.data) > 400_000
    assert len(vendor_styles.data) > 20_000


def test_journal_embeds_history_values_for_autocomplete(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    create_response = client.post("/events/rows", json=_journal_row())
    assert create_response.status_code == 201

    page = client.get("/events").get_data(as_text=True)
    rows = _embedded_json(page, "event-journal-data")
    suggestions = _embedded_json(page, "event-journal-suggestions")

    assert isinstance(rows, list)
    assert isinstance(suggestions, dict)
    assert rows[0]["asset_label"] == "ВЭУ №17"
    assert "ВЭУ №17" in suggestions["asset_label"]
    assert "Иванов И.И." in suggestions["performer"]
    assert "Петров П.П." in suggestions["author"]
    assert "Повышенная вибрация" in suggestions["reason"]
    assert "Передано дежурному инженеру" in suggestions["actions"]


def test_inline_row_calculates_downtime_and_source_workbook_losses(
    tmp_path: Path,
) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    create_response = client.post("/events/rows", json=_journal_row())
    create_payload = create_response.get_json()

    assert create_response.status_code == 201
    assert create_payload["ok"] is True
    assert create_payload["row"]["status"] == "open"
    assert create_payload["row"]["author"] == "Петров П.П."
    assert create_payload["row"]["downtime_losses_rub"] == ""
    event_id = create_payload["row"]["id"]
    revision = create_payload["row"]["revision"]

    update_response = client.patch(
        f"/events/{event_id}/row",
        json=_journal_row(
            end_date="26.07.2026",
            end_time="20:40",
            revision=revision,
        ),
    )
    update_payload = update_response.get_json()

    assert update_response.status_code == 200
    assert update_payload["ok"] is True
    assert update_payload["row"]["status"] == "closed"
    assert update_payload["row"]["downtime"] == "2 ч 30 мин"
    assert update_payload["row"]["downtime_losses_rub"] == "6250"

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        event = session.get(Event, event_id)
        assert event is not None
        assert event.end_at is not None
        assert event.status == "closed"
        assert event.author == "Петров П.П."
        assert event.downtime_losses_rub == Decimal("6250.00")
