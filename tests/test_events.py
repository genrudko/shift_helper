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


def _v2_create_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "startAt": "2026-07-29T16:20",
        "assetLabel": " ВЭУ №18 ",
        "eventType": "other",
        "description": " Новая запись из Univer ",
        "reason": None,
        "actions": " Передано смене ",
        "performer": None,
        "errorCodes": None,
        "rotorLimit": None,
        "includeInReport": True,
    }
    values.update(overrides)
    return {"clientId": "draft:test-create", "values": values}


def test_event_create_edit_and_close(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    create_response = client.post("/events/new", data=_event_form(), follow_redirects=True)
    assert create_response.status_code == 200
    assert "Событие зарегистрировано" in create_response.get_data(as_text=True)
    assert "ВЭУ №17" in create_response.get_data(as_text=True)

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


def test_journal_v2_host_and_snapshot_contract(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    client.post("/events/new", data=_event_form())

    host_response = client.get("/events/v2")
    assert host_response.status_code == 200
    host_html = host_response.get_data(as_text=True)
    assert 'id="app"' in host_html
    assert "/static/univer-v2/journal-v2.css" in host_html
    assert "/static/univer-v2/journal-v2.js" in host_html
    assert "event_journal" not in host_html

    snapshot_response = client.get("/events/api/v2/snapshot")
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.get_json()
    assert snapshot["schemaVersion"] == 1
    assert isinstance(snapshot["generatedAt"], str)
    assert len(snapshot["records"]) == 1

    record = snapshot["records"][0]
    assert record["id"] == 1
    assert record["revision"] == 1
    assert record["startAt"] == "2026-07-26T18:10"
    assert record["endAt"] is None
    assert record["assetLabel"] == "ВЭУ №17"
    assert record["eventType"] == "rotor_limit"
    assert record["eventTypeLabel"] == "Ограничение по оборотам"
    assert record["description"] == "Установлено ограничение по оборотам"
    assert record["reason"] == "Повышенная вибрация"
    assert record["actions"] == "Информация передана сменному персоналу"
    assert record["performer"] == "Иванов И.И."
    assert record["errorCodes"] == "214"
    assert record["rotorLimit"] == "0.80"
    assert record["repairPowerMw"] == "1.00"
    assert record["status"] == "open"
    assert record["includeInReport"] is True


def test_journal_v2_create_record_persists_complete_draft(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    response = client.post("/events/api/v2/records", json=_v2_create_payload())

    assert response.status_code == 201
    body = response.get_json()
    assert body["schemaVersion"] == 1
    assert body["clientId"] == "draft:test-create"
    record = body["record"]
    assert record["id"] == 1
    assert record["revision"] == 1
    assert record["startAt"] == "2026-07-29T16:20"
    assert record["assetLabel"] == "ВЭУ №18"
    assert record["eventType"] == "other"
    assert record["eventTypeLabel"] == "Другое"
    assert record["description"] == "Новая запись из Univer"
    assert record["reason"] is None
    assert record["actions"] == "Передано смене"
    assert record["status"] == "open"
    assert record["includeInReport"] is True

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        event = session.scalar(select(Event))
        assert event is not None
        assert event.asset_label == "ВЭУ №18"
        assert event.description == "Новая запись из Univer"
        assert event.event_type == "other"
        assert event.revision == 1


def test_journal_v2_create_rejects_partial_or_forbidden_draft(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    partial = client.post(
        "/events/api/v2/records",
        json=_v2_create_payload(description="   "),
    )
    assert partial.status_code == 422
    assert partial.get_json()["error"]["code"] == "validation_error"

    forbidden_payload = _v2_create_payload()
    forbidden_payload["values"]["status"] = "closed"
    forbidden = client.post("/events/api/v2/records", json=forbidden_payload)
    assert forbidden.status_code == 422
    assert forbidden.get_json()["error"]["code"] == "validation_error"

    invalid_id = client.post(
        "/events/api/v2/records",
        json={"clientId": "", "values": _v2_create_payload()["values"]},
    )
    assert invalid_id.status_code == 400
    assert invalid_id.get_json()["error"]["code"] == "invalid_client_id"

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        assert session.scalar(select(Event)) is None


def test_journal_v2_patch_persists_and_recalculates(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    client.post("/events/new", data=_event_form())

    response = client.patch(
        "/events/api/v2/records/1",
        json={
            "revision": 1,
            "changes": {
                "description": "  Ограничение скорректировано  ",
                "reason": "  Новая причина  ",
                "rotorLimit": "0,90",
            },
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["schemaVersion"] == 1
    record = body["record"]
    assert record["revision"] == 2
    assert record["description"] == "Ограничение скорректировано"
    assert record["reason"] == "Новая причина"
    assert record["rotorLimit"] == "0.90"
    assert record["repairPowerMw"] == "0.55"

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        event = session.get(Event, 1)
        assert event is not None
        assert event.revision == 2
        assert event.description == "Ограничение скорректировано"
        assert event.reason == "Новая причина"
        assert str(event.rotor_limit) == "0.90"
        assert str(event.repair_power_mw) == "0.55"


def test_journal_v2_patch_rejects_stale_revision(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    client.post("/events/new", data=_event_form())

    accepted = client.patch(
        "/events/api/v2/records/1",
        json={"revision": 1, "changes": {"description": "Первая правка"}},
    )
    assert accepted.status_code == 200

    conflict = client.patch(
        "/events/api/v2/records/1",
        json={"revision": 1, "changes": {"description": "Устаревшая правка"}},
    )

    assert conflict.status_code == 409
    error = conflict.get_json()["error"]
    assert error["code"] == "revision_conflict"
    assert error["current"]["revision"] == 2
    assert error["current"]["description"] == "Первая правка"

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        event = session.get(Event, 1)
        assert event is not None
        assert event.description == "Первая правка"
        assert event.revision == 2


def test_journal_v2_patch_rejects_invalid_or_forbidden_change(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    client.post("/events/new", data=_event_form())

    invalid = client.patch(
        "/events/api/v2/records/1",
        json={"revision": 1, "changes": {"description": "   "}},
    )
    assert invalid.status_code == 422
    assert invalid.get_json()["error"]["code"] == "validation_error"

    forbidden = client.patch(
        "/events/api/v2/records/1",
        json={"revision": 1, "changes": {"status": "closed"}},
    )
    assert forbidden.status_code == 422
    assert forbidden.get_json()["error"]["code"] == "validation_error"

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        event = session.get(Event, 1)
        assert event is not None
        assert event.description == "Установлено ограничение по оборотам"
        assert event.status == "open"
        assert event.revision == 1


def test_invalid_rotor_limit_is_rejected(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    response = client.post("/events/new", data=_event_form(rotor_limit="1,20"))

    assert response.status_code == 200
    assert "не больше 1" in response.get_data(as_text=True)

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        assert session.scalar(select(Event)) is None
