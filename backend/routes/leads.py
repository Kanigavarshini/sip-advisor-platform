"""
routes/leads.py
----------------
PRD Section 4 -- Leads. Full lifecycle: creation, qualification, status &
priority ("temperature") management, follow-up tracking, activity/notes
timeline, document upload, referral tracking and conversion to Client 360.
"""

import os
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from models.db import query, query_one, get_connection
from services import lead_engine

leads_bp = Blueprint("leads", __name__)

LEAD_DOC_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "lead_documents")
os.makedirs(LEAD_DOC_DIR, exist_ok=True)


def _now():
    return datetime.now().strftime(lead_engine.DATE_FMT)


# ---------------------------------------------------------------------
# Lead CRUD
# ---------------------------------------------------------------------

@leads_bp.route("/api/leads", methods=["GET"])
def list_leads():
    """Filters: status, priority, source, assigned_to, q (name/phone/email search)"""
    status = request.args.get("status")
    priority = request.args.get("priority")
    source = request.args.get("source")
    assigned_to = request.args.get("assigned_to")
    q = request.args.get("q", "").strip()

    sql = "SELECT * FROM leads WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if priority:
        sql += " AND priority = ?"
        params.append(priority)
    if source:
        sql += " AND source = ?"
        params.append(source)
    if assigned_to:
        sql += " AND assigned_to = ?"
        params.append(assigned_to)
    if q:
        sql += " AND (full_name LIKE ? OR phone LIKE ? OR email LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]
    sql += " ORDER BY created_at DESC"

    rows = query(sql, tuple(params))
    return jsonify(lead_engine.recommend_bulk(rows))


@leads_bp.route("/api/leads", methods=["POST"])
def create_lead():
    data = request.get_json(force=True)
    full_name = data.get("full_name")
    phone = data.get("phone")
    if not full_name or not phone:
        return jsonify({"error": "full_name and phone are required"}), 400

    source = data.get("source", "Other")
    if source not in lead_engine.VALID_SOURCES:
        return jsonify({"error": f"source must be one of {lead_engine.VALID_SOURCES}"}), 400

    priority = data.get("priority", "Warm")
    if priority not in lead_engine.VALID_PRIORITIES:
        return jsonify({"error": f"priority must be one of {lead_engine.VALID_PRIORITIES}"}), 400

    lead_id = lead_engine.new_lead_id()
    now = _now()

    conn = get_connection()
    conn.execute("""
        INSERT INTO leads (
            lead_id, full_name, phone, email, source, referred_by_ucc,
            status, priority, assigned_to, expected_investment_amount,
            interested_scheme, next_follow_up_date, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'New', ?, ?, ?, ?, ?, ?, ?)
    """, (
        lead_id, full_name, phone, data.get("email"), source, data.get("referred_by_ucc"),
        priority, data.get("assigned_to"), data.get("expected_investment_amount"),
        data.get("interested_scheme"), data.get("next_follow_up_date"), now, now,
    ))
    conn.execute("""
        INSERT INTO lead_activities (lead_id, activity_type, description, created_by, created_at)
        VALUES (?, 'Note', 'Lead created', ?, ?)
    """, (lead_id, data.get("assigned_to") or "System", now))
    conn.commit()
    conn.close()

    lead = query_one("SELECT * FROM leads WHERE lead_id = ?", (lead_id,))
    lead["recommendation"] = lead_engine.recommend_for_lead(lead)
    return jsonify(lead), 201


@leads_bp.route("/api/leads/<lead_id>", methods=["GET"])
def get_lead(lead_id):
    lead = query_one("SELECT * FROM leads WHERE lead_id = ?", (lead_id,))
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    lead["recommendation"] = lead_engine.recommend_for_lead(lead)
    lead["activities"] = query(
        "SELECT * FROM lead_activities WHERE lead_id = ? ORDER BY created_at DESC, id DESC", (lead_id,)
    )
    lead["documents"] = query(
        "SELECT id, file_name, file_type, uploaded_at FROM lead_documents WHERE lead_id = ? ORDER BY uploaded_at DESC",
        (lead_id,)
    )
    return jsonify(lead)


@leads_bp.route("/api/leads/<lead_id>", methods=["PUT"])
def update_lead(lead_id):
    lead = query_one("SELECT * FROM leads WHERE lead_id = ?", (lead_id,))
    if not lead:
        return jsonify({"error": "Lead not found"}), 404

    data = request.get_json(force=True)
    editable = [
        "full_name", "phone", "email", "source", "status", "priority",
        "assigned_to", "expected_investment_amount", "interested_scheme",
        "next_follow_up_date", "lost_reason",
    ]
    if "status" in data and data["status"] not in lead_engine.VALID_STATUSES:
        return jsonify({"error": f"status must be one of {lead_engine.VALID_STATUSES}"}), 400
    if "priority" in data and data["priority"] not in lead_engine.VALID_PRIORITIES:
        return jsonify({"error": f"priority must be one of {lead_engine.VALID_PRIORITIES}"}), 400
    if data.get("status") == "Lost" and not data.get("lost_reason") and not lead.get("lost_reason"):
        return jsonify({"error": "lost_reason is required when marking a lead as Lost"}), 400

    updates = {k: v for k, v in data.items() if k in editable}
    if not updates:
        return jsonify({"error": "No editable fields supplied"}), 400

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [_now(), lead_id]

    conn = get_connection()
    conn.execute(f"UPDATE leads SET {set_clause}, updated_at = ? WHERE lead_id = ?", params)
    if "status" in updates and updates["status"] != lead["status"]:
        conn.execute("""
            INSERT INTO lead_activities (lead_id, activity_type, description, created_by, created_at)
            VALUES (?, 'Status Change', ?, ?, ?)
        """, (lead_id, f"Status changed from {lead['status']} to {updates['status']}",
              data.get("updated_by", "RM Admin"), _now()))
    conn.commit()
    conn.close()

    updated = query_one("SELECT * FROM leads WHERE lead_id = ?", (lead_id,))
    updated["recommendation"] = lead_engine.recommend_for_lead(updated)
    return jsonify(updated)


