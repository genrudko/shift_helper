"""HTTP routes for the operational event journal."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .domain import (
    EVENT_TYPE_CHOICES,
    EventValidationError,
    event_values_for_form,
    event_values_from_form,
)
from .models import Event

events_blueprint = Blueprint("events", __name__, url_prefix="/events")
EVENT_TYPE_LABELS = dict(EVENT_TYPE_CHOICES)

# Plain spreadsheet cells and the compact row editor share one optimistic PATCH
# contract. Status/end time still change only through an explicit transition.
V2_PATCH_FIELDS: dict[str, str] = {
    "startAt": "start_at",
    "assetLabel": "asset_label",
    "eventType": "event_type",
    "description": "description",
    "reason": "reason",
    "actions": "actions",
    "performer": "performer",
    "errorCodes": "error_codes",
    "rotorLimit": "rotor_limit",
    "includeInReport": "include_in_report",
}
V2_NULLABLE_PATCH_FIELDS = {"reason", "actions", "performer", "errorCodes", "rotorLimit"}

# New rows use the same domain validator as the classic form. The browser sends
# explicit defaults for start time, event type and report inclusion; the API
# does not create partial records from an unfinished spreadsheet row.
V2_CREATE_FIELDS: dict[str, str] = {
    "startAt": "start_at",
    "assetLabel": "asset_label",
    "eventType": "event_type",
    "description": "description",
    "reason": "reason",
    "actions": "actions",
    "performer": "performer",
    "errorCodes": "error_codes",
    "rotorLimit": "rotor_limit",
    "includeInReport": "include_in_report",
}
V2_NULLABLE_CREATE_FIELDS = {"reason", "actions", "performer", "errorCodes", "rotorLimit"}


def _database_engine() -> Engine:
    return current_app.extensions["shift_helper_database_engine"]


def _get_event_or_404(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        abort(404)
    return event


def _event_snapshot(event: Event) -> dict[str, object]:
    return {
        "id": event.id,
        "revision": event.revision,
        "startAt": event.start_at.isoformat(timespec="minutes"),
        "endAt": event.end_at.isoformat(timespec="minutes") if event.end_at else None,
        "assetLabel": event.asset_label,
        "eventType": event.event_type,
        "eventTypeLabel": EVENT_TYPE_LABELS.get(event.event_type, event.event_type),
        "description": event.description,
        "reason": event.reason,
        "actions": event.actions,
        "performer": event.performer,
        "errorCodes": event.error_codes,
        "rotorLimit": str(event.rotor_limit) if event.rotor_limit is not None else None,
        "repairPowerMw": (
            str(event.repair_power_mw) if event.repair_power_mw is not None else None
        ),
        "status": event.status,
        "includeInReport": event.include_in_report,
    }


def _api_error(code: str, message: str, *, status: int, **details: object) -> tuple[Response, int]:
    return jsonify({"error": {"code": code, "message": message, **details}}), status


def _valid_expected_revision(payload: Mapping[str, Any]) -> int | None:
    revision = payload.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        return None
    return revision


def _v2_patch_form_values(event: Event, changes: Mapping[str, Any]) -> dict[str, str]:
    values = event_values_for_form(event)

    for api_field, raw_value in changes.items():
        model_field = V2_PATCH_FIELDS.get(api_field)
        if model_field is None:
            raise EventValidationError(f"Поле «{api_field}» нельзя изменять через Journal UI V2.")

        if api_field == "includeInReport":
            if not isinstance(raw_value, bool):
                raise EventValidationError(
                    "Поле «includeInReport» должно содержать логическое значение."
                )
            values[model_field] = "on" if raw_value else ""
        elif raw_value is None and api_field in V2_NULLABLE_PATCH_FIELDS:
            values[model_field] = ""
        elif isinstance(raw_value, str):
            values[model_field] = raw_value
        else:
            raise EventValidationError(f"Поле «{api_field}» должно содержать текст.")

    return values


def _v2_create_form_values(values: Mapping[str, Any]) -> dict[str, str]:
    form_values = {
        "start_at": "",
        "asset_label": "",
        "event_type": "",
        "description": "",
        "reason": "",
        "actions": "",
        "performer": "",
        "error_codes": "",
        "rotor_limit": "",
        "include_in_report": "",
    }

    for api_field, raw_value in values.items():
        model_field = V2_CREATE_FIELDS.get(api_field)
        if model_field is None:
            raise EventValidationError(f"Поле «{api_field}» нельзя передавать при создании записи.")

        if api_field == "includeInReport":
            if not isinstance(raw_value, bool):
                raise EventValidationError(
                    "Поле «includeInReport» должно содержать логическое значение."
                )
            form_values[model_field] = "on" if raw_value else ""
        elif raw_value is None and api_field in V2_NULLABLE_CREATE_FIELDS:
            form_values[model_field] = ""
        elif isinstance(raw_value, str):
            form_values[model_field] = raw_value
        else:
            raise EventValidationError(f"Поле «{api_field}» должно содержать текст.")

    return form_values


@events_blueprint.get("")
def list_events() -> str:
    status = request.args.get("status", "all")
    if status not in {"all", "open", "closed"}:
        status = "all"

    statement = select(Event).order_by(Event.start_at.desc(), Event.id.desc())
    if status != "all":
        statement = statement.where(Event.status == status)

    with Session(_database_engine()) as session:
        events = list(session.scalars(statement))

    return render_template(
        "events/list.html",
        events=events,
        selected_status=status,
        event_type_labels=EVENT_TYPE_LABELS,
    )


@events_blueprint.get("/v2")
def journal_v2() -> str:
    """Render the clean Univer Sheets frontend host."""

    return render_template("events/univer_v2.html")


@events_blueprint.get("/api/v2/snapshot")
def journal_v2_snapshot() -> Response:
    """Return the stable snapshot contract used by Journal UI V2."""

    statement = select(Event).order_by(Event.start_at.asc(), Event.id.asc())
    with Session(_database_engine()) as session:
        records = [_event_snapshot(event) for event in session.scalars(statement)]

    return jsonify(
        {
            "schemaVersion": 1,
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "eventTypes": [
                {"value": event_type, "label": label}
                for event_type, label in EVENT_TYPE_CHOICES
            ],
            "records": records,
        }
    )


@events_blueprint.post("/api/v2/records")
def journal_v2_create_record() -> tuple[Response, int]:
    """Create one complete event from the first Univer draft row."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _api_error("invalid_json", "Ожидался JSON-объект.", status=400)

    client_id = payload.get("clientId")
    values = payload.get("values")
    if not isinstance(client_id, str) or not client_id.strip() or len(client_id) > 128:
        return _api_error(
            "invalid_client_id",
            "Укажите корректный временный идентификатор строки.",
            status=400,
        )
    if not isinstance(values, dict):
        return _api_error("invalid_values", "Не переданы значения новой записи.", status=400)

    try:
        normalized = event_values_from_form(_v2_create_form_values(values))
    except EventValidationError as exc:
        return _api_error("validation_error", str(exc), status=422)

    with Session(_database_engine()) as session:
        event = Event(**normalized)
        session.add(event)
        session.commit()
        session.refresh(event)
        return (
            jsonify(
                {
                    "schemaVersion": 1,
                    "clientId": client_id,
                    "record": _event_snapshot(event),
                }
            ),
            201,
        )


