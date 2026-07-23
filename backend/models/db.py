"""
db.py
-----
Simple SQLite connection helper shared by all routes/services.
Swap this module out later to point at MongoDB without changing route code,
if you migrate as per the original 3-tier architecture (vector store /
prediction cache / metadata) discussed for the production version.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sip_advisor.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query(sql, params=()):
    conn = get_connection()
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def init_proposal_tables():
    """
    Creates the proposal-related tables if they don't already exist.
    Kept separate from `sips` (which gets replaced wholesale on every
    dataset upload/ingestion run) so proposals -- real advisory work created
    by RMs -- are never wiped out by a dataset refresh.
    """
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proposals (
            proposal_id TEXT PRIMARY KEY,
            ucc TEXT NOT NULL,
            proposal_date TEXT NOT NULL,
            created_by TEXT NOT NULL,
            version_number INTEGER NOT NULL DEFAULT 1,
            parent_proposal_id TEXT,
            purpose TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Draft',
            client_decision TEXT NOT NULL DEFAULT 'Pending',
            decision_reason TEXT,
            internal_notes TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proposal_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            scheme_name TEXT NOT NULL,
            investment_type TEXT NOT NULL,
            recommended_amount REAL NOT NULL,
            actual_amount REAL,
            FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS proposal_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_proposal_ucc ON proposals(ucc)")
    conn.commit()
    conn.close()


def init_leads_tables():
    """
    Creates the Leads module tables (PRD Section 4).
    Kept separate from `sips` for the same reason as proposals: leads are
    real pipeline data created by RMs/marketing and must never be wiped out
    by a dataset (re-)upload.
    """
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            lead_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            source TEXT NOT NULL DEFAULT 'Other',
            referred_by_ucc TEXT,
            status TEXT NOT NULL DEFAULT 'New',
            priority TEXT NOT NULL DEFAULT 'Warm',
            assigned_to TEXT,
            expected_investment_amount REAL,
            interested_scheme TEXT,
            next_follow_up_date TEXT,
            lost_reason TEXT,
            converted_ucc TEXT,
            converted_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            description TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (lead_id) REFERENCES leads(lead_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (lead_id) REFERENCES leads(lead_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lead_status ON leads(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lead_priority ON leads(priority)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lead_activity_lead ON lead_activities(lead_id)")
    conn.commit()
    conn.close()


def init_client_extension_tables():
    """
    Creates the Client 360 extension tables (PRD Section 5) that hold
    everything the raw `sips` ingestion table doesn't: family info, goals,
    notes, communication history and referrals. Keyed by `ucc` so they
    survive dataset re-uploads just like proposals/leads do.
    """
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS client_profiles (
            ucc TEXT PRIMARY KEY,
            family_members TEXT,
            financial_goals TEXT,
            risk_notes TEXT,
            quarterly_review_date TEXT,
            annual_review_date TEXT,
            last_review_notes TEXT,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS client_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ucc TEXT NOT NULL,
            note TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS client_communications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ucc TEXT NOT NULL,
            channel TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS client_referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ucc TEXT NOT NULL,
            referred_name TEXT NOT NULL,
            referred_phone TEXT,
            lead_id TEXT,
            status TEXT NOT NULL DEFAULT 'New',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_ucc ON client_notes(ucc)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comms_ucc ON client_communications(ucc)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_referrals_ucc ON client_referrals(ucc)")
    conn.commit()
    conn.close()
