"""
routes/assistant.py
---------------------
Solution 8: AI Assistant. Not an LLM for this prototype -- a keyword-based
router over the same rule-based data/AI engine, so simple natural-language-
style questions resolve to real dataset queries. Designed so a future version
can swap this router for an actual LLM call (e.g. OpenAI GPT / Google Gemini)
without changing what the frontend sends or expects back.
"""

from flask import Blueprint, request, jsonify
from models.db import query
from services.reminder_service import get_due_clients, get_missed_clients
from services.ai_engine import recommend_bulk

assistant_bp = Blueprint("assistant", __name__)


def handle_query(text: str):
    t = text.lower()

    if "due tomorrow" in t or "due today" in t:
        days = 1 if "tomorrow" in t else 0
        rows = [c for c in get_due_clients(2) if c["days_to_due"] == days]
        return {"answer": f"{len(rows)} SIP(s) due", "results": rows}

    if "due" in t and ("day" in t or "soon" in t):
        rows = get_due_clients(2)
        return {"answer": f"{len(rows)} SIP(s) due in the next 2 days", "results": rows}

    if "missed" in t:
        rows = get_missed_clients()
        return {"answer": f"{len(rows)} client(s) with missed SIPs", "results": rows}

    if "high risk" in t or "high-risk" in t:
        rows = query("SELECT * FROM sips WHERE risk_level = 'High'")
        return {"answer": f"{len(rows)} high-risk client(s)", "results": recommend_bulk(rows)}

    if "premium" in t:
        rows = query("SELECT * FROM sips WHERE is_premium = 1")
        return {"answer": f"{len(rows)} premium client(s)", "results": rows}

    if "inactive" in t or "completed" in t:
        rows = query("SELECT * FROM sips WHERE status = 'Completed'")
        return {"answer": f"{len(rows)} completed/inactive SIP(s)", "results": rows}

    if "annual report" in t or "yearly report" in t:
        return {
            "answer": "Use the Reports tab and select a custom date range covering "
                      "the full year to generate an annual report.",
            "results": [],
        }

    return {
        "answer": "I couldn't match that to a known query. Try: 'show SIPs due "
                  "tomorrow', 'show missed SIPs', 'show high risk clients', "
                  "'show premium clients'.",
        "results": [],
    }


@assistant_bp.route("/api/assistant/query", methods=["GET"])
def assistant_query():
    q = request.args.get("q", "")
    if not q:
        return jsonify({"error": "Missing query parameter 'q'"}), 400
    return jsonify(handle_query(q))
