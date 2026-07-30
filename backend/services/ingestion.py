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
import re
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

# Columns present in the *enriched* dataset this platform itself produces
# (e.g. sip_advisor_enriched_preview.xlsx, or a full DB export). If someone
# re-uploads that file instead of the original raw mock dataset, we should
# still accept it rather than failing on "missing required columns".
ENRICHED_COLUMNS = [
    "sr_no", "ucc", "investor_name", "holding_type", "folio_no", "bank_details",
    "sip_no", "sip_submission_date", "scheme", "sip_start_date", "sip_end_date",
    "sip_amount", "frequency", "next_due_date", "days_to_due", "missed_count",
    "status", "risk_level", "is_premium", "last_transaction_date", "needs_reminder",
]


class DatasetValidationError(Exception):
    """Raised when an uploaded file doesn't match either supported schema."""
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


def load_dataset_flexible(path: str):
    """
    Reads an uploaded Excel file and figures out which of the three
    supported schemas it's in:
      - "client_report" -> a real RM-exported "SIP Status Report" (e.g.
                            SIPStatusReport_....xls straight from the AMC/RTA
                            portal) -- has a title row, slightly different
                            column names, slash dates, and real amounts.
      - "raw"      -> the original RupeeVyze_SIP_Mock_Dataset.xlsx style file
                       (Sr.No, UCC, Investor Name, ... Start End Date)
      - "enriched" -> a file this platform already produced (e.g. someone
                       re-uploads sip_advisor_enriched_preview.xlsx, or a
                       full export of the sips table)
    Returns (kind, dataframe). Raises DatasetValidationError if none match.
    """
    client_df = load_client_report(path)
    if client_df is not None:
        return "client_report", client_df

    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    columns = set(df.columns)

    if set(REQUIRED_COLUMNS).issubset(columns):
        return "raw", df
    if set(ENRICHED_COLUMNS).issubset(columns):
        return "enriched", df

    missing_raw = [c for c in REQUIRED_COLUMNS if c not in columns]
    raise DatasetValidationError(
        "This file doesn't match a supported format. Upload either the "
        "original SIP dataset (with columns like UCC, Investor Name, "
        f"Scheme, etc. -- missing: {', '.join(missing_raw)}), a client SIP "
        "Status Report, or a dataset previously exported from this "
        "dashboard."
    )


# ---------------------------------------------------------------------------
# Real client "SIP Status Report" support (e.g. SIPStatusReport_*.xls) --
# these come straight from the AMC/RTA portal and have a title row above the
# real header, slightly different column names ("Sr No.", "Folio No.",
# "SIP End Date"), slash-formatted dates, and real installment amounts/status
# that the mock dataset doesn't have.
# ---------------------------------------------------------------------------

_COLUMN_ALIASES = {
    "sr no": "Sr.No",
    "ucc": "UCC",
    "investor name": "Investor Name",
    "demat physical": "Demat/Physical",
    "folio no": "Folio No",
    "bank details": "Bank Details",
    "sip no": "SIP No",
    "sip submission date": "SIP Submission Date",
    "scheme": "Scheme",
    "sip start date": "SIP Start Date",
    "sip end date": "Start End Date",
    "start end date": "Start End Date",
    "no of installments": "No of Installments",
    "frequency": "Frequency",
    "investment amt": "Investment Amt",
    "installment amt": "Installment Amt",
    "sip status": "SIP Status",
    "sip stop cancellation date": "SIP Stop/Cancellation Date",
    "reason": "Reason",
    "is top up sip": "Is Top Up SIP",
}


def _normalize_key(value) -> str:
    s = str(value).strip().lower()
    s = s.replace("/", " ")
    s = re.sub(r"[.\s]+", " ", s).strip()
    return s


def _rename_report_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_COLUMN_ALIASES.get(_normalize_key(c), str(c).strip()) for c in df.columns]
    return df


def _find_header_row(headerless_df: pd.DataFrame, max_scan: int = 10):
    """Scans the first few rows for the one that looks like the real column
    header (has both a UCC-like and an Investor-Name-like cell), to skip
    past a report title row such as 'SIP Status Report'."""
    for i in range(min(max_scan, len(headerless_df))):
        row_keys = [_normalize_key(v) for v in headerless_df.iloc[i].tolist()]
        if "ucc" in row_keys and "investor name" in row_keys:
            return i
    return None


def _normalize_date_cell(value) -> str:
    """Converts an Excel datetime, dd/mm/yyyy, or dd-mm-yyyy cell into the
    platform's canonical dd-mm-yyyy string. Returns "" for blank/placeholder
    cells (NaN, '-', ' ')."""
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime(DATE_FMT)
    s = str(value).strip()
    if not s or s in ("-", "nan", "NaT"):
        return ""
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).strftime(DATE_FMT)
        except ValueError:
            continue
    return ""


