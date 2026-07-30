from pathlib import Path

from shift_helper import create_app
from shift_helper.launcher import (
    application_url,
    primary_application_url,
)


def test_primary_user_routes_resolve_only_to_univer(tmp_path: Path) -> None:
    app = create_app(testing=True, data_root=tmp_path)
    client = app.test_client()

    for legacy_path in ("/", "/events", "/events/new", "/events/999/edit"):
        response = client.get(legacy_path, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/events/v2")

    primary = client.get("/", follow_redirects=True)
    assert primary.status_code == 200
    assert primary.request.path == "/events/v2"
    html = primary.get_data(as_text=True)
    assert 'id="app"' in html
    assert "/static/univer-v2/journal-v2.css" in html
    assert "/static/univer-v2/journal-v2.js" in html
    assert "Создать событие" not in html
    assert "Новое событие" not in html


def test_launcher_primary_url_points_to_univer_runtime() -> None:
    assert application_url("127.0.0.1", 17843) == "http://127.0.0.1:17843"
    assert primary_application_url("127.0.0.1", 17843) == (
        "http://127.0.0.1:17843/events/v2"
    )
    assert primary_application_url("::1", 17843) == "http://[::1]:17843/events/v2"
