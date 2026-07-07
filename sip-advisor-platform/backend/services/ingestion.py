"""
ingestion.py
------------
Phase 1: Data layer.

Reads the raw RupeeVyze SIP mock dataset (registration-level fields only)
and builds an enriched dataset that the rest of the platform (API, AI engine,
reports, reminders, analytics) will read from.

Raw columns (from the source Excel):
    Sr.No, UCC, Investor Name, Demat/Physical, Folio No, Bank Details,
    SIP No, SIP Submission Date, Scheme, SIP Start Date, Start End Date

Derived columns added here (clearly flagged as SIMULATED for the prototype,
since the real system would pull these from a transactions/ledger table):
    sip_amount          - monthly SIP installment amount
    frequency           - fixed as "Monthly"
    next_due_date       - next monthly due date after REFERENCE_DATE, based on
                           the day-of-month of SIP Start Date
    missed_count        - number of missed installments (simulated)
    status              - Active / Missed / Completed
                           (Completed if Start End Date has already passed)
    risk_level          - Low / Medium / High, rule-based on missed_count
    is_premium          - True if sip_amount >= PREMIUM_THRESHOLD
    last_transaction_date - most recent successful installment date (simulated)

Output: writes an enriched SQLite database at backend/data/sip_advisor.db
with a single `sips` table, plus a CSV/Excel copy for quick inspection.
"""

import sqlite3
import random
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
import os
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_FILE = os.path.join(_THIS_DIR, "..", "data", "RupeeVyze_SIP_Mock_Dataset.xlsx")
DB_FILE = os.path.join(_THIS_DIR, "..", "data", "sip_advisor.db")
ENRICHED_PREVIEW_FILE = os.path.join(_THIS_DIR, "..", "data", "sip_advisor_enriched_preview.xlsx")

# "Today" for the purposes of computing due dates / missed status.
# In production this would just be datetime.now(). Kept as a constant here
# so the prototype behaves consistently no matter when it's run/demoed.
REFERENCE_DATE = datetime(2026, 7, 5)

REMINDER_DAYS_BEFORE = 2          # Solution 3 / 6: configurable reminder window
PREMIUM_THRESHOLD = 5000          # Solution 7: premium client rule
DATE_FMT = "%d-%m-%Y"

SCHEME_AMOUNT_RANGES = {
    # Rough realistic monthly SIP ranges per scheme, purely for simulation
    "Axis Midcap Fund": (2000, 8000),
    "ICICI Prudential Bluechip Fund": (1000, 6000),
    "Nippon India Growth Fund": (1500, 7000),
    "Parag Parikh Flexi Cap Fund": (2000, 10000),
    "HDFC Flexi Cap Fund": (1000, 5000),
    "Mirae Asset Large Cap Fund": (1500, 6000),
    "SBI Small Cap Fund": (2000, 9000),
}


def load_raw_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]
    return df


def simulate_amount(scheme: str, rng: random.Random) -> int:
    low, high = SCHEME_AMOUNT_RANGES.get(scheme, (1000, 5000))
    # round to nearest 500 for realistic SIP amounts
    return rng.randrange(low, high + 1, 500)


def compute_next_due_date(sip_start: datetime, reference: datetime) -> datetime:
    """Next monthly due date on the same day-of-month as sip_start, after reference."""
    day = sip_start.day
    candidate = reference.replace(day=1) + relativedelta(day=day)
    if candidate <= reference:
        candidate = candidate + relativedelta(months=1)
        candidate = candidate.replace(day=1) + relativedelta(day=day)
    return candidate


def simulate_missed_count(rng: random.Random) -> int:
    # Weighted so most clients have 0 missed SIPs, a few have several
    return rng.choices([0, 1, 2, 3, 4], weights=[60, 20, 10, 6, 4])[0]


def derive_status(end_date: datetime, missed_count: int, reference: datetime) -> str:
    if end_date <= reference:
        return "Completed"
    if missed_count >= 3:
        return "Missed"
    return "Active"


def derive_risk_level(missed_count: int) -> str:
    # Rule-based AI engine logic (Solution 7)
    if missed_count >= 3:
        return "High"
    if missed_count >= 1:
        return "Medium"
    return "Low"


def build_enriched_dataset(raw_df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []

    for _, r in raw_df.iterrows():
        sip_start = datetime.strptime(r["SIP Start Date"], DATE_FMT)
        sip_end = datetime.strptime(r["Start End Date"], DATE_FMT)

        amount = simulate_amount(r["Scheme"], rng)
        missed_count = simulate_missed_count(rng)
        status = derive_status(sip_end, missed_count, REFERENCE_DATE)
        risk_level = derive_risk_level(missed_count)
        next_due = compute_next_due_date(sip_start, REFERENCE_DATE)
        days_to_due = (next_due - REFERENCE_DATE).days
        last_txn = next_due - relativedelta(months=1)

        rows.append({
            "sr_no": r["Sr.No"],
            "ucc": r["UCC"],
            "investor_name": r["Investor Name"],
            "holding_type": r["Demat/Physical"],
            "folio_no": r["Folio No"],
            "bank_details": r["Bank Details"],
            "sip_no": r["SIP No"],
            "sip_submission_date": r["SIP Submission Date"],
            "scheme": r["Scheme"],
            "sip_start_date": r["SIP Start Date"],
            "sip_end_date": r["Start End Date"],
            # --- derived / simulated fields below ---
            "sip_amount": amount,
            "frequency": "Monthly",
            "next_due_date": next_due.strftime(DATE_FMT),
            "days_to_due": days_to_due,
            "missed_count": missed_count,
            "status": status,
            "risk_level": risk_level,
            "is_premium": amount >= PREMIUM_THRESHOLD,
            "last_transaction_date": last_txn.strftime(DATE_FMT),
            "needs_reminder": 0 <= days_to_due <= REMINDER_DAYS_BEFORE,
        })

    return pd.DataFrame(rows)


def save_to_sqlite(df: pd.DataFrame, db_path: str):
    conn = sqlite3.connect(db_path)
    df.to_sql("sips", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ucc ON sips(ucc)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_investor ON sips(investor_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_folio ON sips(folio_no)")
    conn.commit()
    conn.close()


def main():
    raw_df = load_raw_data(RAW_FILE)
    enriched_df = build_enriched_dataset(raw_df)
    save_to_sqlite(enriched_df, DB_FILE)
    enriched_df.to_excel(ENRICHED_PREVIEW_FILE, index=False)

    print(f"Loaded {len(raw_df)} raw records")
    print(f"Wrote enriched dataset to {DB_FILE} (table: sips)")
    print(f"Preview Excel written to {ENRICHED_PREVIEW_FILE}")
    print("\nStatus breakdown:")
    print(enriched_df["status"].value_counts())
    print("\nRisk breakdown:")
    print(enriched_df["risk_level"].value_counts())
    print(f"\nClients needing reminder in next {REMINDER_DAYS_BEFORE} days: "
          f"{enriched_df['needs_reminder'].sum()}")


if __name__ == "__main__":
    main()
