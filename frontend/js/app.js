const API = ""; // same-origin, Flask serves both API and frontend

// ---------- Tab navigation ----------
document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");

    if (btn.dataset.tab === "overview") loadOverview();
    if (btn.dataset.tab === "reminders") loadReminders();
    if (btn.dataset.tab === "analytics") loadAnalytics();
    if (btn.dataset.tab === "leads") loadLeadsTab();
  });
});

function riskBadge(risk) {
  const cls = risk === "High" ? "badge-high" : risk === "Medium" ? "badge-medium" : "badge-low";
  return `<span class="badge ${cls}">${risk}</span>`;
}

function priorityBadge(priority) {
  const cls = priority === "Hot" ? "badge-hot" : priority === "Warm" ? "badge-warm" : "badge-cold";
  return `<span class="badge ${cls}">${priority}</span>`;
}

function leadStatusBadge(status) {
  return `<span class="badge badge-status">${status}</span>`;
}

// ---------- Dataset upload ----------
document.getElementById("dataset-upload-btn").addEventListener("click", uploadDataset);

async function uploadDataset() {
  const fileInput = document.getElementById("dataset-file-input");
  const statusBox = document.getElementById("upload-status");

  if (!fileInput.files.length) {
    statusBox.className = "upload-status error";
    statusBox.textContent = "Please choose a file first.";
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  statusBox.className = "upload-status loading";
  statusBox.textContent = "Uploading and processing... this can take a few seconds.";

  try {
    const res = await fetch(`${API}/api/dataset/upload`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (!res.ok) {
      statusBox.className = "upload-status error";
      statusBox.textContent = data.error || "Upload failed.";
      return;
    }

    statusBox.className = "upload-status success";
    statusBox.textContent = `${data.message} ${data.summary.records_loaded} SIP(s) added from this file — ${data.summary.total_records} total in the dataset now.`;
    fileInput.value = "";
    loadOverview();
  } catch (err) {
    statusBox.className = "upload-status error";
    statusBox.textContent = "Something went wrong. Please try again.";
  }
}

async function clearDataset() {
  const statusBox = document.getElementById("upload-status");
  if (!confirm(
    "This will permanently delete ALL client/SIP data (including the 100 sample demo records, if still present, and any uploaded data). Leads and proposals are not affected. This can't be undone. Continue?"
  )) {
    return;
  }

  statusBox.className = "upload-status loading";
  statusBox.textContent = "Clearing all client data...";

  try {
    const res = await fetch(`${API}/api/dataset/clear`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) {
      statusBox.className = "upload-status error";
      statusBox.textContent = data.error || "Could not clear data.";
      return;
    }
    statusBox.className = "upload-status success";
    statusBox.textContent = data.message;
    loadOverview();
  } catch (err) {
    statusBox.className = "upload-status error";
    statusBox.textContent = "Something went wrong. Please try again.";
  }
}

// ---------- Add single client manually ----------
const CLIENT_SCHEMES = [
  "Axis Midcap Fund", "ICICI Prudential Bluechip Fund", "Nippon India Growth Fund",
  "Parag Parikh Flexi Cap Fund", "HDFC Flexi Cap Fund", "Mirae Asset Large Cap Fund",
  "SBI Small Cap Fund",
];

function toggleAddClientForm() {
  const container = document.getElementById("add-client-form-container");
  if (container.innerHTML.trim()) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = `
    <div class="lead-form">
      <div class="form-row">
        <input type="text" id="new-client-ucc" placeholder="UCC (auto-generated if unknown)">
        <input type="text" id="new-client-name" placeholder="Investor name *">
        <select id="new-client-holding">
          <option>Demat</option>
          <option>Physical</option>
        </select>
      </div>
      <div class="form-row">
        <input type="text" id="new-client-folio" placeholder="Folio No (optional)">
        <input type="text" id="new-client-bank" placeholder="Bank details *">
        <input type="text" id="new-client-sipno" placeholder="SIP No (optional)">
      </div>
      <div class="form-row">
        <select id="new-client-scheme">${CLIENT_SCHEMES.map(s => `<option>${s}</option>`).join("")}</select>
        <input type="text" id="new-client-submission-date" placeholder="SIP submission date (dd-mm-yyyy) *">
        <input type="text" id="new-client-start-date" placeholder="SIP start date (dd-mm-yyyy) *">
      </div>
      <div class="form-row">
        <input type="text" id="new-client-end-date" placeholder="SIP end date (dd-mm-yyyy) *">
      </div>
      <p class="hint">Fields marked * are required. Leave UCC/Folio No/SIP No blank if not known yet -- they'll be auto-generated and can be reconciled later. If this UCC already exists, this adds another SIP under the same client instead of creating a duplicate.</p>
      <div class="btn-row">
        <button onclick="submitManualClient()">Add Client</button>
        <button onclick="document.getElementById('add-client-form-container').innerHTML=''">Cancel</button>
      </div>
      <div id="add-client-status" class="upload-status"></div>
    </div>
  `;
  container.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function submitManualClient() {
  const statusBox = document.getElementById("add-client-status");
  const payload = {
    "UCC": document.getElementById("new-client-ucc").value.trim(),
    "Investor Name": document.getElementById("new-client-name").value.trim(),
    "Demat/Physical": document.getElementById("new-client-holding").value,
    "Folio No": document.getElementById("new-client-folio").value.trim(),
    "Bank Details": document.getElementById("new-client-bank").value.trim(),
    "SIP No": document.getElementById("new-client-sipno").value.trim(),
    "Scheme": document.getElementById("new-client-scheme").value,
    "SIP Submission Date": document.getElementById("new-client-submission-date").value.trim(),
    "SIP Start Date": document.getElementById("new-client-start-date").value.trim(),
    "Start End Date": document.getElementById("new-client-end-date").value.trim(),
  };

  const REQUIRED_KEYS = [
    "Investor Name", "Demat/Physical", "Bank Details", "Scheme",
    "SIP Submission Date", "SIP Start Date", "Start End Date",
  ];
  const missing = REQUIRED_KEYS.filter(k => !payload[k]);
  if (missing.length) {
    statusBox.className = "upload-status error";
    statusBox.textContent = "Please fill in all required fields (marked *).";
    return;
  }

  statusBox.className = "upload-status loading";
  statusBox.textContent = "Adding client...";

  try {
    const res = await fetch(`${API}/api/dataset/add-client`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      statusBox.className = "upload-status error";
      statusBox.textContent = data.error || "Could not add client.";
      return;
    }
    statusBox.className = "upload-status success";
    statusBox.textContent = `${data.message}: ${data.client.investor_name} (UCC ${data.client.ucc}, SIP No ${data.client.sip_no}).`;
    await loadOverview();
  } catch (err) {
    statusBox.className = "upload-status error";
    statusBox.textContent = "Something went wrong. Please try again.";
  }
}

// ---------- Overview ----------
async function loadOverview() {
  const summary = await fetch(`${API}/api/analytics/summary`).then(r => r.json());
  const effectiveness = await fetch(`${API}/api/analytics/proposal-effectiveness`).then(r => r.json());
  const leadSummary = await fetch(`${API}/api/leads/summary`).then(r => r.json());
  const grid = document.getElementById("stat-grid");
  grid.innerHTML = `
    <div class="stat-card"><div class="value">${summary.total_clients}</div><div class="label">Total clients</div></div>
    <div class="stat-card"><div class="value">${summary.active_sips}</div><div class="label">Active SIPs</div></div>
    <div class="stat-card"><div class="value">${summary.due_soon}</div><div class="label">Due soon</div></div>
    <div class="stat-card"><div class="value">${summary.missed_sips}</div><div class="label">Missed SIPs</div></div>
    <div class="stat-card"><div class="value">${summary.high_risk_clients}</div><div class="label">High risk clients</div></div>
    <div class="stat-card"><div class="value">${summary.premium_clients}</div><div class="label">Premium clients</div></div>
    <div class="stat-card"><div class="value">${effectiveness.acceptance_rate_percent}%</div><div class="label">Proposal acceptance rate</div></div>
    <div class="stat-card"><div class="value">${leadSummary.open_leads}</div><div class="label">Open leads</div></div>
    <div class="stat-card"><div class="value">${leadSummary.hot_leads}</div><div class="label">Hot leads</div></div>
    <div class="stat-card"><div class="value">${leadSummary.conversion_rate_percent}%</div><div class="label">Lead conversion rate</div></div>
  `;

  const highRisk = await fetch(`${API}/api/clients/attention?limit=10`).then(r => r.json());
  const tbody = document.querySelector("#attention-table tbody");
  tbody.innerHTML = highRisk.map(c => `
    <tr class="lead-row" onclick="switchToClientTab('${c.ucc}')">
      <td>${c.investor_name} <span style="color:var(--text-secondary)">(${c.ucc})</span></td>
      <td>${c.high_risk_sip_count} of ${c.sip_count}</td>
      <td>${c.high_risk_schemes.join(", ")}</td>
      <td class="ai-suggestion">${c.recommendation.action}</td>
    </tr>
  `).join("") || `<tr><td colspan="4">No high-risk clients</td></tr>`;

  const hotLeads = await fetch(`${API}/api/leads?priority=Hot`).then(r => r.json());
  const leadTbody = document.querySelector("#lead-attention-table tbody");
  const openHotLeads = hotLeads.filter(l => !["Converted", "Lost"].includes(l.status)).slice(0, 10);
  leadTbody.innerHTML = openHotLeads.map(l => `
    <tr class="lead-row" onclick="switchToLeadTab('${l.lead_id}')">
      <td>${l.full_name}</td>
      <td>${priorityBadge(l.priority)}</td>
      <td>${leadStatusBadge(l.status)}</td>
      <td class="ai-suggestion">${l.recommendation.action}</td>
    </tr>
  `).join("") || `<tr><td colspan="4">No hot leads waiting on action</td></tr>`;
}

function switchToLeadTab(leadId) {
  document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelector('.nav-item[data-tab="leads"]').classList.add("active");
  document.getElementById("tab-leads").classList.add("active");
  loadLeadsTab().then(() => showLeadDetail(leadId));
}

function switchToClientTab(ucc) {
  document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelector('.nav-item[data-tab="clients"]').classList.add("active");
  document.getElementById("tab-clients").classList.add("active");
  showClientProfile(ucc);
}

// ---------- Client 360 ----------
document.getElementById("client-search-btn").addEventListener("click", searchClients);
document.getElementById("client-search-input").addEventListener("keydown", e => {
  if (e.key === "Enter") searchClients();
});

async function searchClients() {
  const q = document.getElementById("client-search-input").value.trim();
  if (!q) return;
  const results = await fetch(`${API}/api/clients/search?q=${encodeURIComponent(q)}`).then(r => r.json());
  const container = document.getElementById("client-results");
  container.innerHTML = results.map(c => `
    <div class="client-result-item" onclick="showClientProfile('${c.ucc}')">
      <span>${c.investor_name} (${c.ucc})</span>
      <span>${riskBadge(c.risk_level)}</span>
    </div>
  `).join("") || `<div class="hint">No matches found.</div>`;
}

async function showClientProfile(ucc) {
  currentUcc = ucc;
  const c = await fetch(`${API}/api/clients/${ucc}`).then(r => r.json());
  const profile = document.getElementById("client-profile");
  profile.innerHTML = `
    <h2>${c.investor_name} <span style="font-weight:400;color:var(--text-secondary)">(${c.ucc})</span></h2>
    <div class="profile-grid">
      <div class="profile-field"><div class="label">Primary folio</div><div class="value">${c.folio_no}</div></div>
      <div class="profile-field"><div class="label">Holding type</div><div class="value">${c.holding_type}</div></div>
      <div class="profile-field"><div class="label">Bank details</div><div class="value">${c.bank_details}</div></div>
      <div class="profile-field"><div class="label">Number of SIPs</div><div class="value">${c.sip_count}</div></div>
      <div class="profile-field"><div class="label">Total SIP amount</div><div class="value">₹${c.sip_amount}</div></div>
      <div class="profile-field"><div class="label">Next due</div><div class="value">${c.next_due_date} (${c.days_to_due}d)</div></div>
      <div class="profile-field"><div class="label">Overall status</div><div class="value">${c.status}</div></div>
      <div class="profile-field"><div class="label">Highest risk</div><div class="value">${riskBadge(c.risk_level)}</div></div>
      <div class="profile-field"><div class="label">Total missed installments</div><div class="value">${c.missed_count}</div></div>
      <div class="profile-field"><div class="label">Premium client</div><div class="value">${c.is_premium ? "Yes" : "No"}</div></div>
    </div>
    <div class="assistant-answer" style="display:block">
      <strong>AI recommendation:</strong> ${c.recommendation.action} — ${c.recommendation.reason}
    </div>

    <div class="proposals-section">
      <div class="proposals-header">
        <h2>SIPs held by this client (${c.sip_count})</h2>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr><th>Scheme</th><th>Folio No</th><th>Amount</th><th>Start</th><th>End</th><th>Next due</th><th>Status</th><th>Risk</th></tr>
          </thead>
          <tbody>
            ${c.sips.map(s => `
              <tr>
                <td>${s.scheme}</td>
                <td>${s.folio_no}</td>
                <td>₹${s.sip_amount}</td>
                <td>${s.sip_start_date}</td>
                <td>${s.sip_end_date}</td>
                <td>${s.next_due_date}</td>
                <td>${s.status}</td>
                <td>${riskBadge(s.risk_level)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    </div>

    <div class="proposals-section">
      <div class="proposals-header">
        <h2>Proposals</h2>
        <button id="new-proposal-btn" onclick="openProposalForm()">+ New Proposal</button>
      </div>
      <div id="proposal-form-container"></div>
      <div id="proposals-list" class="proposals-list"></div>
    </div>

    <div class="client-subsections">
      <div class="subsection">
        <div class="subsection-header">
          <h2>Family &amp; financial goals</h2>
          <button class="small-btn" onclick="openProfileForm()">Edit</button>
        </div>
        <div id="client-profile-form-container"></div>
        <div id="client-profile-view"></div>
      </div>

      <div class="subsection">
        <div class="subsection-header"><h2>Notes</h2></div>
        <div class="form-row">
          <input type="text" id="new-note-text" placeholder="Add an internal note...">
          <button class="small-btn" onclick="addClientNote()">Add</button>
        </div>
        <div id="client-notes-list"></div>
      </div>

      <div class="subsection">
        <div class="subsection-header"><h2>Communication history</h2></div>
        <div class="form-row">
          <select id="new-comm-channel">${["Call", "Email", "WhatsApp", "Meeting", "SMS"].map(c => `<option>${c}</option>`).join("")}</select>
          <input type="text" id="new-comm-summary" placeholder="What was discussed?">
          <button class="small-btn" onclick="addClientCommunication()">Log</button>
        </div>
        <div id="client-comms-list"></div>
      </div>

      <div class="subsection">
        <div class="subsection-header"><h2>Referrals</h2></div>
        <div class="form-row">
          <input type="text" id="new-referral-name" placeholder="Referred person's name">
          <input type="text" id="new-referral-phone" placeholder="Phone">
          <label style="display:flex;align-items:center;gap:6px;font-size:13px;">
            <input type="checkbox" id="new-referral-create-lead" checked style="width:auto"> Create a lead
          </label>
          <button class="small-btn" onclick="addClientReferral()">Add referral</button>
        </div>
        <div id="client-referrals-list"></div>
      </div>
    </div>
  `;
  loadProposals(ucc);
  loadClientProfile(ucc);
  loadClientNotes(ucc);
  loadClientCommunications(ucc);
  loadClientReferrals(ucc);
}

// ---------- Client 360 extensions: profile, notes, communications, referrals ----------

async function loadClientProfile(ucc) {
  const p = await fetch(`${API}/api/clients/${ucc}/profile`).then(r => r.json());
  const view = document.getElementById("client-profile-view");
  const familyChips = (p.family_members || []).map(f => `<span class="chip">${f.name} (${f.relation}${f.dob ? ", " + f.dob : ""})</span>`).join("") || "<span class='hint'>No family members recorded.</span>";
  const goalChips = (p.financial_goals || []).map(g => `<span class="chip">${g.goal}: ₹${Number(g.target_amount).toLocaleString()} by ${g.target_year}</span>`).join("") || "<span class='hint'>No financial goals recorded.</span>";

  view.innerHTML = `
    <div class="profile-field"><div class="label">Family members</div></div>
    <div class="chip-list">${familyChips}</div>
    <div class="profile-field"><div class="label">Financial goals</div></div>
    <div class="chip-list">${goalChips}</div>
    <div class="profile-grid">
      <div class="profile-field"><div class="label">Risk notes</div><div class="value">${p.risk_notes || "—"}</div></div>
      <div class="profile-field"><div class="label">Quarterly review</div><div class="value">${p.quarterly_review_date || "—"}</div></div>
      <div class="profile-field"><div class="label">Annual review</div><div class="value">${p.annual_review_date || "—"}</div></div>
    </div>
  `;
  window._currentClientProfile = p;
}

function openProfileForm() {
  const p = window._currentClientProfile || { family_members: [], financial_goals: [] };
  const container = document.getElementById("client-profile-form-container");
  container.innerHTML = `
    <div class="subsection-form">
      <label class="hint" style="margin:0">Family members (one per line: Name, Relation, DOB)</label>
      <textarea id="profile-family-input" rows="2">${(p.family_members || []).map(f => `${f.name}, ${f.relation}, ${f.dob || ""}`).join("\n")}</textarea>
      <label class="hint" style="margin:0">Financial goals (one per line: Goal, Target amount, Target year)</label>
      <textarea id="profile-goals-input" rows="2">${(p.financial_goals || []).map(g => `${g.goal}, ${g.target_amount}, ${g.target_year}`).join("\n")}</textarea>
      <textarea id="profile-risk-notes" rows="2" placeholder="Risk notes">${p.risk_notes || ""}</textarea>
      <div class="form-row">
        <input type="text" id="profile-quarterly-review" placeholder="Quarterly review date (dd-mm-yyyy)" value="${p.quarterly_review_date || ""}">
        <input type="text" id="profile-annual-review" placeholder="Annual review date (dd-mm-yyyy)" value="${p.annual_review_date || ""}">
      </div>
      <div class="btn-row">
        <button onclick="saveClientProfile()">Save</button>
        <button onclick="document.getElementById('client-profile-form-container').innerHTML=''">Cancel</button>
      </div>
    </div>
  `;
}

async function saveClientProfile() {
  const family_members = document.getElementById("profile-family-input").value.split("\n")
    .map(l => l.trim()).filter(Boolean)
    .map(l => { const [name, relation, dob] = l.split(",").map(s => (s || "").trim()); return { name, relation, dob }; });
  const financial_goals = document.getElementById("profile-goals-input").value.split("\n")
    .map(l => l.trim()).filter(Boolean)
    .map(l => { const [goal, target_amount, target_year] = l.split(",").map(s => (s || "").trim()); return { goal, target_amount: parseFloat(target_amount) || 0, target_year }; });

  await fetch(`${API}/api/clients/${currentUcc}/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      family_members, financial_goals,
      risk_notes: document.getElementById("profile-risk-notes").value.trim(),
      quarterly_review_date: document.getElementById("profile-quarterly-review").value.trim() || null,
      annual_review_date: document.getElementById("profile-annual-review").value.trim() || null,
    }),
  });
  document.getElementById("client-profile-form-container").innerHTML = "";
  loadClientProfile(currentUcc);
}

