"""
routes/reports.py
-------------------
Solutions 3, 4, 5: individual reports, combined reports (all/branch/scheme),
and custom date-range reports. Returns a downloadable file path (the frontend
turns this into a download link / triggers a browser download).
"""

from flask import Blueprint, request, jsonify, send_file
from models.db import query, query_one
from services.report_generator import build_report

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/api/reports/individual/<ucc>", methods=["GET"])
def individual_report(ucc):
    fmt = request.args.get("format", "excel")
    rows = query("SELECT * FROM sips WHERE ucc = ?", (ucc,))
    if not rows:
        return jsonify({"error": "Client not found"}), 404

    path = build_report(rows, scope=f"individual_{ucc}", fmt=fmt)
    return send_file(path, as_attachment=True)


@reports_bp.route("/api/reports/combined", methods=["GET"])
def combined_report():
    """
    Query params:
      format: excel | pdf
      scope: all | branch | scheme
      value: required if scope is branch or scheme (e.g. scheme name, bank name)
      start_date, end_date: dd-mm-yyyy, optional (Solution 5: custom date range)
    """
    fmt = request.args.get("format", "excel")
    scope = request.args.get("scope", "all")
    value = request.args.get("value")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    sql = "SELECT * FROM sips WHERE 1=1"
    params = []
    scope_name = "combined_all"

    if scope == "scheme" and value:
        sql += " AND scheme = ?"
        params.append(value)
        scope_name = f"combined_scheme_{value.replace(' ', '_')}"
    elif scope == "branch" and value:
        sql += " AND bank_details LIKE ?"
        params.append(f"%{value}%")
        scope_name = f"combined_branch_{value.replace(' ', '_')}"

    rows = query(sql, tuple(params))
    if not rows:
        return jsonify({"error": "No records match this scope/filter"}), 404

    path = build_report(rows, scope=scope_name, fmt=fmt,
                         start_date=start_date, end_date=end_date)
    return send_file(path, as_attachment=True)
