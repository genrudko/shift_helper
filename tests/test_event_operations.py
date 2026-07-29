from pathlib import Path

from sqlalchemy.orm import Session

from shift_helper import create_app
from shift_helper.models import Event


def _event_form(asset: str, description: str) -> dict[str, str]:
    return {
        "start_at": "2026-07-29T20:00",
        "asset_label": asset,
        "event_type": "other",
        "description": description,
        "reason": "Исходная причина",
        "actions": "",
        "performer": "",
        "error_codes": "",
        "rotor_limit": "",
        "include_in_report": "on",
    }


def _operation_state(client) -> dict[str, object]:
    response = client.get("/events/api/v2/operations/state")
    assert response.status_code == 200
    return response.get_json()


def test_single_patch_can_be_undone_and_redone_persistently(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    assert client.post(
        "/events/new",
        data=_event_form("ВЭУ №50", "До изменения"),
    ).status_code == 302

    creation_state = _operation_state(client)
    assert creation_state["canUndo"] is False
    assert creation_state["undo"]["kind"] == "create"
    assert "необратимым барьером" in creation_state["undoReason"]

    patched = client.patch(
        "/events/api/v2/records/1",
        json={
            "revision": 1,
            "changes": {
                "description": "После изменения",
                "reason": "Новая причина",
            },
        },
    )
    assert patched.status_code == 200
    assert patched.get_json()["record"]["revision"] == 2

    state = _operation_state(client)
    assert state["canUndo"] is True
    assert state["canRedo"] is False
    assert state["undo"]["kind"] == "patch"
    assert state["undo"]["recordIds"] == [1]
    operation_id = state["undo"]["operationId"]

    undone = client.post(
        "/events/api/v2/operations/undo",
        json={"operationId": operation_id},
    )
    assert undone.status_code == 200
    assert undone.headers["X-Shift-Helper-Event-Mirror"] == "ok"
    assert undone.headers["X-Shift-Helper-Backup"] == "ok"
    record = undone.get_json()["records"][0]
    assert record["description"] == "До изменения"
    assert record["reason"] == "Исходная причина"
    assert record["revision"] == 3
    assert undone.get_json()["state"]["canRedo"] is True

    redone = client.post(
        "/events/api/v2/operations/redo",
        json={"operationId": operation_id},
    )
    assert redone.status_code == 200
    record = redone.get_json()["records"][0]
    assert record["description"] == "После изменения"
    assert record["reason"] == "Новая причина"
    assert record["revision"] == 4
    assert redone.get_json()["state"]["canUndo"] is True
    assert redone.get_json()["state"]["canRedo"] is False

    history = client.get("/events/api/v2/records/1/history").get_json()["entries"]
    assert [entry["action"] for entry in history] == [
        "create",
        "update",
        "update",
        "update",
    ]
    assert history[1]["operationId"] == operation_id
    assert history[2]["operationId"].startswith("history-undo:")
    assert history[3]["operationId"].startswith("history-redo:")


def test_batch_undo_and_redo_are_atomic_for_all_rows(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    client.post("/events/new", data=_event_form("ВЭУ №51", "Первая"))
    client.post("/events/new", data=_event_form("ВЭУ №52", "Вторая"))

    batch = client.post(
        "/events/api/v2/records/batch",
        json={
            "operations": [
                {
                    "recordId": 1,
                    "revision": 1,
                    "changes": {"description": "Первая пакетная"},
                },
                {
                    "recordId": 2,
                    "revision": 1,
                    "changes": {"description": "Вторая пакетная"},
                },
            ]
        },
    )
    assert batch.status_code == 200
    state = _operation_state(client)
    assert state["undo"]["kind"] == "batch"
    assert state["undo"]["recordIds"] == [1, 2]
    operation_id = state["undo"]["operationId"]

    undone = client.post(
        "/events/api/v2/operations/undo",
        json={"operationId": operation_id},
    )
    assert undone.status_code == 200
    assert [record["description"] for record in undone.get_json()["records"]] == [
        "Первая",
        "Вторая",
    ]
    assert [record["revision"] for record in undone.get_json()["records"]] == [3, 3]

    redone = client.post(
        "/events/api/v2/operations/redo",
        json={"operationId": operation_id},
    )
    assert redone.status_code == 200
    assert [record["description"] for record in redone.get_json()["records"]] == [
        "Первая пакетная",
        "Вторая пакетная",
    ]
    assert [record["revision"] for record in redone.get_json()["records"]] == [4, 4]


def test_new_edit_after_undo_discards_redo_branch(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    client.post("/events/new", data=_event_form("ВЭУ №53", "Исходное"))
    client.patch(
        "/events/api/v2/records/1",
        json={"revision": 1, "changes": {"description": "Первая ветка"}},
    )
    operation_id = _operation_state(client)["undo"]["operationId"]
    assert client.post(
        "/events/api/v2/operations/undo",
        json={"operationId": operation_id},
    ).status_code == 200
    assert _operation_state(client)["canRedo"] is True

    replacement = client.patch(
        "/events/api/v2/records/1",
        json={"revision": 3, "changes": {"description": "Новая ветка"}},
    )
    assert replacement.status_code == 200
    state = _operation_state(client)
    assert state["canRedo"] is False
    assert state["canUndo"] is True
    assert state["undo"]["operationId"] != operation_id

    stale_redo = client.post(
        "/events/api/v2/operations/redo",
        json={"operationId": operation_id},
    )
    assert stale_redo.status_code == 409


def test_untracked_concurrent_change_blocks_undo(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    client.post("/events/new", data=_event_form("ВЭУ №54", "Исходное"))
    client.patch(
        "/events/api/v2/records/1",
        json={"revision": 1, "changes": {"description": "Отслеживаемое"}},
    )
    operation_id = _operation_state(client)["undo"]["operationId"]

    engine = app.extensions["shift_helper_database_engine"]
    with Session(engine) as session:
        event = session.get(Event, 1)
        assert event is not None
        event.description = "Внешнее изменение"
        event.revision += 1
        session.commit()

    conflict = client.post(
        "/events/api/v2/operations/undo",
        json={"operationId": operation_id},
    )
    assert conflict.status_code == 409
    assert conflict.get_json()["error"]["code"] == "operation_conflict"
    assert conflict.get_json()["error"]["current"]["description"] == "Внешнее изменение"

    with Session(engine) as session:
        event = session.get(Event, 1)
        assert event is not None
        assert event.description == "Внешнее изменение"
        assert event.revision == 3


def test_close_is_an_explicit_undo_barrier(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    client.post("/events/new", data=_event_form("ВЭУ №55", "Исходное"))
    client.patch(
        "/events/api/v2/records/1",
        json={"revision": 1, "changes": {"description": "Изменённое"}},
    )
    closed = client.post(
        "/events/api/v2/records/1/close",
        json={"revision": 2},
    )
    assert closed.status_code == 200

    state = _operation_state(client)
    assert state["canUndo"] is False
    assert state["undo"]["kind"] == "close"
    assert "необратимым барьером" in state["undoReason"]