async function loadClientNotes(ucc) {
  const notes = await fetch(`${API}/api/clients/${ucc}/notes`).then(r => r.json());
  document.getElementById("client-notes-list").innerHTML = notes.map(n => `
    <div class="note-item">${n.note}<div class="item-meta">${n.created_at} · ${n.created_by}</div></div>
  `).join("") || `<div class="hint">No notes yet.</div>`;
}

async function addClientNote() {
  const input = document.getElementById("new-note-text");
  const note = input.value.trim();
  if (!note) return;
  await fetch(`${API}/api/clients/${currentUcc}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ note, created_by: "RM Admin" }),
  });
  input.value = "";
  loadClientNotes(currentUcc);
}

async function loadClientCommunications(ucc) {
  const comms = await fetch(`${API}/api/clients/${ucc}/communications`).then(r => r.json());
  document.getElementById("client-comms-list").innerHTML = comms.map(c => `
    <div class="comm-item"><span class="activity-type-tag">${c.channel}</span>${c.summary}<div class="item-meta">${c.created_at} · ${c.created_by}</div></div>
  `).join("") || `<div class="hint">No communication history yet.</div>`;
}

async function addClientCommunication() {
  const channel = document.getElementById("new-comm-channel").value;
  const summaryInput = document.getElementById("new-comm-summary");
  const summary = summaryInput.value.trim();
  if (!summary) return;
  await fetch(`${API}/api/clients/${currentUcc}/communications`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel, summary, created_by: "RM Admin" }),
  });
  summaryInput.value = "";
  loadClientCommunications(currentUcc);
}

async function loadClientReferrals(ucc) {
  const referrals = await fetch(`${API}/api/clients/${ucc}/referrals`).then(r => r.json());
  document.getElementById("client-referrals-list").innerHTML = referrals.map(r => `
    <div class="referral-item">${r.referred_name}${r.referred_phone ? " · " + r.referred_phone : ""}
      ${leadStatusBadge(r.status)}
      <div class="item-meta">${r.created_at}${r.lead_id ? " · Linked lead: " + r.lead_id : ""}</div>
    </div>
  `).join("") || `<div class="hint">No referrals logged yet.</div>`;
}

async function addClientReferral() {
  const referred_name = document.getElementById("new-referral-name").value.trim();
  const referred_phone = document.getElementById("new-referral-phone").value.trim();
  const create_lead = document.getElementById("new-referral-create-lead").checked;
  if (!referred_name) {
    alert("Enter the referred person's name.");
    return;
  }
  const res = await fetch(`${API}/api/clients/${currentUcc}/referrals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ referred_name, referred_phone: referred_phone || null, create_lead }),
  });
  if (!res.ok) {
    const err = await res.json();
    alert(err.error || "Could not add referral.");
    return;
  }
  document.getElementById("new-referral-name").value = "";
  document.getElementById("new-referral-phone").value = "";
  loadClientReferrals(currentUcc);
}