@leads_bp.route("/api/leads/<lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    """Permanently removes a lead (e.g. not interested / duplicate / bad data),
    along with its activity timeline and any uploaded documents."""
    lead = query_one("SELECT * FROM leads WHERE lead_id = ?", (lead_id,))
    if not lead:
        return jsonify({"error": "Lead not found"}), 404

    docs = query("SELECT stored_path FROM lead_documents WHERE lead_id = ?", (lead_id,))

    conn = get_connection()
    conn.execute("DELETE FROM lead_activities WHERE lead_id = ?", (lead_id,))
    conn.execute("DELETE FROM lead_documents WHERE lead_id = ?", (lead_id,))
    conn.execute("DELETE FROM leads WHERE lead_id = ?", (lead_id,))
    conn.commit()
    conn.close()

    for doc in docs:
        try:
            if os.path.exists(doc["stored_path"]):
                os.remove(doc["stored_path"])
        except OSError:
            pass

    return jsonify({"message": f"Lead {lead_id} deleted"}), 200


# ---------------------------------------------------------------------
# Activity timeline (calls, meetings, notes)
# ---------------------------------------------------------------------

@leads_bp.route("/api/leads/<lead_id>/activities", methods=["GET"])
def list_activities(lead_id):
    return jsonify(query(
        "SELECT * FROM lead_activities WHERE lead_id = ? ORDER BY created_at DESC, id DESC", (lead_id,)
    ))


@leads_bp.route("/api/leads/<lead_id>/activities", methods=["POST"])
def add_activity(lead_id):
    lead = query_one("SELECT lead_id FROM leads WHERE lead_id = ?", (lead_id,))
    if not lead:
        return jsonify({"error": "Lead not found"}), 404

    data = request.get_json(force=True)
    activity_type = data.get("activity_type", "Note")
    description = data.get("description")
    if not description:
        return jsonify({"error": "description is required"}), 400

    conn = get_connection()
    conn.execute("""
        INSERT INTO lead_activities (lead_id, activity_type, description, created_by, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (lead_id, activity_type, description, data.get("created_by", "RM Admin"), _now()))
    conn.execute("UPDATE leads SET updated_at = ? WHERE lead_id = ?", (_now(), lead_id))
    conn.commit()
    conn.close()

    return jsonify(query(
        "SELECT * FROM lead_activities WHERE lead_id = ? ORDER BY created_at DESC, id DESC", (lead_id,)
    )), 201


# ---------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------

@leads_bp.route("/api/leads/<lead_id>/documents", methods=["POST"])
def upload_document(lead_id):
    lead = query_one("SELECT lead_id FROM leads WHERE lead_id = ?", (lead_id,))
    if not lead:
        return jsonify({"error": "Lead not found"}), 404
    if "file" not in request.files:
        return jsonify({"error": "No file sent"}), 400

    file = request.files["file"]
    file_type = request.form.get("file_type", "Other")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    stored_name = f"{lead_id}_{timestamp}_{file.filename}"
    stored_path = os.path.join(LEAD_DOC_DIR, stored_name)
    file.save(stored_path)

    conn = get_connection()
    conn.execute("""
        INSERT INTO lead_documents (lead_id, file_name, file_type, stored_path, uploaded_at)
        VALUES (?, ?, ?, ?, ?)
    """, (lead_id, file.filename, file_type, stored_path, _now()))
    conn.commit()
    conn.close()
    return jsonify(query(
        "SELECT id, file_name, file_type, uploaded_at FROM lead_documents WHERE lead_id = ? ORDER BY uploaded_at DESC",
        (lead_id,)
    )), 201


@leads_bp.route("/api/leads/documents/<int:doc_id>/download", methods=["GET"])
def download_document(doc_id):
    doc = query_one("SELECT * FROM lead_documents WHERE id = ?", (doc_id,))
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    return send_file(doc["stored_path"], as_attachment=True, download_name=doc["file_name"])


# ---------------------------------------------------------------------
# Conversion to Client
# ---------------------------------------------------------------------

@leads_bp.route("/api/leads/<lead_id>/convert", methods=["POST"])
def convert_lead(lead_id):
    data = request.get_json(force=True, silent=True) or {}
    try:
        lead = lead_engine.convert_lead_to_client(lead_id, data.get("converted_by", "RM Admin"))
        return jsonify(lead)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------
# Analytics / KPIs
# ---------------------------------------------------------------------

@leads_bp.route("/api/leads/summary", methods=["GET"])
def leads_summary():
    return jsonify(lead_engine.get_summary())


@leads_bp.route("/api/leads/funnel", methods=["GET"])
def leads_funnel():
    return jsonify(lead_engine.get_funnel())
