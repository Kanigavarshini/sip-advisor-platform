"""
routes/reminders.py
---------------------
Solution 6: smart reminder management with a configurable days-before window.
"""

from flask import Blueprint, request, jsonify
from services.reminder_service import get_due_clients, get_missed_clients, build_reminder_message

reminders_bp = Blueprint("reminders", __name__)


@reminders_bp.route("/api/reminders/due", methods=["GET"])
def due_reminders():
    days = int(request.args.get("days", 2))
    clients = get_due_clients(days_before=days)
    for c in clients:
        c["preview_message"] = build_reminder_message(c)
    return jsonify(clients)


@reminders_bp.route("/api/reminders/missed", methods=["GET"])
def missed_reminders():
    return jsonify(get_missed_clients())
