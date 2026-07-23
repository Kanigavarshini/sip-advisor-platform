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

This module can be run directly (python services/ingestion.py) OR imported
and called as run_ingestion(raw_file_path) -- the upload route in
routes/dataset.py uses the latter so a new dataset can be uploaded live
through the dashboard, with no command line needed.
"""

import os
import sqlite3
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

# ---------------------------------------------------------------------------
# Paths -- always resolved relative to this file's own location, so this
# script works correctly no matter which folder you run it from.
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_THIS_DIR, "..", "data")

DEFAULT_RAW_FILE = os.path.join(DATA_DIR, "RupeeVyze_SIP_Mock_Dataset.xlsx")
DB_FILE = os.path.join(DATA_DIR, "sip_advisor.db")
ENRICHED_PREVIEW_FILE = os.path.join(DATA_DIR, "sip_advisor_enriched_preview.xlsx")

# "Today" for the purposes of computing due dates / missed status.
# Using the real current date so a freshly-uploaded dataset behaves correctly
# whenever it's uploaded, rather than a fixed demo date.
REFERENCE_DATE = datetime.now()

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

REQUIRED_COLUMNS = [
    "Sr.No", "UCC", "Investor Name", "Demat/Physical", "Folio No",
    "Bank Details", "SIP No", "SIP Submission Date", "Scheme",
    "SIP Start Date", "Start End Date",
]


class DatasetValidationError(Exception):
    """Raised when an uploaded file doesn't match the expected schema."""
    pass


def load_raw_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DatasetValidationError(
            f"Uploaded file is missing required column(s): {', '.join(missing)}"
        )
    return df


def simulate_amount(scheme: str, rng: random.Random) -> int:
    low, high = SCHEME_AMOUNT_RANGES.get(scheme, (1000, 5000))
    return rng.randrange(low, high + 1, 500)


def compute_next_due_date(sip_start: datetime, reference: datetime) -> datetime:
    day = sip_start.day
    candidate = reference.replace(day=1) + relativedelta(day=day)
    if candidate <= reference:
        candidate = candidate + relativedelta(months=1)
        candidate = candidate.replace(day=1) + relativedelta(day=day)
    return candidate


def simulate_missed_count(rng: random.Random) -> int:
    return rng.choices([0, 1, 2, 3, 4], weights=[60, 20, 10, 6, 4])[0]


def derive_status(end_date: datetime, missed_count: int, reference: datetime) -> str:
    if end_date <= reference:
        return "Completed"
    if missed_count >= 3:
        return "Missed"
    return "Active"


def derive_risk_level(missed_count: int) -> str:
    if missed_count >= 3:
        return "High"
    if missed_count >= 1:
        return "Medium"
    return "Low"


def enrich_row(r, rng: random.Random) -> dict:
    """
    Builds one enriched `sips` row (dict of DB column -> value) from one raw
    record `r` (a pandas Series, or a plain dict with the same raw column
    names). Shared by the bulk Excel ingestion path and the "add one client
    manually" path so both produce identically-shaped rows.
    """
    sip_start = datetime.strptime(str(r["SIP Start Date"]), DATE_FMT)
    sip_end = datetime.strptime(str(r["Start End Date"]), DATE_FMT)

    amount = simulate_amount(r["Scheme"], rng)
    missed_count = simulate_missed_count(rng)
    status = derive_status(sip_end, missed_count, REFERENCE_DATE)
    risk_level = derive_risk_level(missed_count)
    next_due = compute_next_due_date(sip_start, REFERENCE_DATE)
    days_to_due = (next_due - REFERENCE_DATE).days
    last_txn = next_due - relativedelta(months=1)

    return {
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
    }