def load_client_report(path: str):
    """
    Reads a real RM-exported SIP Status Report if the file matches that
    shape; returns None (not an error) if it doesn't, so the caller can fall
    through to trying the other two formats.
    """
    try:
        headerless = pd.read_excel(path, header=None)
    except Exception:
        return None

    header_row = _find_header_row(headerless)
    if header_row is None:
        return None

    df = pd.read_excel(path, header=header_row)
    df = _rename_report_columns(df)

    if "UCC" not in df.columns or set(REQUIRED_COLUMNS) - set(df.columns):
        return None

    # Drop footer/summary rows (e.g. a trailing "Total" row) and any fully
    # blank rows -- real reports append a totals line with no UCC.
    df = df[df["UCC"].notna()].copy()
    df = df[df["UCC"].astype(str).str.strip() != ""].copy()
    if df.empty:
        return None

    # UCC often comes through as a float (e.g. 4405693.0) since the column
    # has no other non-numeric values for pandas to infer a string dtype
    # from. Clean it up to a plain string id.
    def _clean_ucc(v):
        s = str(v).strip()
        if s.endswith(".0"):
            s = s[:-2]
        return s

    df["UCC"] = df["UCC"].apply(_clean_ucc)

    for date_col in ("SIP Submission Date", "SIP Start Date", "Start End Date"):
        df[date_col] = df[date_col].apply(_normalize_date_cell)
    if "SIP Stop/Cancellation Date" in df.columns:
        df["SIP Stop/Cancellation Date"] = df["SIP Stop/Cancellation Date"].apply(_normalize_date_cell)

    # Drop any row still missing a usable start/end date after normalization
    # -- keeps one bad row from failing the whole upload.
    df = df[(df["SIP Start Date"] != "") & (df["Start End Date"] != "")].copy()

    df["Sr.No"] = range(1, len(df) + 1)
    df = df.reset_index(drop=True)
    return df


def enrich_client_report_row(r, rng: random.Random) -> dict:
    """
    Like enrich_row(), but for a real SIP Status Report row: uses the real
    installment amount, frequency, and stop/cancellation info when present,
    only falling back to simulation for fields the report genuinely doesn't
    contain (e.g. individual missed-installment history).
    """
    sip_start = datetime.strptime(str(r["SIP Start Date"]), DATE_FMT)
    sip_end = datetime.strptime(str(r["Start End Date"]), DATE_FMT)

    real_amount = pd.to_numeric(r.get("Installment Amt"), errors="coerce")
    amount = int(real_amount) if pd.notna(real_amount) and real_amount > 0 else simulate_amount(r["Scheme"], rng)

    frequency = str(r.get("Frequency") or "").strip().title() or "Monthly"

    stop_date = str(r.get("SIP Stop/Cancellation Date") or "").strip()
    report_status = str(r.get("SIP Status") or "").strip().lower()
    was_stopped = bool(stop_date) or "cancel" in report_status or "reject" in report_status

    missed_count = 4 if was_stopped else simulate_missed_count(rng)
    status = derive_status(sip_end, missed_count, REFERENCE_DATE)
    if was_stopped and status != "Completed":
        status = "Missed"
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
        "sip_no": _ensure_sip_no(r["SIP No"], r["UCC"], r["Sr.No"]),
        "sip_submission_date": r["SIP Submission Date"],
        "scheme": r["Scheme"],
        "sip_start_date": r["SIP Start Date"],
        "sip_end_date": r["Start End Date"],
        "sip_amount": amount,
        "frequency": frequency,
        "next_due_date": next_due.strftime(DATE_FMT),
        "days_to_due": days_to_due,
        "missed_count": missed_count,
        "status": status,
        "risk_level": risk_level,
        "is_premium": amount >= PREMIUM_THRESHOLD,
        "last_transaction_date": last_txn.strftime(DATE_FMT),
        "needs_reminder": 0 <= days_to_due <= REMINDER_DAYS_BEFORE,
    }


