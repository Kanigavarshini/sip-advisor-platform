"""
routes/analytics.py
---------------------
Solution 1 (centralized dashboard stats) and Solution 9 (analytics charts).
"""

from flask import Blueprint, jsonify
from models.db import query, query_one

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/api/analytics/summary", methods=["GET"])
def summary():
    total = query_one("SELECT COUNT(*) as c FROM sips")["c"]
    active = query_one("SELECT COUNT(*) as c FROM sips WHERE status = 'Active'")["c"]
    missed = query_one("SELECT COUNT(*) as c FROM sips WHERE status = 'Missed'")["c"]
    due_soon = query_one(
        "SELECT COUNT(*) as c FROM sips WHERE days_to_due >= 0 AND days_to_due <= 2"
    )["c"]
    high_risk = query_one("SELECT COUNT(*) as c FROM sips WHERE risk_level = 'High'")["c"]
    premium = query_one("SELECT COUNT(*) as c FROM sips WHERE is_premium = 1")["c"]

    return jsonify({
        "total_clients": total,
        "active_sips": active,
        "missed_sips": missed,
        "due_soon": due_soon,
        "high_risk_clients": high_risk,
        "premium_clients": premium,
    })


@analytics_bp.route("/api/analytics/status-breakdown", methods=["GET"])
def status_breakdown():
    rows = query("SELECT status, COUNT(*) as count FROM sips GROUP BY status")
    return jsonify(rows)


@analytics_bp.route("/api/analytics/risk-distribution", methods=["GET"])
def risk_distribution():
    rows = query("SELECT risk_level, COUNT(*) as count FROM sips GROUP BY risk_level")
    return jsonify(rows)


@analytics_bp.route("/api/analytics/scheme-distribution", methods=["GET"])
def scheme_distribution():
    rows = query("SELECT scheme, COUNT(*) as count FROM sips GROUP BY scheme ORDER BY count DESC")
    return jsonify(rows)


@analytics_bp.route("/api/analytics/monthly-trend", methods=["GET"])
def monthly_trend():
    """SIPs grouped by the month of sip_start_date (registration trend)."""
    rows = query("""
        SELECT substr(sip_start_date, 4, 7) as month, COUNT(*) as count
        FROM sips
        GROUP BY month
        ORDER BY substr(month,4,4), substr(month,1,2)
    """)
    return jsonify(rows)
