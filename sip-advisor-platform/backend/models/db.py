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