def build_enriched_dataset_from_client_report(df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = [enrich_client_report_row(r, rng) for _, r in df.iterrows()]
    return pd.DataFrame(rows)


def normalize_enriched_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans up a re-uploaded enriched dataset so it saves into `sips` with
    the exact same column order/types the bulk-ingestion path produces --
    no re-simulation needed, since the amounts/status/risk are already there.
    """
    out = df[ENRICHED_COLUMNS].copy()

    def as_date_str(v):
        if hasattr(v, "strftime"):
            return v.strftime(DATE_FMT)
        return str(v).strip()

    for col in ("sip_submission_date", "sip_start_date", "sip_end_date",
                "next_due_date", "last_transaction_date"):
        out[col] = out[col].apply(as_date_str)

    out["sr_no"] = pd.to_numeric(out["sr_no"], errors="coerce").fillna(0).astype(int)
    out["sip_amount"] = pd.to_numeric(out["sip_amount"], errors="coerce").fillna(0).round().astype(int)
    out["days_to_due"] = pd.to_numeric(out["days_to_due"], errors="coerce").fillna(0).astype(int)
    out["missed_count"] = pd.to_numeric(out["missed_count"], errors="coerce").fillna(0).astype(int)
    out["is_premium"] = out["is_premium"].astype(bool)
    out["needs_reminder"] = out["needs_reminder"].astype(bool)

    for col in ("ucc", "investor_name", "holding_type", "folio_no", "bank_details",
                "sip_no", "scheme", "frequency", "status", "risk_level"):
        out[col] = out[col].astype(str).str.strip()

    out["sip_no"] = [
        _ensure_sip_no(sip_no, ucc, sr_no)
        for sip_no, ucc, sr_no in zip(out["sip_no"], out["ucc"], out["sr_no"])
    ]

    return out


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


def _ensure_sip_no(value, ucc, sr_no) -> str:
    """
    Guarantees a non-blank sip_no, since it's used as the upsert key when
    appending an upload to the existing dataset. Real client reports
    sometimes leave this blank/'-' for a row; without a fallback, several
    such rows would all collide under the same blank key.
    """
    s = str(value).strip()
    if s and s.lower() not in ("nan", "none", "-"):
        return s
    return f"AUTO-{ucc}-{sr_no}"


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
        "sip_no": _ensure_sip_no(r["SIP No"], r["UCC"], r["Sr.No"]),
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
    "Investor Name", "Demat/Physical", "Bank Details",
    "Scheme", "SIP Submission Date", "SIP Start Date", "Start End Date",
]

# These are genuinely useful but not always known at the moment an RM is
# registering a client on the spot -- auto-generated if left blank.
MANUAL_OPTIONAL_FIELDS = ["UCC", "Folio No", "SIP No"]


def _generate_ucc() -> str:
    return f"NEWCL{random.randint(100000, 999999)}"


def _generate_folio_no() -> str:
    return f"AUTO-{random.randint(10000000, 99999999)}"


def _generate_sip_no() -> str:
    return f"AUTO-SIP-{random.randint(100000, 999999)}"


def add_manual_client(fields: dict) -> dict:
    """
    Adds a single client/SIP record directly from the dashboard, without
    needing a full Excel re-upload. This APPENDS one row to the existing
    `sips` table (unlike a bulk Excel upload, which replaces the whole
    table), so the rest of the dataset is left untouched.

    UCC, Folio No, and SIP No are optional -- a client can already exist
    with other SIPs under the same UCC (one investor can hold several SIPs),
    and if UCC itself isn't known yet it's auto-generated so the record can
    still be created and reconciled with the real UCC later.
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

    ucc = str(fields.get("UCC", "")).strip() or _generate_ucc()
    folio_no = str(fields.get("Folio No", "")).strip() or _generate_folio_no()
    sip_no = str(fields.get("SIP No", "")).strip() or _generate_sip_no()

    # Only sip_no needs to be unique -- a client (UCC) can hold multiple SIPs.
    existing = conn.execute("SELECT 1 FROM sips WHERE sip_no = ?", (sip_no,)).fetchone()
    if existing:
        conn.close()
        raise DatasetValidationError(f"A SIP with SIP No '{sip_no}' already exists")

    max_sr_row = conn.execute("SELECT MAX(sr_no) AS m FROM sips").fetchone()
    max_sr = (max_sr_row["m"] or 0) if max_sr_row else 0
    conn.close()

    # A fresh, non-deterministic seed per manual add so simulated amounts
    # don't collide with the deterministic bulk-upload sequence.
    rng = random.Random()
    record = {
        "Sr.No": max_sr + 1,
        "UCC": ucc,
        "Investor Name": str(fields["Investor Name"]).strip(),
        "Demat/Physical": str(fields["Demat/Physical"]).strip(),
        "Folio No": folio_no,
        "Bank Details": str(fields["Bank Details"]).strip(),
        "SIP No": sip_no,
        "SIP Submission Date": str(fields["SIP Submission Date"]).strip(),
        "Scheme": str(fields["Scheme"]).strip(),
        "SIP Start Date": str(fields["SIP Start Date"]).strip(),
        "Start End Date": str(fields["Start End Date"]).strip(),
    }
    enriched = enrich_row(record, rng)

    conn = sqlite3.connect(DB_FILE)
    columns = ", ".join(enriched.keys())
    placeholders = ", ".join("?" for _ in enriched)
    conn.execute(f"INSERT INTO sips ({columns}) VALUES ({placeholders})", tuple(enriched.values()))
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sip_no ON sips(sip_no)")
    conn.commit()
    conn.close()

    return enriched


def save_to_sqlite(df: pd.DataFrame, db_path: str, mode: str = "append"):
    """
    mode="replace": wipes and replaces the whole `sips` table. Only used by
        the CLI baseline reset (python services/ingestion.py), to (re)seed a
        clean demo dataset.
    mode="append":  used by every dashboard upload. Each row is *upserted*
        by `sip_no` -- if a SIP with that sip_no already exists, it's
        updated in place; otherwise it's added as a new row. This means
        uploading a second Excel file (even for a different batch of
        clients) ADDS to the existing dataset instead of wiping it, and
        re-uploading the same file twice doesn't create duplicates.
    """
    conn = sqlite3.connect(db_path)

    if mode == "replace" or not _table_exists(conn):
        df.to_sql("sips", conn, if_exists="replace", index=False)
    else:
        # Offset sr_no so newly-added rows continue numbering after the
        # existing dataset, instead of restarting at 1 and colliding.
        max_sr_row = conn.execute("SELECT MAX(sr_no) AS m FROM sips").fetchone()
        max_sr = (max_sr_row[0] or 0) if max_sr_row else 0
        df = df.copy()
        df["sr_no"] = range(max_sr + 1, max_sr + 1 + len(df))

        cols = list(df.columns)
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(cols)
        for _, row in df.iterrows():
            sip_no = row["sip_no"]
            conn.execute("DELETE FROM sips WHERE sip_no = ?", (sip_no,))
            conn.execute(f"INSERT INTO sips ({col_list}) VALUES ({placeholders})", tuple(row[c] for c in cols))

    conn.execute("CREATE INDEX IF NOT EXISTS idx_ucc ON sips(ucc)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_investor ON sips(investor_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_folio ON sips(folio_no)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sip_no ON sips(sip_no)")
    conn.commit()
    conn.close()


def _table_exists(conn) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='sips'"
    ).fetchone()
    return row is not None


