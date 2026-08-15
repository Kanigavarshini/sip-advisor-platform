"""
routes/clients.py
------------------
Solution 2 (Client 360) and the search bar behind Solution 1/3:
search by Investor Name / UCC / Folio Number, and view a full client profile.

IMPORTANT: one investor (UCC) can hold several SIPs (different schemes,
folios, even different funds registered on different dates) -- the `sips`
table has one row per SIP, not one row per client. Every endpoint here
aggregates those rows by `ucc` so a client with 14 SIPs shows up as ONE
client (with all 14 SIPs listed inside their profile), not 14 separate
"clients" with the same name.
"""

from flask import Blueprint, request, jsonify
from models.db import query, query_one
from services.ai_engine import recommend_for_client, recommend_bulk

clients_bp = Blueprint("clients", __name__)

RISK_RANK = {"Low": 1, "Medium": 2, "High": 3}
PREMIUM_THRESHOLD = 5000


def _aggregate_by_ucc(sip_rows: list) -> list:
    """
    Groups raw `sips` rows (one per SIP) into one summary dict per UCC.
    Each summary dict has the same shape recommend_for_client() expects
    (missed_count, days_to_due, is_premium, risk_level, sip_amount) so
    existing recommendation logic works unchanged on the aggregated view,
    plus a nested "sips" list with every individual SIP for that client.
    """
    groups = {}
    order = []
    for r in sip_rows:
        ucc = r["ucc"]
        if ucc not in groups:
            groups[ucc] = []
            order.append(ucc)
        groups[ucc].append(r)

    clients = []
    for ucc in order:
        sips = groups[ucc]
        first = sips[0]
        total_amount = sum(s["sip_amount"] for s in sips)
        missed_total = sum(s["missed_count"] for s in sips)
        # A client is considered missed when any SIP has a missed installment.
        # This keeps the Client 360/Overview status consistent even when an
        # imported row has a non-standard status label but missed_count > 0.
        missed_sip_count = sum(1 for s in sips if int(s.get("missed_count") or 0) > 0 or s.get("status") == "Missed")
        worst_risk = max((s["risk_level"] for s in sips), key=lambda r: RISK_RANK.get(r, 0))
        if missed_sip_count:
            overall_status = "Missed"
        elif any(s["status"] == "Active" for s in sips):
            overall_status = "Active"
        else:
            overall_status = sips[0]["status"]

        upcoming = [s for s in sips if s.get("days_to_due", -1) >= 0]
        soonest = min(upcoming, key=lambda s: s["days_to_due"]) if upcoming else \
            min(sips, key=lambda s: s.get("days_to_due", 0))

        clients.append({
            "ucc": ucc,
            "investor_name": first["investor_name"],
            "holding_type": first["holding_type"],
            "bank_details": first["bank_details"],
            "folio_no": first["folio_no"],
            "sip_count": len(sips),
            "sip_amount": total_amount,
            "missed_count": missed_total,
            "missed_sip_count": missed_sip_count,
            "status": overall_status,
            "risk_level": worst_risk,
            "is_premium": bool(any(s["is_premium"] for s in sips) or total_amount >= PREMIUM_THRESHOLD),
            "needs_reminder": bool(any(s["needs_reminder"] for s in sips)),
            "next_due_date": soonest.get("next_due_date"),
            "days_to_due": soonest.get("days_to_due"),
            "schemes": sorted({s["scheme"] for s in sips}),
            "sips": recommend_bulk(sips),
        })
    return clients


@clients_bp.route("/api/clients/search", methods=["GET"])
def search_clients():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    like = f"%{q}%"
    sql = """
        SELECT * FROM sips
        WHERE investor_name LIKE ? OR ucc LIKE ? OR folio_no LIKE ?
    """
    rows = query(sql, (like, like, like))
    clients = _aggregate_by_ucc(rows)[:25]
    return jsonify(recommend_bulk(clients))


@clients_bp.route("/api/clients/<ucc>", methods=["GET"])
def get_client(ucc):
    rows = query("SELECT * FROM sips WHERE ucc = ?", (ucc,))
    if not rows:
        return jsonify({"error": "Client not found"}), 404
    client = _aggregate_by_ucc(rows)[0]
    client["recommendation"] = recommend_for_client(client)
    return jsonify(client)




@clients_bp.route("/api/clients/attention", methods=["GET"])
def clients_needing_attention():
    """
    Returns client-level attention items for the Overview dashboard.

    The queue is intentionally based on the same transparent recommendation
    engine used in Client 360: high/medium risk, missed SIPs, due-soon SIPs,
    and premium-client handling are surfaced; healthy clients are excluded.
    One row is returned per UCC so clients holding multiple SIPs are not
    duplicated in the attention queue.
    """
    rows = query("SELECT * FROM sips ORDER BY ucc, sr_no")
    clients = _aggregate_by_ucc(rows)
    attention = []
    for client in clients:
        rec = recommend_for_client(client)
        if rec["label"] == "Healthy":
            continue
        item = dict(client)
        item["recommendation"] = rec
        attention.append(item)

    priority = {
        "High risk": 1,
        "Due soon": 2,
        "Premium client": 3,
        "Medium risk": 4,
    }
    attention.sort(key=lambda c: (priority.get(c["recommendation"]["label"], 9), c["investor_name"]))
    return jsonify(attention[:25])


@clients_bp.route("/api/clients", methods=["GET"])
def list_clients():
    """
    Optional filters: status, risk_level, scheme -- applied at the SIP
    level (e.g. "which SIPs are high risk right now"), used by the Overview
    "needs attention" table which shows one row per flagged SIP/scheme.
    """
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
