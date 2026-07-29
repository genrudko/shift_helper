"""Request-scoped identity exposed to SQLite audit triggers."""

from __future__ import annotations

from contextvars import ContextVar, Token

_actor: ContextVar[str] = ContextVar("shift_helper_audit_actor", default="system")
_client_ip: ContextVar[str | None] = ContextVar(
    "shift_helper_audit_client_ip",
    default=None,
)


def current_audit_actor() -> str:
    return _actor.get()


def current_audit_client_ip() -> str | None:
    return _client_ip.get()


def bind_audit_context(actor: str, client_ip: str | None) -> tuple[Token[str], Token[str | None]]:
    return _actor.set(actor), _client_ip.set(client_ip)


def reset_audit_context(tokens: tuple[Token[str], Token[str | None]]) -> None:
    actor_token, client_ip_token = tokens
    _client_ip.reset(client_ip_token)
    _actor.reset(actor_token)