def build_enriched_dataset(raw_df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = [enrich_row(r, rng) for _, r in raw_df.iterrows()]
    return pd.DataFrame(rows)


MANUAL_REQUIRED_FIELDS = [
    "UCC", "Investor Name", "Demat/Physical", "Folio No", "Bank Details",
    "SIP No", "SIP Submission Date", "Scheme", "SIP Start Date", "Start End Date",
]


def add_manual_client(fields: dict) -> dict:
    """
    Adds a single client/SIP record directly from the dashboard, without
    needing a full Excel re-upload. This APPENDS one row to the existing
    `sips` table (unlike a bulk Excel upload, which replaces the whole
    table), so the rest of the dataset is left untouched.
    """
    missing = [c for c in MANUAL_REQUIRED_FIELDS if not str(fields.get(c, "")).strip()]
    if missing:
        raise DatasetValidationError(f"Missing required field(s): {', '.join(missing)}")

    for date_field in ("SIP Submission Date", "SIP Start Date", "Start End Date"):
        try:
            datetime.strptime(str(fields[date_field]).strip(), DATE_FMT)
        except ValueError:
            raise DatasetValidationError(
                f"'{date_field}' must be in dd-mm-yyyy format (got '{fields[date_field]}')"
            )

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    existing = conn.execute("SELECT 1 FROM sips WHERE ucc = ?", (fields["UCC"],)).fetchone()
    if existing:
        conn.close()
        raise DatasetValidationError(f"A client with UCC '{fields['UCC']}' already exists")

    max_sr_row = conn.execute("SELECT MAX(sr_no) AS m FROM sips").fetchone()
    max_sr = (max_sr_row["m"] or 0) if max_sr_row else 0
    conn.close()

    # A fresh, non-deterministic seed per manual add so simulated amounts
    # don't collide with the deterministic bulk-upload sequence.
    rng = random.Random()
    record = {"Sr.No": max_sr + 1, **{k: str(fields[k]).strip() for k in MANUAL_REQUIRED_FIELDS}}
    enriched = enrich_row(record, rng)

    conn = sqlite3.connect(DB_FILE)
    columns = ", ".join(enriched.keys())
    placeholders = ", ".join("?" for _ in enriched)
    conn.execute(f"INSERT INTO sips ({columns}) VALUES ({placeholders})", tuple(enriched.values()))
    conn.commit()
    conn.close()

    return enriched


def save_to_sqlite(df: pd.DataFrame, db_path: str):
    conn = sqlite3.connect(db_path)
    df.to_sql("sips", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ucc ON sips(ucc)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_investor ON sips(investor_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_folio ON sips(folio_no)")
    conn.commit()
    conn.close()


def run_ingestion(raw_file_path: str = None) -> dict:
    """
    Runs the full ingestion pipeline and returns a summary dict.
    Used both by the CLI entrypoint (main) and by the /api/dataset/upload
    route, so uploading a new dataset through the dashboard does exactly
    the same thing as running this script manually.
    """
    raw_file_path = raw_file_path or DEFAULT_RAW_FILE
    raw_df = load_raw_data(raw_file_path)
    enriched_df = build_enriched_dataset(raw_df)
    save_to_sqlite(enriched_df, DB_FILE)
    enriched_df.to_excel(ENRICHED_PREVIEW_FILE, index=False)

    return {
        "records_loaded": len(raw_df),
        "status_breakdown": enriched_df["status"].value_counts().to_dict(),
        "risk_breakdown": enriched_df["risk_level"].value_counts().to_dict(),
        "due_soon_count": int(enriched_df["needs_reminder"].sum()),
    }


def main():
    summary = run_ingestion()
    print(f"Loaded {summary['records_loaded']} raw records")
    print(f"Wrote enriched dataset to {DB_FILE} (table: sips)")
    print(f"Preview Excel written to {ENRICHED_PREVIEW_FILE}")
    print("\nStatus breakdown:", summary["status_breakdown"])
    print("Risk breakdown:", summary["risk_breakdown"])
    print(f"Clients needing reminder in next {REMINDER_DAYS_BEFORE} days: "
          f"{summary['due_soon_count']}")


if __name__ == "__main__":
    main()
