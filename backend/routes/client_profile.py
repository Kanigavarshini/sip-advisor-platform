"""
routes/client_profile.py
-------------------------
PRD Section 5 -- Clients (Client 360) extensions that live alongside the
core `sips` record: family information, financial goals, risk notes,
quarterly/annual review dates, notes, communication history and referral
tracking. Kept in their own tables (see models/db.py
init_client_extension_tables) so they survive dataset re-uploads, the same
way Proposals and Leads do.
"""

import json
from datetime import datetime
from flask import Blueprint, request, jsonify
from models.db import query, query_one, get_connection
from services import lead_engine

client_profile_bp = Blueprint("client_profile", __name__)

COMM_CHANNELS = ["Call", "Email", "WhatsApp", "Meeting", "SMS"]


def _now():
    return datetime.now().strftime("%d-%m-%Y")


def _client_exists(ucc):
    return query_one("SELECT ucc FROM sips WHERE ucc = ?", (ucc,)) is not None


# ---------------------------------------------------------------------
# Profile: family, financial goals, risk notes, review dates
# ---------------------------------------------------------------------

@client_profile_bp.route("/api/clients/<ucc>/profile", methods=["GET"])
def get_profile(ucc):
    if not _client_exists(ucc):
        return jsonify({"error": "Client not found"}), 404
    row = query_one("SELECT * FROM client_profiles WHERE ucc = ?", (ucc,))
    if not row:
        return jsonify({
            "ucc": ucc, "family_members": [], "financial_goals": [],
            "risk_notes": "", "quarterly_review_date": None,
            "annual_review_date": None, "last_review_notes": "",
        })
    row["family_members"] = json.loads(row["family_members"] or "[]")
    row["financial_goals"] = json.loads(row["financial_goals"] or "[]")
    return jsonify(row)


@client_profile_bp.route("/api/clients/<ucc>/profile", methods=["PUT"])
def update_profile(ucc):
    if not _client_exists(ucc):
        return jsonify({"error": "Client not found"}), 404

    data = request.get_json(force=True)
    family_members = json.dumps(data.get("family_members", []))
    financial_goals = json.dumps(data.get("financial_goals", []))
    risk_notes = data.get("risk_notes", "")
    quarterly_review_date = data.get("quarterly_review_date")
    annual_review_date = data.get("annual_review_date")
    last_review_notes = data.get("last_review_notes", "")

    conn = get_connection()
    conn.execute("""
        INSERT INTO client_profiles (ucc, family_members, financial_goals, risk_notes,
            quarterly_review_date, annual_review_date, last_review_notes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ucc) DO UPDATE SET
            family_members=excluded.family_members,
            financial_goals=excluded.financial_goals,
            risk_notes=excluded.risk_notes,
            quarterly_review_date=excluded.quarterly_review_date,
            annual_review_date=excluded.annual_review_date,
            last_review_notes=excluded.last_review_notes,
            updated_at=excluded.updated_at
    """, (ucc, family_members, financial_goals, risk_notes,
          quarterly_review_date, annual_review_date, last_review_notes, _now()))
    conn.commit()
    conn.close()

    row = query_one("SELECT * FROM client_profiles WHERE ucc = ?", (ucc,))
    row["family_members"] = json.loads(row["family_members"] or "[]")
    row["financial_goals"] = json.loads(row["financial_goals"] or "[]")
    return jsonify(row)


# ---------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------

@client_profile_bp.route("/api/clients/<ucc>/notes", methods=["GET"])
def list_notes(ucc):
    if not _client_exists(ucc):
        return jsonify({"error": "Client not found"}), 404
    return jsonify(query(
        "SELECT * FROM client_notes WHERE ucc = ? ORDER BY created_at DESC, id DESC", (ucc,)
    ))


