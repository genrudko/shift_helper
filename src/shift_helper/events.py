"""HTTP routes for the operational event journal."""

from __future__ import annotations

import json
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .domain import (
    EVENT_TYPE_CHOICES,
    EventValidationError,
    calculate_downtime_losses_rub,
    event_to_row,
    event_values_for_form,
    event_values_from_form,
    event_values_from_row,
)
from .models import DeletedEvent, Event

events_blueprint = Blueprint("events", __name__, url_prefix="/events")
EVENT_TYPE_LABELS = dict(EVENT_TYPE_CHOICES)


def _database_engine() -> Engine:
    return current_app.extensions["shift_helper_database_engine"]


def _get_event_or_404(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        abort(404)
    return event


def _request_json() -> dict[str, object]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise EventValidationError("Не удалось прочитать данные строки.")
    return payload


def _distinct_values(session: Session, column) -> list[str]:
    statement = (
        select(column)
        .where(column.is_not(None), column != "")
        .distinct()
        .order_by(column)
    )
    return [str(value) for value in session.scalars(statement) if value]


def _event_snapshot(event: Event) -> str:
    values = {
        column.name: getattr(event, column.key)
        for column in Event.__table__.columns
    }
    return json.dumps(values, ensure_ascii=False, default=str, sort_keys=True)


@events_blueprint.get("")
def list_events() -> str:
    selected_status = request.args.get("status", "all")
    if selected_status not in {"all", "open", "closed"}:
        selected_status = "all"

    statement = select(Event).order_by(Event.start_at.asc(), Event.id.asc())
    with Session(_database_engine()) as session:
        rows = [event_to_row(event) for event in session.scalars(statement)]
        suggestions = {
            "asset_label": _distinct_values(session, Event.asset_label),
            "description": _distinct_values(session, Event.description),
            "performer": _distinct_values(session, Event.performer),
            "author": _distinct_values(session, Event.author),
            "reason": _distinct_values(session, Event.reason),
            "actions": _distinct_values(session, Event.actions),
        }

    now = datetime.now().replace(second=0, microsecond=0)
    return render_template(
        "events/list.html",
        rows=rows,
        suggestions=suggestions,
        selected_status=selected_status,
        draft_date=now.strftime("%d.%m.%Y"),
        draft_time=now.strftime("%H:%M"),
    )


@events_blueprint.post("/rows")
def create_event_row():
    try:
        payload = _request_json()
        normalized = event_values_from_row(payload)
    except EventValidationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    with Session(_database_engine()) as session:
        event = Event(**normalized)
        session.add(event)
        session.commit()
        session.refresh(event)
        return jsonify({"ok": True, "row": event_to_row(event)}), 201


@events_blueprint.patch("/<int:event_id>/row")
def update_event_row(event_id: int):
    try:
        payload = _request_json()
    except EventValidationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    with Session(_database_engine()) as session:
        event = _get_event_or_404(session, event_id)
        expected_revision = payload.get("revision")
        if expected_revision is not None and int(expected_revision) != event.revision:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Строка уже была изменена. Обновите журнал и повторите ввод.",
                    }
                ),
                409,
            )

        try:
            normalized = event_values_from_row(payload, existing_event=event)
        except EventValidationError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

        for field_name, field_value in normalized.items():
            setattr(event, field_name, field_value)
        event.revision += 1
        session.commit()
        session.refresh(event)
        return jsonify({"ok": True, "row": event_to_row(event)})


@events_blueprint.delete("/<int:event_id>/row")
def delete_event_row(event_id: int):
    try:
        payload = _request_json()
    except EventValidationError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    with Session(_database_engine()) as session:
        event = _get_event_or_404(session, event_id)
        expected_revision = payload.get("revision")
        if expected_revision is not None and int(expected_revision) != event.revision:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Строка уже была изменена. Обновите журнал перед удалением.",
                    }
                ),
                409,
            )

        session.add(
            DeletedEvent(
                original_event_id=event.id,
                snapshot_json=_event_snapshot(event),
            )
        )
        session.delete(event)
        session.commit()
        return jsonify({"ok": True, "deleted_id": event_id})


@events_blueprint.route("/new", methods=["GET", "POST"])
def create_event() -> str:
    """Keep the legacy full form available as a diagnostic fallback."""
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
    """Keep the legacy full form available as a diagnostic fallback."""
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
    """Keep the legacy close action for compatibility with previous builds."""
    with Session(_database_engine()) as session:
        event = _get_event_or_404(session, event_id)
        if event.status == "closed":
            flash("Событие уже завершено.", "info")
        else:
            event.end_at = datetime.now().replace(second=0, microsecond=0)
            event.downtime_losses_rub = calculate_downtime_losses_rub(
                event.start_at,
                event.end_at,
            )
            event.status = "closed"
            event.revision += 1
            session.commit()
            flash("Событие завершено текущим временем.", "success")
    return redirect(url_for("events.list_events", status="open"))