@events_blueprint.patch("/api/v2/records/<int:event_id>")
def journal_v2_patch_record(event_id: int) -> tuple[Response, int] | Response:
    """Persist one optimistic-concurrency patch from the Univer journal."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _api_error("invalid_json", "Ожидался JSON-объект.", status=400)

    expected_revision = _valid_expected_revision(payload)
    changes = payload.get("changes")
    if expected_revision is None:
        return _api_error("invalid_revision", "Укажите корректную ревизию записи.", status=400)
    if not isinstance(changes, dict) or not changes:
        return _api_error("invalid_changes", "Не переданы изменения записи.", status=400)

    with Session(_database_engine()) as session:
        event = session.get(Event, event_id)
        if event is None:
            return _api_error("not_found", "Запись журнала не найдена.", status=404)

        if event.revision != expected_revision:
            return _api_error(
                "revision_conflict",
                "Запись уже изменена в другом окне. Обновите строку перед повторным сохранением.",
                status=409,
                current=_event_snapshot(event),
            )

        try:
            normalized = event_values_from_form(_v2_patch_form_values(event, changes))
        except EventValidationError as exc:
            return _api_error("validation_error", str(exc), status=422)

        update_values: dict[str, object] = {
            V2_PATCH_FIELDS[api_field]: normalized[V2_PATCH_FIELDS[api_field]]
            for api_field in changes
            if api_field in V2_PATCH_FIELDS
        }
        if "rotorLimit" in changes:
            update_values["repair_power_mw"] = normalized["repair_power_mw"]
        update_values["updated_at"] = datetime.now()
        update_values["revision"] = Event.revision + 1

        result = session.execute(
            update(Event)
            .where(Event.id == event_id, Event.revision == expected_revision)
            .values(**update_values)
        )
        if result.rowcount != 1:
            session.rollback()
            current = session.get(Event, event_id)
            if current is None:
                return _api_error("not_found", "Запись журнала не найдена.", status=404)
            return _api_error(
                "revision_conflict",
                "Запись уже изменена в другом окне. Обновите строку перед повторным сохранением.",
                status=409,
                current=_event_snapshot(current),
            )

        session.commit()
        updated_event = session.get(Event, event_id)
        if updated_event is None:
            return _api_error("not_found", "Запись журнала не найдена.", status=404)

        return jsonify({"schemaVersion": 1, "record": _event_snapshot(updated_event)})


@events_blueprint.post("/api/v2/records/<int:event_id>/close")
def journal_v2_close_record(event_id: int) -> tuple[Response, int] | Response:
    """Close one open event through an explicit optimistic transition."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _api_error("invalid_json", "Ожидался JSON-объект.", status=400)

    expected_revision = _valid_expected_revision(payload)
    if expected_revision is None:
        return _api_error("invalid_revision", "Укажите корректную ревизию записи.", status=400)

    with Session(_database_engine()) as session:
        event = session.get(Event, event_id)
        if event is None:
            return _api_error("not_found", "Запись журнала не найдена.", status=404)

        if event.revision != expected_revision:
            return _api_error(
                "revision_conflict",
                "Запись уже изменена в другом окне. Обновите строку перед повторным действием.",
                status=409,
                current=_event_snapshot(event),
            )
        if event.status == "closed":
            return _api_error(
                "already_closed",
                "Событие уже завершено.",
                status=422,
                current=_event_snapshot(event),
            )

        closed_at = datetime.now().replace(second=0, microsecond=0)
        result = session.execute(
            update(Event)
            .where(
                Event.id == event_id,
                Event.revision == expected_revision,
                Event.status == "open",
            )
            .values(
                status="closed",
                end_at=closed_at,
                updated_at=closed_at,
                revision=Event.revision + 1,
            )
        )
        if result.rowcount != 1:
            session.rollback()
            current = session.get(Event, event_id)
            if current is None:
                return _api_error("not_found", "Запись журнала не найдена.", status=404)
            return _api_error(
                "revision_conflict",
                "Запись уже изменена в другом окне. Обновите строку перед повторным действием.",
                status=409,
                current=_event_snapshot(current),
            )

        session.commit()
        updated_event = session.get(Event, event_id)
        if updated_event is None:
            return _api_error("not_found", "Запись журнала не найдена.", status=404)

        return jsonify({"schemaVersion": 1, "record": _event_snapshot(updated_event)})


