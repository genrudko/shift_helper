"""Request-scoped identity and operation metadata exposed to SQLite triggers."""

from __future__ import annotations

from contextvars import ContextVar, Token

_actor: ContextVar[str] = ContextVar("shift_helper_audit_actor", default="system")
_client_ip: ContextVar[str | None] = ContextVar(
    "shift_helper_audit_client_ip",
    default=None,
)
_operation_id: ContextVar[str | None] = ContextVar(
    "shift_helper_operation_id",
    default=None,
)
_operation_kind: ContextVar[str] = ContextVar(
    "shift_helper_operation_kind",
    default="system",
)
_operation_reversible: ContextVar[int] = ContextVar(
    "shift_helper_operation_reversible",
    default=0,
)
_operation_track: ContextVar[int] = ContextVar(
    "shift_helper_operation_track",
    default=0,
)

AuditContextTokens = tuple[
    Token[str],
    Token[str | None],
    Token[str | None],
    Token[str],
    Token[int],
    Token[int],
]


def current_audit_actor() -> str:
    return _actor.get()


def current_audit_client_ip() -> str | None:
    return _client_ip.get()


def current_operation_id() -> str | None:
    return _operation_id.get()


def current_operation_kind() -> str:
    return _operation_kind.get()


def current_operation_reversible() -> int:
    return _operation_reversible.get()


def current_operation_track() -> int:
    return _operation_track.get()


def bind_audit_context(
    actor: str,
    client_ip: str | None,
    *,
    operation_id: str | None = None,
    operation_kind: str = "request",
    operation_reversible: bool = False,
    operation_track: bool = False,
) -> AuditContextTokens:
    return (
        _actor.set(actor),
        _client_ip.set(client_ip),
        _operation_id.set(operation_id),
        _operation_kind.set(operation_kind),
        _operation_reversible.set(1 if operation_reversible else 0),
        _operation_track.set(1 if operation_track else 0),
    )


def reset_audit_context(tokens: AuditContextTokens) -> None:
    (
        actor_token,
        client_ip_token,
        operation_id_token,
        operation_kind_token,
        operation_reversible_token,
        operation_track_token,
    ) = tokens
    _operation_track.reset(operation_track_token)
    _operation_reversible.reset(operation_reversible_token)
    _operation_kind.reset(operation_kind_token)
    _operation_id.reset(operation_id_token)
    _client_ip.reset(client_ip_token)
    _actor.reset(actor_token)