def run_ingestion(raw_file_path: str = None, mode: str = "append") -> dict:
    """
    Runs the full ingestion pipeline and returns a summary dict.

    mode="append" (default, used by the /api/dataset/upload route): the
        uploaded file's rows are added to whatever's already in the `sips`
        table (upserted by sip_no), so uploading a second Excel file does
        NOT erase the first one.
    mode="replace" (used by the CLI baseline reset, `python
        services/ingestion.py`): wipes and reloads a clean demo dataset.

    Accepts any of the three supported upload formats -- raw mock dataset,
    a real client SIP Status Report, or a previously exported enriched
    dataset -- detected automatically via load_dataset_flexible().
    """
    raw_file_path = raw_file_path or DEFAULT_RAW_FILE
    kind, df = load_dataset_flexible(raw_file_path)

    if kind == "raw":
        enriched_df = build_enriched_dataset(df)
    elif kind == "client_report":
        enriched_df = build_enriched_dataset_from_client_report(df)
    else:
        enriched_df = normalize_enriched_dataset(df)

    save_to_sqlite(enriched_df, DB_FILE, mode=mode)

    # Preview export always reflects the FULL current dataset (not just the
    # rows from this upload), since uploads accumulate rather than replace.
    conn = sqlite3.connect(DB_FILE)
    full_df = pd.read_sql("SELECT * FROM sips ORDER BY sr_no", conn)
    conn.close()
    full_df.to_excel(ENRICHED_PREVIEW_FILE, index=False)

    return {
        "records_loaded": len(enriched_df),
        "total_records": len(full_df),
        "status_breakdown": full_df["status"].value_counts().to_dict(),
        "risk_breakdown": full_df["risk_level"].value_counts().to_dict(),
        "due_soon_count": int(full_df["needs_reminder"].sum()),
    }


def main():
    summary = run_ingestion(mode="replace")
    print(f"Loaded {summary['records_loaded']} raw records")
    print(f"Wrote enriched dataset to {DB_FILE} (table: sips)")
    print(f"Preview Excel written to {ENRICHED_PREVIEW_FILE}")
    print("\nStatus breakdown:", summary["status_breakdown"])
    print("Risk breakdown:", summary["risk_breakdown"])
    print(f"Clients needing reminder in next {REMINDER_DAYS_BEFORE} days: "
          f"{summary['due_soon_count']}")


if __name__ == "__main__":
    main()