// ---------- Proposal Management ----------
let currentUcc = null;
let recRowCount = 0;
const PROPOSAL_PURPOSES = [
  "Initial Investment", "Quarterly Review", "Annual Review", "Additional SIP",
  "Lumpsum Investment", "Portfolio Rebalancing", "Goal Planning",
  "Tax Planning", "Insurance Review", "Other",
];
const REJECTION_REASONS = [
  "Waiting for Bonus", "Salary Delayed", "Market Uncertainty",
  "Needs Family Approval", "Already Invested Elsewhere", "Other",
];

function proposalStatusBadge(status) {
  const map = {
    "Draft": "badge-medium", "Shared": "badge-medium", "Discussion": "badge-medium",
    "Accepted": "badge-low", "Executed": "badge-low",
    "Partially Accepted": "badge-medium", "Rejected": "badge-high", "Archived": "badge-medium",
  };
  return `<span class="badge ${map[status] || "badge-medium"}">${status}</span>`;
}

async function loadProposals(ucc) {
  const proposals = await fetch(`${API}/api/clients/${ucc}/proposals`).then(r => r.json());
  const list = document.getElementById("proposals-list");

  if (!proposals.length) {
    list.innerHTML = `<div class="hint">No proposals yet for this client. Click "+ New Proposal" to create the first one.</div>`;
    return;
  }

  list.innerHTML = proposals.map(p => {
    const recRows = p.recommendations.map(r => `
      <tr>
        <td>${r.scheme_name}</td>
        <td>${r.investment_type}</td>
        <td>₹${r.recommended_amount.toLocaleString()}</td>
        <td>
          <input type="number" class="actual-input" id="actual-${r.id}" placeholder="Actual ₹"
                 value="${r.actual_amount ?? ''}">
          <button class="small-btn" onclick="saveActual('${p.proposal_id}', ${r.id})">Save</button>
        </td>
      </tr>
    `).join("");

    return `
      <div class="proposal-card">
        <div class="proposal-card-header">
          <div>
            <strong>${p.proposal_id}</strong>
            <span class="version-badge">V${p.version_number}</span>
            ${proposalStatusBadge(p.status)}
            <span class="decision-badge">${p.client_decision}</span>
          </div>
          <div class="proposal-meta">${p.proposal_date} · by ${p.created_by}</div>
        </div>

        <div class="proposal-purpose">${p.purpose}</div>

        <table class="data-table proposal-rec-table">
          <thead><tr><th>Scheme</th><th>Type</th><th>Recommended</th><th>Actual</th></tr></thead>
          <tbody>${recRows}</tbody>
        </table>

        ${p.decision_reason ? `<div class="hint">Reason: ${p.decision_reason}</div>` : ""}
        ${p.internal_notes ? `<div class="internal-notes"><strong>Internal notes:</strong> ${p.internal_notes}</div>` : ""}

        <div class="proposal-actions">
          <select id="status-${p.proposal_id}">
            ${["Draft","Shared","Discussion","Accepted","Partially Accepted","Rejected","Executed","Archived"]
              .map(s => `<option value="${s}" ${s === p.status ? "selected" : ""}>${s}</option>`).join("")}
          </select>
          <select id="decision-${p.proposal_id}">
            ${["Pending","Accepted","Partially Accepted","Rejected"]
              .map(d => `<option value="${d}" ${d === p.client_decision ? "selected" : ""}>${d}</option>`).join("")}
          </select>
          <select id="reason-${p.proposal_id}">
            <option value="">No reason</option>
            ${REJECTION_REASONS.map(r => `<option value="${r}">${r}</option>`).join("")}
          </select>
          <button class="small-btn" onclick="saveStatus('${p.proposal_id}')">Update</button>
          <button class="small-btn" onclick="openProposalForm('${p.proposal_id}')">Create New Version</button>
        </div>

        <div class="attachments-row">
          <strong>Attachments:</strong>
          ${p.attachments.map(a => `<a href="${API}/api/proposals/attachments/${a.id}/download" class="attachment-link">${a.file_name}</a>`).join(" ") || "<span class='hint'>None</span>"}
          <input type="file" id="attach-file-${p.proposal_id}" class="attach-input">
          <select id="attach-type-${p.proposal_id}">
            <option>Proposal PDF</option><option>Excel Working</option>
            <option>Presentation</option><option>Research Notes</option>
          </select>
          <button class="small-btn" onclick="uploadAttachment('${p.proposal_id}')">Upload</button>
        </div>
      </div>
    `;
  }).join("");
}

