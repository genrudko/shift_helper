from pathlib import Path

from shift_helper import create_app


def test_health_and_runtime_database(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.get_json()["status"] == "ok"

    index_response = client.get("/")
    assert index_response.status_code == 200
    assert b"Shift-Helper" in index_response.data

    assert (tmp_path / "data" / "shift_helper.sqlite3").is_file()
    assert (tmp_path / "exports").is_dir()
    assert (tmp_path / "backups").is_dir()
    assert (tmp_path / "imports").is_dir()
    assert (tmp_path / "logs").is_dir()
