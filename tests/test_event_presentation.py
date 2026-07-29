from pathlib import Path

from sqlalchemy import text

from shift_helper import create_app


def _presentation() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "workbookStyles": {
            "operator-bold": {
                "bl": 1,
                "bg": {"rgb": "#FFF3BF"},
            }
        },
        "sheet": {
            "zoomRatio": 1.25,
            "freeze": {
                "startRow": 1,
                "startColumn": 2,
                "ySplit": 1,
                "xSplit": 2,
            },
            "columnData": {
                "3": {"w": 210.0, "hd": 0},
                "5": {"w": 360.0, "hd": 0},
            },
            "rowData": {
                "1": {"h": 44.0, "hd": 0},
            },
            "cellStyles": {
                "1": {"5": "operator-bold"},
            },
        },
    }


def test_presentation_state_is_separate_from_event_data(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    backups = tmp_path / "backups"
    mirror = tmp_path / "exports" / "Журнал событий.xlsx"
    initial_backups = sorted(backups.glob("shift_helper-*.sqlite3"))
    initial_mirror_mtime = mirror.stat().st_mtime_ns

    empty = client.get("/events/api/v2/presentation")
    assert empty.status_code == 200
    assert empty.get_json()["revision"] == 0
    assert empty.get_json()["presentation"]["schemaVersion"] == 1

    saved = client.put(
        "/events/api/v2/presentation",
        json={"revision": 0, "presentation": _presentation()},
    )
    assert saved.status_code == 200
    assert saved.headers["X-Shift-Helper-Event-Mirror"] == "ok"
    assert saved.headers["X-Shift-Helper-Backup"] == "ok"
    body = saved.get_json()
    assert body["revision"] == 1
    assert body["presentation"] == _presentation()

    loaded = client.get("/events/api/v2/presentation").get_json()
    assert loaded == body
    assert sorted(backups.glob("shift_helper-*.sqlite3")) == initial_backups
    assert mirror.stat().st_mtime_ns == initial_mirror_mtime

    engine = app.extensions["shift_helper_database_engine"]
    with engine.connect() as connection:
        assert connection.scalar(
            text("SELECT value FROM app_metadata WHERE key = 'schema_version'")
        ) == "5"
        assert connection.scalar(text("SELECT COUNT(*) FROM events")) == 0
        assert connection.scalar(text("SELECT COUNT(*) FROM journal_presentation")) == 1


def test_presentation_uses_optimistic_revision(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    accepted = client.put(
        "/events/api/v2/presentation",
        json={"revision": 0, "presentation": _presentation()},
    )
    assert accepted.status_code == 200

    stale_payload = _presentation()
    stale_payload["sheet"]["zoomRatio"] = 1.5  # type: ignore[index]
    conflict = client.put(
        "/events/api/v2/presentation",
        json={"revision": 0, "presentation": stale_payload},
    )
    assert conflict.status_code == 409
    error = conflict.get_json()["error"]
    assert error["code"] == "revision_conflict"
    assert error["current"]["revision"] == 1
    assert error["current"]["presentation"] == _presentation()


def test_presentation_rejects_cell_values_and_formulas(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    invalid = _presentation()
    invalid["sheet"]["cellStyles"] = {  # type: ignore[index]
        "1": {"5": {"bl": 1, "v": "Запрещённое значение"}}
    }

    response = client.put(
        "/events/api/v2/presentation",
        json={"revision": 0, "presentation": invalid},
    )
    assert response.status_code == 422
    error = response.get_json()["error"]
    assert error["code"] == "validation_error"
    assert "значения ячеек" in error["message"]

    assert client.get("/events/api/v2/presentation").get_json()["revision"] == 0


def test_identical_presentation_is_a_noop(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()
    first = client.put(
        "/events/api/v2/presentation",
        json={"revision": 0, "presentation": _presentation()},
    ).get_json()
    repeated = client.put(
        "/events/api/v2/presentation",
        json={"revision": 1, "presentation": _presentation()},
    ).get_json()

    assert first["revision"] == repeated["revision"] == 1
    assert first["updatedAt"] == repeated["updatedAt"]