function openProposalForm(parentProposalId = null) {
  recRowCount = 0;
  const container = document.getElementById("proposal-form-container");
  container.innerHTML = `
    <div class="proposal-form">
      <h2>${parentProposalId ? "Create New Version" : "New Proposal"}</h2>
      <input type="hidden" id="parent-proposal-id" value="${parentProposalId || ""}">
      <select id="proposal-purpose">
        ${PROPOSAL_PURPOSES.map(p => `<option>${p}</option>`).join("")}
      </select>
      <div id="rec-rows"></div>
      <button class="small-btn" onclick="addRecRow()">+ Add recommendation</button>
      <textarea id="proposal-notes" placeholder="Internal notes (advisor-only)..." rows="2"></textarea>
      <div class="btn-row">
        <button onclick="submitProposal()">Submit</button>
        <button onclick="closeProposalForm()">Cancel</button>
      </div>
    </div>
  `;
  addRecRow();
}

function closeProposalForm() {
  document.getElementById("proposal-form-container").innerHTML = "";
}

function addRecRow() {
  recRowCount++;
  const id = recRowCount;
  const rows = document.getElementById("rec-rows");
  const row = document.createElement("div");
  row.className = "rec-row";
  row.id = `rec-row-${id}`;
  row.innerHTML = `
    <input type="text" placeholder="Scheme name" class="rec-scheme">
    <select class="rec-type"><option>SIP</option><option>Lumpsum</option></select>
    <input type="number" placeholder="Amount (₹)" class="rec-amount">
    <button class="small-btn" onclick="document.getElementById('rec-row-${id}').remove()">✕</button>
  `;
  rows.appendChild(row);
}

