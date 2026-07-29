from pathlib import Path

from sqlalchemy.orm import Session

from shift_helper import create_app
from shift_helper.models import Event


def _event_form(asset: str, description: str) -> dict[str, str]:
    return {
        "start_at": "2026-07-29T16:00",
        "asset_label": asset,
        "event_type": "other",
        "description": description,
        "reason": "",
        "actions": "",
        "performer": "",
        "error_codes": "",
        "rotor_limit": "",
        "include_in_report": "on",
    }


def _seed_two(client) -> None:
    assert client.post("/events/new", data=_event_form("ВЭУ №1", "Первая")).status_code == 302
    assert client.post("/events/new", data=_event_form("ВЭУ №2", "Вторая")).status_code == 302


def test_batch_patch_updates_multiple_records_atomically(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    _seed_two(client)

    response = client.post(
        "/events/api/v2/records/batch",
        json={
            "operations": [
                {
                    "recordId": 1,
                    "revision": 1,
                    "changes": {
                        "description": "Первая пакетная",
                        "actions": "Действие 1",
                    },
                },
                {
                    "recordId": 2,
                    "revision": 1,
                    "changes": {
                        "description": "Вторая пакетная",
                        "actions": "Действие 2",
                    },
                },
            ]
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Shift-Helper-Event-Mirror"] == "ok"
    body = response.get_json()
    assert body["schemaVersion"] == 1
    assert [record["id"] for record in body["records"]] == [1, 2]
    assert [record["revision"] for record in body["records"]] == [2, 2]
    assert [record["description"] for record in body["records"]] == [
        "Первая пакетная",
        "Вторая пакетная",
    ]

    history_one = client.get("/events/api/v2/records/1/history").get_json()["entries"]
    history_two = client.get("/events/api/v2/records/2/history").get_json()["entries"]
    assert [entry["action"] for entry in history_one] == ["create", "update"]
    assert [entry["action"] for entry in history_two] == ["create", "update"]


def test_batch_validation_failure_rolls_back_every_record(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    _seed_two(client)

    response = client.post(
        "/events/api/v2/records/batch",
        json={
            "operations": [
                {
                    "recordId": 1,
                    "revision": 1,
                    "changes": {"description": "Не должно сохраниться"},
                },
                {
                    "recordId": 2,
                    "revision": 1,
                    "changes": {"description": "   "},
                },
            ]
        },
    )

    assert response.status_code == 422
    error = response.get_json()["error"]
    assert error["code"] == "validation_error"
    assert error["operationIndex"] == 1
    assert error["recordId"] == 2

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        first = session.get(Event, 1)
        second = session.get(Event, 2)
        assert first is not None and second is not None
        assert first.description == "Первая"
        assert second.description == "Вторая"
        assert first.revision == 1
        assert second.revision == 1


def test_batch_revision_conflict_rolls_back_every_record(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    _seed_two(client)

    accepted = client.patch(
        "/events/api/v2/records/2",
        json={"revision": 1, "changes": {"reason": "Конкурентное изменение"}},
    )
    assert accepted.status_code == 200

    response = client.post(
        "/events/api/v2/records/batch",
        json={
            "operations": [
                {
                    "recordId": 1,
                    "revision": 1,
                    "changes": {"description": "Не должно сохраниться"},
                },
                {
                    "recordId": 2,
                    "revision": 1,
                    "changes": {"description": "Устаревшее значение"},
                },
            ]
        },
    )

    assert response.status_code == 409
    error = response.get_json()["error"]
    assert error["code"] == "revision_conflict"
    assert error["operationIndex"] == 1
    assert error["recordId"] == 2
    assert error["current"]["revision"] == 2

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        first = session.get(Event, 1)
        second = session.get(Event, 2)
        assert first is not None and second is not None
        assert first.description == "Первая"
        assert first.revision == 1
        assert second.description == "Вторая"
        assert second.reason == "Конкурентное изменение"
        assert second.revision == 2


def test_batch_rejects_duplicate_record_operations(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    _seed_two(client)

    response = client.post(
        "/events/api/v2/records/batch",
        json={
            "operations": [
                {
                    "recordId": 1,
                    "revision": 1,
                    "changes": {"description": "Первая правка"},
                },
                {
                    "recordId": 1,
                    "revision": 1,
                    "changes": {"reason": "Вторая правка"},
                },
            ]
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "duplicate_record"
