"""
proposal_engine.py
--------------------
Implements the Proposal Management module per the RVOS Proposal Management
Final Specification:

- A Proposal is a versioned, formal record of what an advisor recommended
  to a client -- kept separate from what was actually invested.
- Lifecycle: Draft -> Shared -> Discussion -> Accepted / Partially Accepted
  / Rejected -> Executed -> Archived.
- Proposals are never overwritten. A follow-up review creates a NEW version
  linked back to the original via parent_proposal_id.
- Recommended vs Actual amounts are tracked per fund line item so advisory
  effectiveness (acceptance rate) can be measured later.
"""

import uuid
from datetime import datetime
from models.db import get_connection, query, query_one

VALID_STATUSES = [
    "Draft", "Shared", "Discussion", "Accepted",
    "Partially Accepted", "Rejected", "Executed", "Archived",
]
VALID_DECISIONS = ["Accepted", "Partially Accepted", "Rejected", "Pending"]
VALID_PURPOSES = [
    "Initial Investment", "Quarterly Review", "Annual Review", "Additional SIP",
    "Lumpsum Investment", "Portfolio Rebalancing", "Goal Planning",
    "Tax Planning", "Insurance Review", "Other",
]


def _new_proposal_id() -> str:
    return f"PROP-{uuid.uuid4().hex[:8].upper()}"


def create_proposal(ucc: str, created_by: str, purpose: str,
                     recommendations: list, internal_notes: str = "",
                     parent_proposal_id: str = None) -> dict:
    """
    Creates a new proposal (Version 1) or, if parent_proposal_id is given,
    a new version linked to that parent (Version N+1) -- e.g. turning a
    Version 1 Initial Proposal into a Version 2 Quarterly Review without
    ever overwriting the original.
    """
    proposal_id = _new_proposal_id()
    version_number = 1

    if parent_proposal_id:
        parent = query_one("SELECT * FROM proposals WHERE proposal_id = ?", (parent_proposal_id,))
        if not parent:
            raise ValueError("Parent proposal not found")
        # version number = highest version in this chain + 1
        chain_max = query_one("""
            SELECT MAX(version_number) as v FROM proposals
            WHERE proposal_id = ? OR parent_proposal_id = ?
        """, (parent_proposal_id, parent_proposal_id))
        version_number = (chain_max["v"] or parent["version_number"]) + 1

    conn = get_connection()
    conn.execute("""
        INSERT INTO proposals
        (proposal_id, ucc, proposal_date, created_by, version_number,
         parent_proposal_id, purpose, status, client_decision, decision_reason,
         internal_notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Draft', 'Pending', NULL, ?, ?)
    """, (
        proposal_id, ucc, datetime.now().strftime("%d-%m-%Y"), created_by,
        version_number, parent_proposal_id, purpose, internal_notes,
        datetime.now().isoformat(),
    ))

    for rec in recommendations:
        conn.execute("""
            INSERT INTO proposal_recommendations
            (proposal_id, scheme_name, investment_type, recommended_amount, actual_amount)
            VALUES (?, ?, ?, ?, NULL)
        """, (proposal_id, rec["scheme_name"], rec["investment_type"], rec["recommended_amount"]))

    conn.commit()
    conn.close()
    return get_proposal(proposal_id)


def get_proposal(proposal_id: str) -> dict:
    proposal = query_one("SELECT * FROM proposals WHERE proposal_id = ?", (proposal_id,))
    if not proposal:
        return None
    proposal["recommendations"] = query(
        "SELECT * FROM proposal_recommendations WHERE proposal_id = ?", (proposal_id,)
    )
    proposal["attachments"] = query(
        "SELECT id, file_name, file_type, uploaded_at FROM proposal_attachments WHERE proposal_id = ?",
        (proposal_id,)
    )
    return proposal


def list_proposals_for_client(ucc: str) -> list:
    proposals = query(
        "SELECT * FROM proposals WHERE ucc = ? ORDER BY created_at DESC", (ucc,)
    )
    for p in proposals:
        p["recommendations"] = query(
            "SELECT * FROM proposal_recommendations WHERE proposal_id = ?", (p["proposal_id"],)
        )
    return proposals


def update_status(proposal_id: str, status: str, client_decision: str = None,
                   decision_reason: str = None) -> dict:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}")
    if client_decision and client_decision not in VALID_DECISIONS:
        raise ValueError(f"Invalid decision. Must be one of: {', '.join(VALID_DECISIONS)}")

    conn = get_connection()
    conn.execute("""
        UPDATE proposals SET status = ?,
            client_decision = COALESCE(?, client_decision),
            decision_reason = ?
        WHERE proposal_id = ?
    """, (status, client_decision, decision_reason, proposal_id))
    conn.commit()
    conn.close()
    return get_proposal(proposal_id)


def record_actual_investment(proposal_id: str, recommendation_id: int, actual_amount: float) -> dict:
    """Records what was actually invested against a specific recommendation line."""
    conn = get_connection()
    conn.execute(
        "UPDATE proposal_recommendations SET actual_amount = ? WHERE id = ? AND proposal_id = ?",
        (actual_amount, recommendation_id, proposal_id)
    )
    conn.commit()
    conn.close()
    return get_proposal(proposal_id)


def add_attachment(proposal_id: str, file_name: str, file_type: str, stored_path: str) -> dict:
    conn = get_connection()
    conn.execute("""
        INSERT INTO proposal_attachments (proposal_id, file_name, file_type, stored_path, uploaded_at)
        VALUES (?, ?, ?, ?, ?)
    """, (proposal_id, file_name, file_type, stored_path, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return get_proposal(proposal_id)


def get_effectiveness_metrics() -> dict:
    """
    Advisory effectiveness: how much of what was recommended actually got
    invested, and how proposals break down by client decision.
    """
    totals = query_one("""
        SELECT
            COALESCE(SUM(recommended_amount), 0) as total_recommended,
            COALESCE(SUM(actual_amount), 0) as total_actual,
            COUNT(*) as total_recommendations,
            SUM(CASE WHEN actual_amount IS NOT NULL THEN 1 ELSE 0 END) as executed_count
        FROM proposal_recommendations
    """)
    decisions = query("""
        SELECT client_decision, COUNT(*) as count FROM proposals GROUP BY client_decision
    """)
    total_recommended = totals["total_recommended"] or 0
    total_actual = totals["total_actual"] or 0
    acceptance_rate = round((total_actual / total_recommended) * 100, 1) if total_recommended else 0

    return {
        "total_recommended_amount": total_recommended,
        "total_actual_amount": total_actual,
        "acceptance_rate_percent": acceptance_rate,
        "total_recommendation_lines": totals["total_recommendations"],
        "executed_lines": totals["executed_count"],
        "decision_breakdown": decisions,
    }