async function submitProposal() {
  const purpose = document.getElementById("proposal-purpose").value;
  const notes = document.getElementById("proposal-notes").value;
  const parentId = document.getElementById("parent-proposal-id").value;

  const recommendations = Array.from(document.querySelectorAll(".rec-row")).map(row => ({
    scheme_name: row.querySelector(".rec-scheme").value,
    investment_type: row.querySelector(".rec-type").value,
    recommended_amount: parseFloat(row.querySelector(".rec-amount").value) || 0,
  })).filter(r => r.scheme_name && r.recommended_amount > 0);

  if (!recommendations.length) {
    alert("Add at least one recommendation with a scheme name and amount.");
    return;
  }

  const url = parentId
    ? `${API}/api/proposals/${parentId}/version`
    : `${API}/api/clients/${currentUcc}/proposals`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ purpose, recommendations, internal_notes: notes, created_by: "RM Admin" }),
  });

  if (!res.ok) {
    const err = await res.json();
    alert(err.error || "Could not save proposal.");
    return;
  }

  closeProposalForm();
  loadProposals(currentUcc);
}

async function saveStatus(proposalId) {
  const status = document.getElementById(`status-${proposalId}`).value;
  const decision = document.getElementById(`decision-${proposalId}`).value;
  const reason = document.getElementById(`reason-${proposalId}`).value;

  await fetch(`${API}/api/proposals/${proposalId}/status`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, client_decision: decision, decision_reason: reason || null }),
  });
  loadProposals(currentUcc);
}

async function saveActual(proposalId, recId) {
  const value = document.getElementById(`actual-${recId}`).value;
  await fetch(`${API}/api/proposals/${proposalId}/recommendations/${recId}/actual`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actual_amount: parseFloat(value) || 0 }),
  });
  loadProposals(currentUcc);
}

async function uploadAttachment(proposalId) {
  const fileInput = document.getElementById(`attach-file-${proposalId}`);
  const typeSelect = document.getElementById(`attach-type-${proposalId}`);
  if (!fileInput.files.length) {
    alert("Choose a file first.");
    return;
  }
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("file_type", typeSelect.value);

  await fetch(`${API}/api/proposals/${proposalId}/attachments`, { method: "POST", body: formData });
  loadProposals(currentUcc);
}

