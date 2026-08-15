"""
routes/proposals.py
---------------------
API for the Proposal Management module. Proposals live under a client
(Client 360), matching the spec: "Proposal Management should NOT be a
separate navigation module -- it should exist as a dedicated section
inside the Client profile."
"""

import os
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from models.db import query_one
from services import proposal_engine

proposals_bp = Blueprint("proposals", __name__)

ATTACHMENT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "proposal_attachments")
os.makedirs(ATTACHMENT_DIR, exist_ok=True)


@proposals_bp.route("/api/clients/<ucc>/proposals", methods=["GET"])
def list_client_proposals(ucc):
    client = query_one("SELECT ucc FROM sips WHERE ucc = ?", (ucc,))
    if not client:
        return jsonify({"error": "Client not found"}), 404
    return jsonify(proposal_engine.list_proposals_for_client(ucc))


@proposals_bp.route("/api/clients/<ucc>/proposals", methods=["POST"])
def create_client_proposal(ucc):
    client = query_one("SELECT ucc FROM sips WHERE ucc = ?", (ucc,))
    if not client:
        return jsonify({"error": "Client not found"}), 404

    data = request.get_json(force=True)
    purpose = data.get("purpose")
    recommendations = data.get("recommendations", [])
    created_by = data.get("created_by", "RM Admin")
    notes = data.get("internal_notes", "")
    parent_proposal_id = data.get("parent_proposal_id")

    if not purpose:
        return jsonify({"error": "purpose is required"}), 400
    if not recommendations:
        return jsonify({"error": "At least one recommendation is required"}), 400
    for r in recommendations:
        if not all(k in r for k in ("scheme_name", "investment_type", "recommended_amount")):
            return jsonify({"error": "Each recommendation needs scheme_name, investment_type, recommended_amount"}), 400

    try:
        proposal = proposal_engine.create_proposal(
            ucc=ucc, created_by=created_by, purpose=purpose,
            recommendations=recommendations, internal_notes=notes,
            parent_proposal_id=parent_proposal_id,
        )
        return jsonify(proposal), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@proposals_bp.route("/api/proposals/<proposal_id>", methods=["GET"])
def get_proposal(proposal_id):
    proposal = proposal_engine.get_proposal(proposal_id)
    if not proposal:
        return jsonify({"error": "Proposal not found"}), 404
    return jsonify(proposal)


@proposals_bp.route("/api/proposals/<proposal_id>/status", methods=["PUT"])
def update_proposal_status(proposal_id):
    data = request.get_json(force=True)
    status = data.get("status")
    client_decision = data.get("client_decision")
    decision_reason = data.get("decision_reason")

    if not status:
        return jsonify({"error": "status is required"}), 400

    try:
        proposal = proposal_engine.update_status(proposal_id, status, client_decision, decision_reason)
        return jsonify(proposal)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@proposals_bp.route("/api/proposals/<proposal_id>/version", methods=["POST"])
def create_new_version(proposal_id):
    """Creates a new version of an existing proposal (e.g. Quarterly Review)."""
    parent = proposal_engine.get_proposal(proposal_id)
    if not parent:
        return jsonify({"error": "Proposal not found"}), 404

    data = request.get_json(force=True)
    purpose = data.get("purpose", parent["purpose"])
    recommendations = data.get("recommendations") or [
        {"scheme_name": r["scheme_name"], "investment_type": r["investment_type"],
         "recommended_amount": r["recommended_amount"]}
        for r in parent["recommendations"]
    ]
    created_by = data.get("created_by", parent["created_by"])
    notes = data.get("internal_notes", "")

    new_version = proposal_engine.create_proposal(
        ucc=parent["ucc"], created_by=created_by, purpose=purpose,
        recommendations=recommendations, internal_notes=notes,
        parent_proposal_id=proposal_id,
    )
    return jsonify(new_version), 201


@proposals_bp.route("/api/proposals/<proposal_id>/recommendations/<int:rec_id>/actual", methods=["PUT"])
def record_actual(proposal_id, rec_id):
    data = request.get_json(force=True)
    actual_amount = data.get("actual_amount")
    if actual_amount is None:
        return jsonify({"error": "actual_amount is required"}), 400

    try:
        proposal = proposal_engine.record_actual_investment(proposal_id, rec_id, float(actual_amount))
        return jsonify(proposal)
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400


@proposals_bp.route("/api/proposals/<proposal_id>/attachments", methods=["POST"])
def upload_attachment(proposal_id):
    parent = proposal_engine.get_proposal(proposal_id)
    if not parent:
        return jsonify({"error": "Proposal not found"}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file sent"}), 400
    file = request.files["file"]
    file_type = request.form.get("file_type", "Other")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    stored_name = f"{proposal_id}_{timestamp}_{file.filename}"
    stored_path = os.path.join(ATTACHMENT_DIR, stored_name)
    file.save(stored_path)

    proposal = proposal_engine.add_attachment(proposal_id, file.filename, file_type, stored_path)
    return jsonify(proposal), 201


@proposals_bp.route("/api/proposals/attachments/<int:attachment_id>/download", methods=["GET"])
def download_attachment(attachment_id):
    from models.db import query_one as q1
    att = q1("SELECT * FROM proposal_attachments WHERE id = ?", (attachment_id,))
    if not att:
        return jsonify({"error": "Attachment not found"}), 404
    return send_file(att["stored_path"], as_attachment=True, download_name=att["file_name"])


@proposals_bp.route("/api/analytics/proposal-effectiveness", methods=["GET"])
def proposal_effectiveness():
    return jsonify(proposal_engine.get_effectiveness_metrics())
