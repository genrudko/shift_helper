"""Explicit authentication boundary for optional manual LAN mode."""

from __future__ import annotations

import hmac
import ipaddress
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from flask import (
    Flask,
    Response,
    g,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)

from .audit_context import bind_audit_context, reset_audit_context

MINIMUM_LAN_TOKEN_LENGTH = 16
LAN_TOKEN_HEADER = "X-Shift-Helper-LAN-Token"
_LOGIN_TEMPLATE = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Доступ к Shift-Helper</title>
  <style>
    body { font-family: "Segoe UI", sans-serif; background: #f4f6f8; color: #182230; }
    main { max-width: 420px; margin: 10vh auto; padding: 24px; background: white;
      border: 1px solid #d8dee8; border-radius: 10px; }
    label { display: grid; gap: 6px; margin: 14px 0; }
    input, button { box-sizing: border-box; width: 100%; min-height: 40px;
      padding: 8px 10px; font: inherit; }
    button { border: 0; border-radius: 6px; background: #2563eb; color: white;
      font-weight: 600; cursor: pointer; }
    .error { color: #b42318; font-weight: 600; }
  </style>
</head>
<body>
  <main>
    <h1>Shift-Helper</h1>
    <p>Введите токен локальной сети, выданный оператором приложения.</p>
    {% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}
    <form method="post">
      <input type="hidden" name="next" value="{{ next_path }}">
      <label>Имя рабочего места
        <input name="client_name" maxlength="80" autocomplete="organization-title" required>
      </label>
      <label>Токен доступа
        <input name="token" type="password" autocomplete="current-password" required>
      </label>
      <button type="submit">Открыть журнал</button>
    </form>
  </main>
</body>
</html>
"""

_OPERATION_ENDPOINTS: dict[str, tuple[str, bool, bool]] = {
    "events.journal_v2_create_record": ("create", False, True),
    "events.journal_v2_patch_record": ("patch", True, True),
    "events.journal_v2_close_record": ("close", False, True),
    "events.create_event": ("create", False, True),
    "events.edit_event": ("edit", True, True),
    "events.close_event": ("close", False, True),
    "event_batch.patch_records_batch": ("batch", True, True),
    "event_operations.undo_operation": ("history-undo", False, False),
    "event_operations.redo_operation": ("history-redo", False, False),
}


def is_loopback_address(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().strip("[]")
    if normalized.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    mapped = getattr(address, "ipv4_mapped", None)
    return bool(mapped and mapped.is_loopback)


def is_loopback_bind_host(host: str) -> bool:
    return is_loopback_address(host)


def load_or_create_session_secret(root: Path) -> str:
    """Persist a random user-owned Flask signing secret without administrator rights."""

    path = root / ".session-secret"
    if path.is_file():
        secret = path.read_text(encoding="ascii").strip()
        if len(secret) >= 64:
            return secret

    root.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_hex(32)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        existing = path.read_text(encoding="ascii").strip()
        if len(existing) < 64:
            raise RuntimeError("Файл session secret повреждён.") from exc
        return existing
    with os.fdopen(descriptor, "w", encoding="ascii") as target:
        target.write(secret + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return secret


def _safe_next_path(value: str | None) -> str:
    if not value:
        return "/events/v2"
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return "/events/v2"
    return parsed.path + (("?" + parsed.query) if parsed.query else "")


def _request_operation_metadata() -> tuple[str | None, str, bool, bool]:
    endpoint = request.endpoint or ""
    metadata = _OPERATION_ENDPOINTS.get(endpoint)
    if metadata is None or request.method not in {"POST", "PATCH", "PUT", "DELETE"}:
        return None, "request", False, False
    operation_kind, reversible, track = metadata
    operation_id = f"{operation_kind}:{uuid4().hex}"
    return operation_id, operation_kind, reversible, track


def configure_lan_security(app: Flask, *, enabled: bool, token: str | None) -> None:
    """Require an authenticated session for every non-loopback LAN request."""

    if enabled and (not token or len(token) < MINIMUM_LAN_TOKEN_LENGTH):
        raise ValueError(
            f"LAN-токен должен содержать не менее {MINIMUM_LAN_TOKEN_LENGTH} символов."
        )
    expected_token = token or ""
    app.extensions["shift_helper_lan"] = {"enabled": enabled}

    @app.before_request
    def authorize_and_bind_audit_context() -> Response | tuple[Response, int] | None:
        remote_ip = request.remote_addr
        loopback = is_loopback_address(remote_ip)
        login_request = request.endpoint == "lan_login"
        session_authenticated = bool(session.get("lan_authenticated"))
        supplied_header = request.headers.get(LAN_TOKEN_HEADER, "")
        header_authenticated = bool(
            enabled
            and supplied_header
            and hmac.compare_digest(supplied_header, expected_token)
        )
        authenticated = session_authenticated or header_authenticated

        if enabled and not loopback and not authenticated and not login_request:
            if request.path.startswith("/events/api/") or request.path == "/health":
                return (
                    jsonify(
                        {
                            "error": {
                                "code": "lan_authentication_required",
                                "message": "Требуется авторизация рабочего места.",
                            }
                        }
                    ),
                    401,
                )
            return redirect(url_for("lan_login", next=request.full_path))

        if loopback or not enabled:
            actor = "local"
            audit_ip = remote_ip
        elif header_authenticated and not session_authenticated:
            actor = "lan:token-header"
            audit_ip = remote_ip
        elif session_authenticated:
            client_id = str(session.get("lan_client_id", "unknown"))
            client_name = str(session.get("lan_client_name", "Рабочее место"))
            actor = f"lan:{client_name}:{client_id}"
            audit_ip = remote_ip
        else:
            actor = "lan-login"
            audit_ip = remote_ip

        operation_id, operation_kind, reversible, track = _request_operation_metadata()
        g.shift_helper_audit_tokens = bind_audit_context(
            actor,
            audit_ip,
            operation_id=operation_id,
            operation_kind=operation_kind,
            operation_reversible=reversible,
            operation_track=track,
        )
        return None

    @app.teardown_request
    def release_audit_context(_error: BaseException | None) -> None:
        tokens = g.pop("shift_helper_audit_tokens", None)
        if tokens is not None:
            reset_audit_context(tokens)

    @app.route("/lan/login", methods=["GET", "POST"])
    def lan_login() -> str | tuple[str, int] | Response:
        next_path = _safe_next_path(request.values.get("next"))
        if request.method == "POST":
            supplied_token = request.form.get("token", "")
            client_name = " ".join(request.form.get("client_name", "").split())[:80]
            if not hmac.compare_digest(supplied_token, expected_token):
                return (
                    render_template_string(
                        _LOGIN_TEMPLATE,
                        error="Неверный токен доступа.",
                        next_path=next_path,
                    ),
                    403,
                )
            if not client_name:
                return (
                    render_template_string(
                        _LOGIN_TEMPLATE,
                        error="Укажите имя рабочего места.",
                        next_path=next_path,
                    ),
                    422,
                )
            session.clear()
            session["lan_authenticated"] = True
            session["lan_client_id"] = secrets.token_hex(8)
            session["lan_client_name"] = client_name
            return redirect(next_path)

        return render_template_string(
            _LOGIN_TEMPLATE,
            error=None,
            next_path=next_path,
        )

    @app.post("/lan/logout")
    def lan_logout() -> Response:
        session.clear()
        return redirect(url_for("lan_login"))