// ---------- Leads ----------
const LEAD_SOURCES = ["Referral", "Walk-in", "Social Media", "Website", "Cold Call", "Event", "Other"];
const LEAD_STATUSES = ["New", "Contacted", "Qualified", "Proposal Sent", "Negotiation", "Converted", "Lost"];
const LEAD_PRIORITIES = ["Hot", "Warm", "Cold"];
const LEAD_ACTIVITY_TYPES = ["Call", "Meeting", "Email", "WhatsApp", "Note"];

let leadFiltersInitialized = false;
let currentLeadId = null;

function initLeadFilters() {
  if (leadFiltersInitialized) return;
  leadFiltersInitialized = true;
  const statusSel = document.getElementById("lead-filter-status");
  const prioritySel = document.getElementById("lead-filter-priority");
  const sourceSel = document.getElementById("lead-filter-source");
  LEAD_STATUSES.forEach(s => statusSel.insertAdjacentHTML("beforeend", `<option value="${s}">${s}</option>`));
  LEAD_PRIORITIES.forEach(p => prioritySel.insertAdjacentHTML("beforeend", `<option value="${p}">${p}</option>`));
  LEAD_SOURCES.forEach(s => sourceSel.insertAdjacentHTML("beforeend", `<option value="${s}">${s}</option>`));

  document.getElementById("lead-filter-btn").addEventListener("click", loadLeads);
  document.getElementById("lead-search-input").addEventListener("keydown", e => {
    if (e.key === "Enter") loadLeads();
  });
}

async function loadLeadsTab() {
  initLeadFilters();
  await loadLeadStats();
  await loadLeads();
}

async function loadLeadStats() {
  const s = await fetch(`${API}/api/leads/summary`).then(r => r.json());
  document.getElementById("lead-stat-grid").innerHTML = `
    <div class="stat-card"><div class="value">${s.total_leads}</div><div class="label">Total leads</div></div>
    <div class="stat-card"><div class="value">${s.open_leads}</div><div class="label">Open leads</div></div>
    <div class="stat-card"><div class="value">${s.hot_leads}</div><div class="label">Hot leads</div></div>
    <div class="stat-card"><div class="value">${s.converted_leads}</div><div class="label">Converted</div></div>
    <div class="stat-card"><div class="value">${s.lost_leads}</div><div class="label">Lost</div></div>
    <div class="stat-card"><div class="value">${s.conversion_rate_percent}%</div><div class="label">Conversion rate</div></div>
  `;
}

async function loadLeads() {
  const q = document.getElementById("lead-search-input").value.trim();
  const status = document.getElementById("lead-filter-status").value;
  const priority = document.getElementById("lead-filter-priority").value;
  const source = document.getElementById("lead-filter-source").value;

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  if (priority) params.set("priority", priority);
  if (source) params.set("source", source);

  const leads = await fetch(`${API}/api/leads?${params.toString()}`).then(r => r.json());
  const tbody = document.querySelector("#leads-table tbody");
  tbody.innerHTML = leads.map(l => `
    <tr class="lead-row" onclick="showLeadDetail('${l.lead_id}')">
      <td>${l.full_name}</td>
      <td>${l.phone}</td>
      <td>${l.source}</td>
      <td>${leadStatusBadge(l.status)}</td>
      <td>${priorityBadge(l.priority)}</td>
      <td>${l.assigned_to || "—"}</td>
      <td>${l.next_follow_up_date || "—"}</td>
      <td class="ai-suggestion">${l.recommendation.action}</td>
      <td>
        <div class="row-actions">
          <button class="small-btn" onclick="event.stopPropagation(); showLeadDetail('${l.lead_id}')">View</button>
          <button class="small-btn" onclick="event.stopPropagation(); editLead('${l.lead_id}')">Edit</button>
          <button class="small-btn danger" onclick="event.stopPropagation(); deleteLead('${l.lead_id}')">Delete</button>
        </div>
      </td>
    </tr>
  `).join("") || `<tr><td colspan="9">No leads match these filters.</td></tr>`;
}

