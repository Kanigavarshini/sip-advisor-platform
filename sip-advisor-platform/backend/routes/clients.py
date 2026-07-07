"""
routes/clients.py
------------------
Solution 2 (Client 360) and the search bar behind Solution 1/3:
search by Investor Name / UCC / Folio Number, and view a full client profile.
"""

from flask import Blueprint, request, jsonify
from models.db import query, query_one
from services.ai_engine import recommend_for_client, recommend_bulk

clients_bp = Blueprint("clients", __name__)


@clients_bp.route("/api/clients/search", methods=["GET"])
def search_clients():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    like = f"%{q}%"
    sql = """
        SELECT * FROM sips
        WHERE investor_name LIKE ? OR ucc LIKE ? OR folio_no LIKE ?
        LIMIT 25
    """
    rows = query(sql, (like, like, like))
    return jsonify(recommend_bulk(rows))


@clients_bp.route("/api/clients/<ucc>", methods=["GET"])
def get_client(ucc):
    row = query_one("SELECT * FROM sips WHERE ucc = ?", (ucc,))
    if not row:
        return jsonify({"error": "Client not found"}), 404
    row["recommendation"] = recommend_for_client(row)
    return jsonify(row)


@clients_bp.route("/api/clients", methods=["GET"])
def list_clients():
    """Optional filters: status, risk_level, scheme"""
    status = request.args.get("status")
    risk = request.args.get("risk_level")
    scheme = request.args.get("scheme")

    sql = "SELECT * FROM sips WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if risk:
        sql += " AND risk_level = ?"
        params.append(risk)
    if scheme:
        sql += " AND scheme = ?"
        params.append(scheme)

    rows = query(sql, tuple(params))
    return jsonify(recommend_bulk(rows))