@events_blueprint.route("/new", methods=["GET", "POST"])
def create_event() -> str:
    values = {
        "start_at": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "event_type": "emergency_stop",
        "include_in_report": "on",
    }

    if request.method == "POST":
        values = request.form.to_dict()
        try:
            normalized = event_values_from_form(request.form)
        except EventValidationError as exc:
            flash(str(exc), "error")
        else:
            with Session(_database_engine()) as session:
                event = Event(**normalized)
                session.add(event)
                session.commit()
            flash("Событие зарегистрировано.", "success")
            return redirect(url_for("events.list_events"))

    return render_template(
        "events/form.html",
        page_title="Новое событие",
        submit_label="Зарегистрировать событие",
        values=values,
        event=None,
        event_types=EVENT_TYPE_CHOICES,
    )


@events_blueprint.route("/<int:event_id>/edit", methods=["GET", "POST"])
def edit_event(event_id: int) -> str:
    with Session(_database_engine()) as session:
        event = _get_event_or_404(session, event_id)
        values = event_values_for_form(event)

        if request.method == "POST":
            values = request.form.to_dict()
            try:
                normalized = event_values_from_form(request.form)
            except EventValidationError as exc:
                flash(str(exc), "error")
            else:
                for field_name, field_value in normalized.items():
                    setattr(event, field_name, field_value)
                event.revision += 1
                session.commit()
                flash("Изменения сохранены.", "success")
                return redirect(url_for("events.list_events"))

        return render_template(
            "events/form.html",
            page_title=f"Событие №{event.id}",
            submit_label="Сохранить изменения",
            values=values,
            event=event,
            event_types=EVENT_TYPE_CHOICES,
        )


@events_blueprint.post("/<int:event_id>/close")
def close_event(event_id: int):
    with Session(_database_engine()) as session:
        event = _get_event_or_404(session, event_id)
        if event.status == "closed":
            flash("Событие уже завершено.", "info")
        else:
            event.end_at = datetime.now().replace(second=0, microsecond=0)
            event.status = "closed"
            event.revision += 1
            session.commit()
            flash("Событие завершено текущим временем.", "success")
    return redirect(url_for("events.list_events", status="open"))
