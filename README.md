# AI SIP Advisor Platform (Prototype)

A centralized, AI-assisted SIP management dashboard built for RupeeVyze,
replacing manual Excel-based workflows. Built as per the problem statement
covering individual client reports, custom date-range reports, configurable
reminders, a Client 360 view, a rule-based AI recommendation engine, an AI
assistant, and analytics.

## Project structure

```
sip-advisor-platform/
├── backend/
│   ├── app.py                     # Flask entrypoint (also serves the frontend)
│   ├── requirements.txt
│   ├── data/
│   │   ├── RupeeVyze_SIP_Mock_Dataset.xlsx   # original mock dataset (100 clients)
│   │   ├── sip_advisor.db                    # enriched SQLite database
│   │   └── sip_advisor_enriched_preview.xlsx # enriched data, for inspection
│   ├── models/
│   │   └── db.py                  # SQLite connection helper
│   ├── services/
│   │   ├── ingestion.py           # reads raw Excel, derives fields, builds the DB
│   │   ├── ai_engine.py           # rule-based recommendation engine (Solution 7)
│   │   ├── report_generator.py    # Excel/PDF report builder (Solutions 3, 4, 5)
│   │   └── reminder_service.py    # configurable reminder logic (Solution 6)
│   ├── routes/
│   │   ├── clients.py             # search + Client 360 (Solutions 1, 2)
│   │   ├── reports.py             # report generation endpoints
│   │   ├── reminders.py           # reminder endpoints
│   │   ├── analytics.py           # dashboard stats + chart data (Solutions 1, 9)
│   │   └── assistant.py           # AI Assistant query router (Solution 8)
│   └── reports_output/            # generated reports land here
│
└── frontend/
    ├── index.html                 # dashboard shell (all 6 tabs)
    ├── css/style.css
    └── js/app.js                  # tab logic + API calls + charts
```

## How the raw dataset was enriched

The original mock dataset only has registration-level fields (UCC, Investor
Name, Folio No, Bank Details, SIP No, Scheme, SIP Start/End dates). It does
**not** contain amount, transaction history, or missed-payment status.

`services/ingestion.py` derives the following fields on top of the real data,
clearly for prototype purposes (a production system would pull these from an
actual transactions/ledger table):

| Field | How it's derived |
|---|---|
| `sip_amount` | Simulated within a realistic range per scheme |
| `next_due_date` | Computed from the day-of-month of SIP Start Date |
| `missed_count` | Simulated (weighted toward 0) |
| `status` | Active / Missed / Completed, rule-based on missed_count and end date |
| `risk_level` | Low / Medium / High, rule-based on missed_count |
| `is_premium` | True if sip_amount ≥ ₹5000 (configurable threshold) |

Re-run `python backend/services/ingestion.py` any time to regenerate the
database (e.g. after changing the reminder window or premium threshold).

## Setup & run

```bash
cd backend
pip install -r requirements.txt

# (Only needed once, or after changing enrichment rules)
python services/ingestion.py

# Start the server
python app.py
```

Then open **http://localhost:5000** in your browser. The Flask server serves
both the API and the dashboard, so this is the only command you need.

## Dashboard tabs (mapped to the problem statement)

| Tab | Solves |
|---|---|
| Overview | Solution 1 — centralized dashboard |
| Client 360 | Solution 2 — search by name/UCC/folio, full profile |
| Reports | Solutions 3, 4, 5 — individual, combined, and custom date-range reports (Excel/PDF) |
| Reminders | Solutions 3, 6 — configurable days-before-due reminder list |
| Analytics | Solution 9 — status, risk, scheme, and trend charts |
| AI Assistant | Solution 8 — natural-language style queries over the dataset |

## Configuration knobs

- Reminder window: change on the Reminders tab (default 2 days), or edit
  `DEFAULT_REMINDER_DAYS` in `services/reminder_service.py`
- Premium threshold: `PREMIUM_THRESHOLD` in `services/ingestion.py`
- Reference "today" for testing: `REFERENCE_DATE` in `services/ingestion.py`

## Next steps for a production version

- Replace simulated fields with real transaction/ledger data
- Swap SQLite for MongoDB (3-tier: vector store / prediction cache / metadata)
- Replace the rule-based AI engine with a trained ML model or LLM
- Add authentication for RM logins
- Wire reminder sending to actual SMS/Email/WhatsApp gateways
