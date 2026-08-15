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
│   │   └── db.py                  # SQLite connection helper + proposal/lead/client-extension table setup
│   ├── services/
│   │   ├── ingestion.py           # reads raw Excel, derives fields, builds the DB
│   │   ├── ai_engine.py           # rule-based recommendation engine (Solution 7)
│   │   ├── report_generator.py    # Excel/PDF report builder (Solutions 3, 4, 5)
│   │   ├── reminder_service.py    # configurable reminder logic (Solution 6)
│   │   ├── proposal_engine.py     # Proposal Management business logic
│   │   └── lead_engine.py         # Leads business rules: scoring & conversion (PRD Section 4)
│   ├── routes/
│   │   ├── clients.py             # search + Client 360 core profile (Solutions 1, 2)
│   │   ├── client_profile.py      # Client 360 extensions: family/goals, notes,
│   │   │                          #   communication history, referrals (PRD Section 5)
│   │   ├── reports.py             # report generation endpoints
│   │   ├── reminders.py           # reminder endpoints
│   │   ├── analytics.py           # dashboard stats + chart data (Solutions 1, 9)
│   │   ├── assistant.py           # AI Assistant query router (Solution 8)
│   │   ├── dataset.py             # live dataset upload (Solution 10, no code/API needed)
│   │   ├── proposals.py           # Proposal Management API
│   │   └── leads.py               # Leads module API: pipeline, activities, conversion (PRD Section 4)
│   └── reports_output/            # generated reports land here
│
└── frontend/
    ├── index.html                 # dashboard shell (Overview, Leads, Client 360, Reports, Reminders, Analytics, AI Assistant)
    ├── css/style.css
    └── js/app.js                  # tab logic + API calls + charts + proposals/leads/client-extension UI
```


## Leads module (RVOS PRD Section 4)

A brand-new pipeline module, added as its own nav tab (Leads), covering the
full lead lifecycle end to end:

- **Creation & qualification**: name, phone, email, source (Referral,
  Walk-in, Social Media, Website, Cold Call, Event, Other), interested
  scheme, expected investment amount.
- **Status & priority ("temperature")**: status moves through
  New → Contacted → Qualified → Proposal Sent → Negotiation → Converted /
  Lost. Priority is Hot / Warm / Cold. Marking a lead Lost requires a
  reason, matching the same accountability pattern used for rejected
  proposals.
- **Follow-up management**: a `next_follow_up_date` per lead, surfaced on
  the Overview tab ("Leads needing attention") whenever it's overdue.
- **Activity timeline**: every call, meeting, email, WhatsApp touch, and
  status change is logged with who/when, exactly like the audit trail
  clients already had for proposals.
- **Documents**: KYC / ID proof / other file upload-download per lead,
  stored under `backend/data/lead_documents/`.
- **AI recommendation**: `services/lead_engine.py` scores each lead with a
  transparent, explainable next-best-action (e.g. "Hot lead, not yet
  contacted → Contact within 24 hours"; "Follow-up overdue → Call today"),
  the same rule-based style as the existing Client 360 recommendation
  engine — no black-box model, easy to demo, swappable later.
- **Referral tracking**: referrals can be logged directly from a client's
  Client 360 profile, which (optionally) auto-creates a linked Lead with
  `source = Referral` so the pipeline and Client 360 stay in sync.
- **Conversion to Client**: a Qualified/Negotiation lead can be converted
  in one click. This inserts a minimal record into the `sips` table
  (folio/bank fields marked "Pending KYC" until back-office onboarding
  completes and the next dataset upload reconciles the real values) and
  marks the lead `Converted`, linking it to the new `ucc`.

Lead data lives in its own tables (`leads`, `lead_activities`,
`lead_documents`), separate from `sips`, so re-uploading a dataset never
touches the pipeline — the same pattern used for Proposals.

## Client 360 extensions (RVOS PRD Section 5)

The Client 360 profile now includes four additional sections beneath
Proposals, each backed by its own table (`client_profiles`, `client_notes`,
`client_communications`, `client_referrals`) so they, too, survive dataset
re-uploads:

- **Family & financial goals**: editable list of family members and
  financial goals (goal, target amount, target year), plus free-text risk
  notes and quarterly/annual review dates.
- **Notes**: a running log of internal, advisor-only notes.
- **Communication history**: logged touchpoints by channel (Call, Email,
  WhatsApp, Meeting, SMS).
- **Referrals**: who a client has referred, with the option to
  auto-generate a linked Lead so referrals feed straight into the Leads
  pipeline.

## Proposal Management module (RVOS spec)

Added per the "RVOS Proposal Management — Final Specification" document. Lives
**inside Client 360**, not as a separate nav tab, per the spec's explicit
placement rule.

- **Lifecycle**: Draft → Shared → Discussion → Accepted / Partially Accepted /
  Rejected → Executed → Archived
- **Versioning**: proposals are never overwritten. "Create New Version" links
  a follow-up (e.g. a Quarterly Review) back to its parent via
  `parent_proposal_id`, and version numbers increment automatically within
  that chain.
- **Recommended vs Actual**: each fund recommendation line stores both the
  recommended amount and what was actually invested, enabling an acceptance
  rate metric (shown on the Overview tab as "Proposal acceptance rate").
- **Attachments**: real file upload/download per proposal (Proposal PDF,
  Excel Working, Presentation, Research Notes), stored under
  `backend/data/proposal_attachments/`.
- **Decision tracking**: Accepted / Partially Accepted / Rejected / Pending,
  with a reason field (Waiting for Bonus, Market Uncertainty, etc.) when a
  recommendation isn't taken up.

Proposal data lives in its own tables (`proposals`, `proposal_recommendations`,
`proposal_attachments`), separate from the `sips` table — so uploading a new
SIP dataset never wipes out real advisory history.



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
| Overview | Solution 1 — centralized dashboard, now also surfacing lead KPIs and leads needing attention |
| Leads | PRD Section 4 — full pipeline: creation, qualification, follow-ups, activity timeline, documents, referrals, conversion to Client 360 |
| Client 360 | Solution 2 + PRD Section 5 — search by name/UCC/folio, full profile, proposals, family/goals, notes, communication history, referrals |
| Reports | Solutions 3, 4, 5 — individual, combined, and custom date-range reports (Excel/PDF) |
| Reminders | Solutions 3, 6 — configurable days-before-due reminder list |
| Analytics | Solution 9 — status, risk, scheme, trend, and lead pipeline funnel charts |
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
