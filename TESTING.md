# Review Testing Guide

This build includes the latest review updates for:

1. Clients needing attention
2. Missed SIP status
3. Proposals inside Client 360
4. Add New Lead inside Leads

## 1. Clients needing attention

1. Start the application from `backend` with `python app.py`.
2. Open the Overview tab.
3. Check **Clients needing attention**.
4. The queue should show client-level records, not duplicate rows for every SIP held by the same UCC.
5. Check that the queue explains **why** the client needs attention and gives a recommended action.
6. Click an attention row. It should open that client's Client 360 profile.
7. A healthy client should not appear in this queue.

### Rules used

- High risk → Contact immediately.
- Due soon → Send reminder.
- Premium client → Assign senior RM.
- Medium risk → Monitor next installment.
- Healthy → No attention item.

## 2. Missed SIP status

1. On Overview, open **Missed SIP status**.
2. Every non-completed SIP with `missed_count > 0` should display **Missed**.
3. The missed-installment count, risk, last transaction date, and recommended action should be visible.
4. Open the Client 360 profile for a missed client and verify the overall status is also **Missed**.
5. In the SIP table, verify the individual SIP shows its Missed badge and missed count.

### Severity

- 0 missed installments → Active (unless the SIP has completed).
- 1–2 missed installments → Missed + Medium risk.
- 3+ missed installments → Missed + High risk.
- A completed SIP remains Completed even if historical missed installments exist.

## 3. Proposals under Client 360

1. Open **Client 360** and search for a valid UCC.
2. Click **+ New Proposal**.
3. Select a purpose, add at least one scheme, choose SIP/Lumpsum, enter an amount, and click Submit.
4. Verify the proposal appears without leaving Client 360.
5. Verify the proposal shows its version number, status, client decision, recommendation lines, and internal notes when supplied.
6. Change the proposal status/decision and click **Update**. Verify the change persists after refresh.
7. Enter an actual investment amount for a recommendation and click **Save**. Verify the actual amount persists.
8. Try a negative actual amount. It should be rejected.
9. Upload an attachment and verify it appears in the proposal card and can be downloaded.
10. Click **Create New Version** and verify a new version is created while the previous proposal remains unchanged.

## 4. Add New Lead under Leads

1. Open **Leads**.
2. Click **+ New Lead**.
3. Enter a full name and phone number. These are required.
4. Optionally enter email, source, priority, assigned RM, interested scheme, expected investment, and next follow-up date.
5. Use `dd-mm-yyyy` for the follow-up date.
6. Click **Create Lead**.
7. Verify the new lead appears in the pipeline with status **New** and the selected priority.
8. Open the lead and verify the AI recommendation is displayed.
9. Edit the lead and verify the changes persist.
10. Update status/priority/follow-up from the lead detail view and verify the update is saved.
11. Log an activity and verify it appears in the activity timeline.
12. If appropriate, convert the lead and verify the new Client 360 UCC is linked from the lead.
