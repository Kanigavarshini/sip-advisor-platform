"""
ai_engine.py
------------
Solution 7 from the problem statement: a rule-based AI recommendation engine.
No ML model is trained for this prototype -- recommendations come from
transparent, explainable if/else rules over the enriched SIP data. This is
intentional: it's easy to demo, requires no historical labeled data, and can
be swapped for a trained model later without changing the API contract
(every recommendation still returns the same {label, action, reason} shape).
"""


def recommend_for_client(client: dict) -> dict:
    """
    client: a single enriched row from the `sips` table (as a dict).
    Returns a recommendation dict: {label, action, reason}
    """
    missed = client["missed_count"]
    days_to_due = client["days_to_due"]
    is_premium = bool(client["is_premium"])
    risk = client["risk_level"]

    # Rule 1: high risk -> contact immediately
    if risk == "High":
        return {
            "label": "High risk",
            "action": "Contact immediately",
            "reason": f"{missed} SIP installments missed",
        }

    # Rule 2: due soon -> send reminder
    if 0 <= days_to_due <= 2:
        return {
            "label": "Due soon",
            "action": "Send reminder",
            "reason": f"Next installment due in {days_to_due} day(s)",
        }

    # Rule 3: premium client -> assign senior RM
    if is_premium:
        return {
            "label": "Premium client",
            "action": "Assign senior RM",
            "reason": f"SIP amount of ₹{client['sip_amount']} qualifies as premium",
        }

    # Rule 4: medium risk -> monitor
    if risk == "Medium":
        return {
            "label": "Medium risk",
            "action": "Monitor next installment",
            "reason": f"{missed} SIP installment(s) missed previously",
        }

    # Default: healthy client
    return {
        "label": "Healthy",
        "action": "No action needed",
        "reason": "SIP is active with no missed installments",
    }


def recommend_bulk(clients: list) -> list:
    """Attach a recommendation to each client record."""
    out = []
    for c in clients:
        rec = recommend_for_client(c)
        merged = dict(c)
        merged["recommendation"] = rec
        out.append(merged)
    return out