function openLeadForm(lead = null) {
  const isEdit = !!lead;
  const container = document.getElementById("lead-form-container");
  container.innerHTML = `
    <div class="lead-form">
      <h2>${isEdit ? `Edit Lead — ${lead.full_name}` : "New Lead"}</h2>
      <div class="form-row">
        <input type="text" id="new-lead-name" placeholder="Full name *" value="${isEdit ? lead.full_name : ""}">
        <input type="text" id="new-lead-phone" placeholder="Phone *" value="${isEdit ? lead.phone : ""}">
        <input type="email" id="new-lead-email" placeholder="Email" value="${isEdit ? (lead.email || "") : ""}">
      </div>
      <div class="form-row">
        <select id="new-lead-source">${LEAD_SOURCES.map(s => `<option ${isEdit && s === lead.source ? "selected" : ""}>${s}</option>`).join("")}</select>
        <select id="new-lead-priority">${LEAD_PRIORITIES.map(p => `<option ${isEdit ? (p === lead.priority ? "selected" : "") : (p === "Warm" ? "selected" : "")}>${p}</option>`).join("")}</select>
        <input type="text" id="new-lead-assigned" placeholder="Assigned to (RM name)" value="${isEdit ? (lead.assigned_to || "") : ""}">
      </div>
      <div class="form-row">
        <input type="text" id="new-lead-scheme" placeholder="Interested scheme" value="${isEdit ? (lead.interested_scheme || "") : ""}">
        <input type="number" id="new-lead-amount" placeholder="Expected investment (₹)" value="${isEdit ? (lead.expected_investment_amount || "") : ""}">
        <input type="text" id="new-lead-followup" placeholder="Next follow-up (dd-mm-yyyy)" value="${isEdit ? (lead.next_follow_up_date || "") : ""}">
      </div>
      <div class="btn-row">
        <button onclick="submitLead(${isEdit ? `'${lead.lead_id}'` : "null"})">${isEdit ? "Save Changes" : "Create Lead"}</button>
        <button onclick="document.getElementById('lead-form-container').innerHTML=''">Cancel</button>
      </div>
    </div>
  `;
  container.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function editLead(leadId) {
  const lead = await fetch(`${API}/api/leads/${leadId}`).then(r => r.json());
  openLeadForm(lead);
}

async function submitLead(editLeadId) {
  const full_name = document.getElementById("new-lead-name").value.trim();
  const phone = document.getElementById("new-lead-phone").value.trim();
  if (!full_name || !phone) {
    alert("Full name and phone are required.");
    return;
  }
  const payload = {
    full_name, phone,
    email: document.getElementById("new-lead-email").value.trim() || null,
    source: document.getElementById("new-lead-source").value,
    priority: document.getElementById("new-lead-priority").value,
    assigned_to: document.getElementById("new-lead-assigned").value.trim() || null,
    interested_scheme: document.getElementById("new-lead-scheme").value.trim() || null,
    expected_investment_amount: parseFloat(document.getElementById("new-lead-amount").value) || null,
    next_follow_up_date: document.getElementById("new-lead-followup").value.trim() || null,
  };

  const res = await fetch(`${API}/api/leads${editLeadId ? "/" + editLeadId : ""}`, {
    method: editLeadId ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    alert(err.error || `Could not ${editLeadId ? "update" : "create"} lead.`);
    return;
  }
  document.getElementById("lead-form-container").innerHTML = "";
  await loadLeadStats();
  await loadLeads();
  if (editLeadId && currentLeadId === editLeadId) showLeadDetail(editLeadId);
}

async function deleteLead(leadId) {
  if (!confirm("Delete this lead? This can't be undone.")) return;
  const res = await fetch(`${API}/api/leads/${leadId}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json();
    alert(err.error || "Could not delete lead.");
    return;
  }
  if (currentLeadId === leadId) {
    currentLeadId = null;
    document.getElementById("lead-detail").innerHTML = "";
  }
  await loadLeadStats();
  await loadLeads();
}

async function showLeadDetail(leadId) {
  currentLeadId = leadId;
  const l = await fetch(`${API}/api/leads/${leadId}`).then(r => r.json());
  const detail = document.getElementById("lead-detail");

  const timeline = l.activities.map(a => `
    <li>
      <span class="activity-type-tag">${a.activity_type}</span>${a.description}
      <div class="timeline-meta">${a.created_at} · ${a.created_by}</div>
    </li>
  `).join("") || `<li class="hint">No activity logged yet.</li>`;

  const docs = l.documents.map(d => `
    <a href="${API}/api/leads/documents/${d.id}/download" class="attachment-link">${d.file_name}</a>
  `).join(" ") || "<span class='hint'>None</span>";

  detail.innerHTML = `
    <div class="panel">
      <div class="lead-detail-header">
        <div>
          <h2>${l.full_name} <span style="font-weight:400;color:var(--text-secondary)">(${l.lead_id})</span></h2>
          <div class="hint" style="margin:0">${l.phone}${l.email ? " · " + l.email : ""} · Source: ${l.source}</div>
        </div>
        <div>${priorityBadge(l.priority)} ${leadStatusBadge(l.status)}</div>
      </div>

      <div class="assistant-answer" style="display:block">
        <strong>AI recommendation:</strong> ${l.recommendation.action} — ${l.recommendation.reason}
      </div>

      ${l.status === "Converted" ? `<div class="hint">Converted to Client 360 as <strong>${l.converted_ucc}</strong> on ${l.converted_at}. <a href="#" onclick="event.preventDefault(); goToClient('${l.converted_ucc}')">View client profile</a></div>` : ""}

      <div class="lead-quick-actions">
        <select id="lead-status-select">
          ${LEAD_STATUSES.map(s => `<option value="${s}" ${s === l.status ? "selected" : ""}>${s}</option>`).join("")}
        </select>
        <select id="lead-priority-select">
          ${LEAD_PRIORITIES.map(p => `<option value="${p}" ${p === l.priority ? "selected" : ""}>${p}</option>`).join("")}
        </select>
        <input type="text" id="lead-followup-input" placeholder="Next follow-up (dd-mm-yyyy)" value="${l.next_follow_up_date || ""}">
        <input type="text" id="lead-lost-reason" placeholder="Lost reason (if marking Lost)" value="${l.lost_reason || ""}">
        <button class="small-btn" onclick="saveLeadQuickEdit()">Save</button>
        ${l.status !== "Converted" ? `<button class="small-btn" onclick="convertLead('${l.lead_id}')">Convert to Client</button>` : ""}
        <button class="small-btn" onclick="editLead('${l.lead_id}')">Edit details</button>
        <button class="small-btn danger" onclick="deleteLead('${l.lead_id}')">Delete lead</button>
      </div>

      <div class="subsection">
        <div class="subsection-header"><h2>Activity timeline</h2></div>
        <div class="form-row">
          <select id="new-activity-type">${LEAD_ACTIVITY_TYPES.map(t => `<option>${t}</option>`).join("")}</select>
          <input type="text" id="new-activity-desc" placeholder="What happened?">
          <button class="small-btn" onclick="addLeadActivity()">Log</button>
        </div>
        <ul class="timeline">${timeline}</ul>
      </div>

      <div class="subsection">
        <div class="subsection-header"><h2>Documents</h2></div>
        <div class="attachments-row">
          ${docs}
          <input type="file" id="lead-doc-file" class="attach-input">
          <select id="lead-doc-type"><option>KYC</option><option>ID Proof</option><option>Other</option></select>
          <button class="small-btn" onclick="uploadLeadDocument()">Upload</button>
        </div>
      </div>
    </div>
  `;
}

async function saveLeadQuickEdit() {
  const status = document.getElementById("lead-status-select").value;
  const priority = document.getElementById("lead-priority-select").value;
  const next_follow_up_date = document.getElementById("lead-followup-input").value.trim() || null;
  const lost_reason = document.getElementById("lead-lost-reason").value.trim() || null;

  const res = await fetch(`${API}/api/leads/${currentLeadId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, priority, next_follow_up_date, lost_reason }),
  });
  if (!res.ok) {
    const err = await res.json();
    alert(err.error || "Could not update lead.");
    return;
  }
  await loadLeadStats();
  await loadLeads();
  showLeadDetail(currentLeadId);
}