@client_profile_bp.route("/api/clients/<ucc>/notes", methods=["POST"])
def add_note(ucc):
    if not _client_exists(ucc):
        return jsonify({"error": "Client not found"}), 404
    data = request.get_json(force=True)
    note = data.get("note")
    if not note:
        return jsonify({"error": "note is required"}), 400

    conn = get_connection()
    conn.execute("""
        INSERT INTO client_notes (ucc, note, created_by, created_at) VALUES (?, ?, ?, ?)
    """, (ucc, note, data.get("created_by", "RM Admin"), _now()))
    conn.commit()
    conn.close()
    return jsonify(query(
        "SELECT * FROM client_notes WHERE ucc = ? ORDER BY created_at DESC, id DESC", (ucc,)
    )), 201


# ---------------------------------------------------------------------
# Communication history
# ---------------------------------------------------------------------

@client_profile_bp.route("/api/clients/<ucc>/communications", methods=["GET"])
def list_communications(ucc):
    if not _client_exists(ucc):
        return jsonify({"error": "Client not found"}), 404
    return jsonify(query(
        "SELECT * FROM client_communications WHERE ucc = ? ORDER BY created_at DESC, id DESC", (ucc,)
    ))


@client_profile_bp.route("/api/clients/<ucc>/communications", methods=["POST"])
def add_communication(ucc):
    if not _client_exists(ucc):
        return jsonify({"error": "Client not found"}), 404
    data = request.get_json(force=True)
    channel = data.get("channel", "Call")
    summary = data.get("summary")
    if channel not in COMM_CHANNELS:
        return jsonify({"error": f"channel must be one of {COMM_CHANNELS}"}), 400
    if not summary:
        return jsonify({"error": "summary is required"}), 400

    conn = get_connection()
    conn.execute("""
        INSERT INTO client_communications (ucc, channel, summary, created_by, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (ucc, channel, summary, data.get("created_by", "RM Admin"), _now()))
    conn.commit()
    conn.close()
    return jsonify(query(
        "SELECT * FROM client_communications WHERE ucc = ? ORDER BY created_at DESC, id DESC", (ucc,)
    )), 201


# ---------------------------------------------------------------------
# Referrals (Client -> new Lead)
# ---------------------------------------------------------------------

@client_profile_bp.route("/api/clients/<ucc>/referrals", methods=["GET"])
def list_referrals(ucc):
    if not _client_exists(ucc):
        return jsonify({"error": "Client not found"}), 404
    return jsonify(query(
        "SELECT * FROM client_referrals WHERE ucc = ? ORDER BY created_at DESC, id DESC", (ucc,)
    ))


@client_profile_bp.route("/api/clients/<ucc>/referrals", methods=["POST"])
def add_referral(ucc):
    if not _client_exists(ucc):
        return jsonify({"error": "Client not found"}), 404
    data = request.get_json(force=True)
    referred_name = data.get("referred_name")
    if not referred_name:
        return jsonify({"error": "referred_name is required"}), 400
    referred_phone = data.get("referred_phone")
    create_lead = bool(data.get("create_lead", True))

    lead_id = None
    now = _now()
    conn = get_connection()

    if create_lead:
        if not referred_phone:
            conn.close()
            return jsonify({"error": "referred_phone is required to auto-create a lead"}), 400
        lead_id = lead_engine.new_lead_id()
        conn.execute("""
            INSERT INTO leads (
                lead_id, full_name, phone, source, referred_by_ucc,
                status, priority, created_at, updated_at
            ) VALUES (?, ?, ?, 'Referral', ?, 'New', 'Warm', ?, ?)
        """, (lead_id, referred_name, referred_phone, ucc, now, now))
        conn.execute("""
            INSERT INTO lead_activities (lead_id, activity_type, description, created_by, created_at)
            VALUES (?, 'Note', ?, ?, ?)
        """, (lead_id, f"Referred by existing client {ucc}", data.get("created_by", "RM Admin"), now))

    conn.execute("""
        INSERT INTO client_referrals (ucc, referred_name, referred_phone, lead_id, status, created_at)
        VALUES (?, ?, ?, ?, 'New', ?)
    """, (ucc, referred_name, referred_phone, lead_id, now))
    conn.commit()
    conn.close()

    return jsonify(query(
        "SELECT * FROM client_referrals WHERE ucc = ? ORDER BY created_at DESC, id DESC", (ucc,)
    )), 201
