"""
reminder_service.py
--------------------
Solution 6: smart, configurable reminder management.

The old system was hardcoded to 4 days before due date. This service takes
the reminder window as a parameter (default 2 days, per the new business
requirement) so RMs/admins can change it without a code change -- e.g. via
a settings endpoint or the dashboard.
"""

from models.db import query

DEFAULT_REMINDER_DAYS = 2


def get_due_clients(days_before: int = DEFAULT_REMINDER_DAYS) -> list:
    """
    Returns all clients whose next_due_date falls within `days_before` days
    from now (i.e. days_to_due between 0 and days_before inclusive).
    """
    sql = """
        SELECT * FROM sips
        WHERE days_to_due >= 0 AND days_to_due <= ?
        ORDER BY days_to_due ASC
    """
    return query(sql, (days_before,))


def get_missed_clients() -> list:
    sql = "SELECT * FROM sips WHERE status = 'Missed' ORDER BY missed_count DESC"
    return query(sql)


def build_reminder_message(client: dict, channel: str = "SMS") -> str:
    """
    Builds a simple reminder message per channel (SMS/Email/WhatsApp).
    In production this would call an SMS/email/WhatsApp gateway.
    """
    return (
        f"Dear {client['investor_name']}, your SIP of ₹{client['sip_amount']} "
        f"for {client['scheme']} is due on {client['next_due_date']}. "
        f"Please ensure sufficient balance. - RupeeVyze"
    )
