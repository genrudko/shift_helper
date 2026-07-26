"""HTTP routes for the operational event journal."""

from __future__ import annotations

from datetime import datetime

from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
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
    event_values_for_form,
    event_values_from_form,
)
from .models import Event


events_blueprint = Blueprint("events", __name__, url_prefix="/events")
EVENT_TYPE_LABELS = dict(EVENT_TYPE_CHOICES)


def _database_engine() -> Engine:
    return current_app.extensions["shift_helper_database_engine"]


def _get_event_or_404(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        abort(404)
    return event


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
