"""
lead_engine.py
--------------
Business rules for the Leads module (PRD Section 4): lead ID generation,
next-best-action recommendations, and conversion of a qualified lead into
a Client 360 record.

Mirrors the transparent, rule-based style of ai_engine.py -- no ML model,
just explainable if/else rules, so recommendations can be swapped for a
trained model later without changing the API contract.
"""

import uuid
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from models.db import get_connection, query, query_one

VALID_SOURCES = [
    "Referral", "Walk-in", "Social Media", "Website", "Cold Call", "Event", "Other",
]
VALID_STATUSES = [
    "New", "Contacted", "Qualified", "Proposal Sent",
    "Negotiation", "Converted", "Lost",
]
VALID_PRIORITIES = ["Hot", "Warm", "Cold"]  # a.k.a. lead temperature
DATE_FMT = "%d-%m-%Y"
PREMIUM_THRESHOLD = 5000  # kept in sync with ingestion.py's premium rule


def new_lead_id() -> str:
    return f"LEAD-{uuid.uuid4().hex[:8].upper()}"


def _days_until(date_str: str) -> int | None:
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str, DATE_FMT)
    except ValueError:
        return None
    return (d - datetime.now()).days


def recommend_for_lead(lead: dict) -> dict:
    """
    Returns a next-best-action recommendation: {label, action, reason}.
    Same shape as ai_engine.recommend_for_client so the frontend can render
    both with one badge/action component.
    """
    status = lead["status"]
    priority = lead["priority"]
    days_left = _days_until(lead.get("next_follow_up_date"))

    if status in ("Converted", "Lost"):
        return {
            "label": status,
            "action": "No action needed" if status == "Converted" else "Archive",
            "reason": f"Lead is already {status.lower()}",
        }

    if days_left is not None and days_left < 0:
        return {
            "label": "Follow-up overdue",
            "action": "Call today",
            "reason": f"Follow-up was due {abs(days_left)} day(s) ago",
        }

    if priority == "Hot" and status == "New":
        return {
            "label": "Hot lead",
            "action": "Contact within 24 hours",
            "reason": "High-priority lead has not been contacted yet",
        }

    if status == "Qualified":
        return {
            "label": "Ready for proposal",
            "action": "Send proposal",
            "reason": "Lead is qualified but no proposal has been sent",
        }

    if status == "Proposal Sent" and (days_left is None or days_left > 5):
        return {
            "label": "Awaiting response",
            "action": "Schedule follow-up",
            "reason": "Proposal sent but no follow-up date set in the next 5 days",
        }

    if status == "Negotiation":
        return {
            "label": "Close attention",
            "action": "Escalate to senior RM",
            "reason": "Lead is in active negotiation",
        }

    if priority == "Cold" and status in ("New", "Contacted"):
        return {
            "label": "Low engagement",
            "action": "Nurture via email/newsletter",
            "reason": "Cold lead with no recent movement",
        }

    return {
        "label": "On track",
        "action": "Continue follow-up cadence",
        "reason": f"Lead is in '{status}' stage, no immediate action required",
    }


def recommend_bulk(leads: list) -> list:
    out = []
    for l in leads:
        merged = dict(l)
        merged["recommendation"] = recommend_for_lead(l)
        out.append(merged)
    return out


def convert_lead_to_client(lead_id: str, converted_by: str = "RM Admin") -> dict:
    """
    Converts a Qualified/Negotiation lead into a Client 360 record.

    Note: real client data normally arrives via the SIP dataset ingestion
    pipeline (services/ingestion.py). Converting a lead in-app instead
    inserts a minimal `sips` row with sensible defaults so the new client
    immediately shows up in Client 360 -- KYC/folio fields are marked
    "Pending" until the back-office completes onboarding and the next
    dataset upload reconciles the real values.
    """
    lead = query_one("SELECT * FROM leads WHERE lead_id = ?", (lead_id,))
    if not lead:
        raise ValueError("Lead not found")
    if lead["status"] == "Converted":
        raise ValueError("Lead is already converted")

    ucc = f"UCC-{lead_id.replace('LEAD-', '')}"
    now = datetime.now()
    amount = lead["expected_investment_amount"] or 1000
    next_due = now + relativedelta(months=1)
    sip_end = now + relativedelta(years=3)

    conn = get_connection()
    conn.execute("""
        INSERT INTO sips (
            sr_no, ucc, investor_name, holding_type, folio_no, bank_details,
            sip_no, sip_submission_date, scheme, sip_start_date, sip_end_date,
            sip_amount, frequency, next_due_date, days_to_due, missed_count,
            status, risk_level, is_premium, last_transaction_date, needs_reminder
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        None, ucc, lead["full_name"], "Pending KYC", f"PENDING-{lead_id}", "Pending KYC",
        f"SIP-{lead_id}", now.strftime(DATE_FMT), lead["interested_scheme"] or "Not Selected",
        now.strftime(DATE_FMT), sip_end.strftime(DATE_FMT),
        amount, "Monthly", next_due.strftime(DATE_FMT), (next_due - now).days, 0,
        "Active", "Low", 1 if amount >= PREMIUM_THRESHOLD else 0, None, 0,
    ))
    conn.execute("""
        UPDATE leads SET status = 'Converted', converted_ucc = ?, converted_at = ?, updated_at = ?
        WHERE lead_id = ?
    """, (ucc, now.strftime(DATE_FMT), now.strftime(DATE_FMT), lead_id))
    conn.execute("""
        INSERT INTO lead_activities (lead_id, activity_type, description, created_by, created_at)
        VALUES (?, 'Status Change', ?, ?, ?)
    """, (lead_id, f"Converted to Client 360 as {ucc}", converted_by, now.strftime(DATE_FMT)))
    # If this lead came from a referral, mark that referral as Converted too
    conn.execute("""
        UPDATE client_referrals SET status = 'Converted' WHERE lead_id = ?
    """, (lead_id,))
    conn.commit()
    conn.close()

    return query_one("SELECT * FROM leads WHERE lead_id = ?", (lead_id,))


def get_funnel() -> list:
    return query("SELECT status, COUNT(*) as count FROM leads GROUP BY status")


def get_summary() -> dict:
    total = query_one("SELECT COUNT(*) as c FROM leads")["c"]
    hot = query_one("SELECT COUNT(*) as c FROM leads WHERE priority = 'Hot' AND status NOT IN ('Converted','Lost')")["c"]
    converted = query_one("SELECT COUNT(*) as c FROM leads WHERE status = 'Converted'")["c"]
    lost = query_one("SELECT COUNT(*) as c FROM leads WHERE status = 'Lost'")["c"]
    open_leads = query_one("SELECT COUNT(*) as c FROM leads WHERE status NOT IN ('Converted','Lost')")["c"]
    closed = converted + lost
    conversion_rate = round((converted / closed) * 100, 1) if closed else 0.0

    return {
        "total_leads": total,
        "open_leads": open_leads,
        "hot_leads": hot,
        "converted_leads": converted,
        "lost_leads": lost,
        "conversion_rate_percent": conversion_rate,
    }
