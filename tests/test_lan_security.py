from pathlib import Path

import pytest

from shift_helper import create_app
from shift_helper.launcher import application_url, browser_host
from shift_helper.security import is_loopback_address, is_loopback_bind_host

LAN_TOKEN = "shift-helper-test-token-2026"
REMOTE = {"REMOTE_ADDR": "192.168.10.44"}


def _event_form(description: str) -> dict[str, str]:
    return {
        "start_at": "2026-07-29T18:10",
        "asset_label": "ВЭУ №31",
        "event_type": "other",
        "description": description,
        "reason": "",
        "actions": "",
        "performer": "",
        "error_codes": "",
        "rotor_limit": "",
        "include_in_report": "on",
    }


def test_lan_mode_requires_authentication_for_non_loopback_requests(tmp_path: Path) -> None:
    app = create_app(
        testing=True,
        data_root=tmp_path,
        lan_mode=True,
        lan_token=LAN_TOKEN,
    )
    client = app.test_client()

    root = client.get("/", environ_overrides=REMOTE)
    assert root.status_code == 302
    assert "/lan/login" in root.headers["Location"]

    api = client.get("/events/api/v2/snapshot", environ_overrides=REMOTE)
    assert api.status_code == 401
    assert api.get_json()["error"]["code"] == "lan_authentication_required"

    health = client.get("/health", environ_overrides=REMOTE)
    assert health.status_code == 401

    login_page = client.get("/lan/login", environ_overrides=REMOTE)
    assert login_page.status_code == 200
    assert "Токен доступа" in login_page.get_data(as_text=True)

    rejected = client.post(
        "/lan/login",
        data={"token": "wrong-token", "client_name": "АРМ-1"},
        environ_overrides=REMOTE,
    )
    assert rejected.status_code == 403
    assert "Неверный токен" in rejected.get_data(as_text=True)


def test_authenticated_lan_session_is_recorded_in_immutable_audit(tmp_path: Path) -> None:
    app = create_app(
        testing=True,
        data_root=tmp_path,
        lan_mode=True,
        lan_token=LAN_TOKEN,
    )
    client = app.test_client()

    login = client.post(
        "/lan/login",
        data={
            "token": LAN_TOKEN,
            "client_name": "АРМ начальника смены",
            "next": "/events/v2",
        },
        environ_overrides=REMOTE,
    )
    assert login.status_code == 302
    assert login.headers["Location"].endswith("/events/v2")

    created = client.post(
        "/events/new",
        data=_event_form("LAN-событие"),
        environ_overrides=REMOTE,
    )
    assert created.status_code == 302
    assert created.headers["X-Shift-Helper-Backup"] == "ok"

    history = client.get(
        "/events/api/v2/records/1/history",
        environ_overrides=REMOTE,
    )
    assert history.status_code == 200
    entry = history.get_json()["entries"][0]
    assert entry["action"] == "create"
    assert entry["actor"].startswith("lan:АРМ начальника смены:")
    assert entry["clientIp"] == "192.168.10.44"


def test_lan_header_token_supports_controlled_api_clients(tmp_path: Path) -> None:
    app = create_app(
        testing=True,
        data_root=tmp_path,
        lan_mode=True,
        lan_token=LAN_TOKEN,
    )
    client = app.test_client()
    headers = {"X-Shift-Helper-LAN-Token": LAN_TOKEN}

    health = client.get("/health", headers=headers, environ_overrides=REMOTE)
    assert health.status_code == 200
    assert health.get_json()["lanMode"] == {"enabled": True}

    created = client.post(
        "/events/new",
        data=_event_form("Событие API-клиента"),
        headers=headers,
        environ_overrides=REMOTE,
    )
    assert created.status_code == 302

    history = client.get(
        "/events/api/v2/records/1/history",
        headers=headers,
        environ_overrides=REMOTE,
    )
    entry = history.get_json()["entries"][0]
    assert entry["actor"] == "lan:token-header"
    assert entry["clientIp"] == "192.168.10.44"


def test_loopback_remains_passwordless_and_has_local_actor(tmp_path: Path) -> None:
    app = create_app(
        testing=True,
        data_root=tmp_path,
        lan_mode=True,
        lan_token=LAN_TOKEN,
    )
    client = app.test_client()

    health = client.get("/health", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
    assert health.status_code == 200

    created = client.post(
        "/events/new",
        data=_event_form("Локальное событие"),
        environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert created.status_code == 302
    history = client.get(
        "/events/api/v2/records/1/history",
        environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
    ).get_json()
    assert history["entries"][0]["actor"] == "local"
    assert history["entries"][0]["clientIp"] == "127.0.0.1"


def test_session_secret_persists_and_lan_token_policy_is_fail_closed(tmp_path: Path) -> None:
    first = create_app(testing=True, data_root=tmp_path)
    first_secret = first.config["SECRET_KEY"]
    second = create_app(testing=True, data_root=tmp_path)
    assert second.config["SECRET_KEY"] == first_secret
    assert len(first_secret) >= 64
    assert (tmp_path / ".session-secret").read_text(encoding="ascii").strip() == first_secret

    with pytest.raises(ValueError, match="не менее 16"):
        create_app(
            testing=True,
            data_root=tmp_path / "invalid",
            lan_mode=True,
            lan_token="short",
        )


def test_launcher_network_helpers_are_explicit() -> None:
    assert application_url("127.0.0.1", 17843) == "http://127.0.0.1:17843"
    assert application_url("::1", 17843) == "http://[::1]:17843"
    assert browser_host("0.0.0.0") == "127.0.0.1"
    assert browser_host("::") == "::1"
    assert is_loopback_address("::ffff:127.0.0.1")
    assert is_loopback_bind_host("localhost")
    assert not is_loopback_bind_host("0.0.0.0")
    assert not is_loopback_bind_host("192.168.10.5")