async function addLeadActivity() {
  const activity_type = document.getElementById("new-activity-type").value;
  const description = document.getElementById("new-activity-desc").value.trim();
  if (!description) return;

  await fetch(`${API}/api/leads/${currentLeadId}/activities`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ activity_type, description, created_by: "RM Admin" }),
  });
  showLeadDetail(currentLeadId);
}

async function uploadLeadDocument() {
  const fileInput = document.getElementById("lead-doc-file");
  const typeSelect = document.getElementById("lead-doc-type");
  if (!fileInput.files.length) {
    alert("Choose a file first.");
    return;
  }
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("file_type", typeSelect.value);
  await fetch(`${API}/api/leads/${currentLeadId}/documents`, { method: "POST", body: formData });
  showLeadDetail(currentLeadId);
}

async function convertLead(leadId) {
  if (!confirm("Convert this lead into a Client 360 record?")) return;
  const res = await fetch(`${API}/api/leads/${leadId}/convert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ converted_by: "RM Admin" }),
  });
  if (!res.ok) {
    const err = await res.json();
    alert(err.error || "Could not convert lead.");
    return;
  }
  await loadLeadStats();
  await loadLeads();
  showLeadDetail(leadId);
}

function goToClient(ucc) {
  document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelector('.nav-item[data-tab="clients"]').classList.add("active");
  document.getElementById("tab-clients").classList.add("active");
  showClientProfile(ucc);
}

// ---------- Reports ----------
document.querySelectorAll("button[data-report]").forEach(btn => {
  btn.addEventListener("click", () => {
    const type = btn.dataset.report;
    const fmt = btn.dataset.format;
    if (type === "individual") {
      const ucc = document.getElementById("report-ucc").value.trim();
      if (!ucc) return alert("Enter a UCC first.");
      window.location = `${API}/api/reports/individual/${ucc}?format=${fmt}`;
    } else {
      const scope = document.getElementById("combined-scope").value;
      const value = document.getElementById("combined-value").value.trim();
      const start = document.getElementById("date-start").value.trim();
      const end = document.getElementById("date-end").value.trim();
      let url = `${API}/api/reports/combined?format=${fmt}&scope=${scope}`;
      if (value) url += `&value=${encodeURIComponent(value)}`;
      if (start) url += `&start_date=${start}`;
      if (end) url += `&end_date=${end}`;
      window.location = url;
    }
  });
});

// ---------- Reminders ----------
document.getElementById("reminder-refresh").addEventListener("click", loadReminders);

async function loadReminders() {
  const days = document.getElementById("reminder-days").value || 2;
  const rows = await fetch(`${API}/api/reminders/due?days=${days}`).then(r => r.json());
  const tbody = document.querySelector("#reminder-table tbody");
  tbody.innerHTML = rows.map(c => `
    <tr>
      <td>${c.investor_name}</td>
      <td>${c.scheme}</td>
      <td>₹${c.sip_amount}</td>
      <td>${c.next_due_date}</td>
      <td>${c.days_to_due}</td>
      <td style="max-width:280px">${c.preview_message}</td>
    </tr>
  `).join("") || `<tr><td colspan="6">No clients due in this window.</td></tr>`;
}

// ---------- Analytics ----------
let charts = {};

function renderChart(id, type, labels, data, colors) {
  const ctx = document.getElementById(id).getContext("2d");
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(ctx, {
    type,
    data: { labels, datasets: [{ data, backgroundColor: colors }] },
    options: { responsive: true, maintainAspectRatio: false }
  });
}

async function loadAnalytics() {
  const status = await fetch(`${API}/api/analytics/status-breakdown`).then(r => r.json());
  renderChart("chart-status", "doughnut",
    status.map(s => s.status), status.map(s => s.count),
    ["#1D9E75", "#E24B4A", "#B4B2A9"]);

  const risk = await fetch(`${API}/api/analytics/risk-distribution`).then(r => r.json());
  renderChart("chart-risk", "doughnut",
    risk.map(r => r.risk_level), risk.map(r => r.count),
    ["#1D9E75", "#EF9F27", "#E24B4A"]);

  const scheme = await fetch(`${API}/api/analytics/scheme-distribution`).then(r => r.json());
  renderChart("chart-scheme", "bar",
    scheme.map(s => s.scheme), scheme.map(s => s.count),
    ["#378ADD"]);

  const trend = await fetch(`${API}/api/analytics/monthly-trend`).then(r => r.json());
  renderChart("chart-trend", "line",
    trend.map(t => t.month), trend.map(t => t.count),
    ["#7F77DD"]);

  const funnel = await fetch(`${API}/api/leads/funnel`).then(r => r.json());
  const funnelOrder = ["New", "Contacted", "Qualified", "Proposal Sent", "Negotiation", "Converted", "Lost"];
  const funnelSorted = funnelOrder
    .map(status => funnel.find(f => f.status === status))
    .filter(Boolean);
  renderChart("chart-lead-funnel", "bar",
    funnelSorted.map(f => f.status), funnelSorted.map(f => f.count),
    ["#EF9F27"]);
}

// ---------- AI Assistant ----------
document.getElementById("assistant-btn").addEventListener("click", askAssistant);
document.getElementById("assistant-input").addEventListener("keydown", e => {
  if (e.key === "Enter") askAssistant();
});

async function askAssistant() {
  const q = document.getElementById("assistant-input").value.trim();
  if (!q) return;
  const res = await fetch(`${API}/api/assistant/query?q=${encodeURIComponent(q)}`).then(r => r.json());

  const answerBox = document.getElementById("assistant-answer");
  answerBox.style.display = "block";
  answerBox.textContent = res.answer;

  const tbody = document.querySelector("#assistant-table tbody");
  tbody.innerHTML = (res.results || []).map(c => `
    <tr>
      <td>${c.investor_name}</td>
      <td>${c.scheme}</td>
      <td>₹${c.sip_amount}</td>
      <td>${c.status}</td>
      <td>${riskBadge(c.risk_level)}</td>
    </tr>
  `).join("");
}

// ---------- Init ----------
loadOverview();
