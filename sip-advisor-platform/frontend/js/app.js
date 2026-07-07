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
  });
});

function riskBadge(risk) {
  const cls = risk === "High" ? "badge-high" : risk === "Medium" ? "badge-medium" : "badge-low";
  return `<span class="badge ${cls}">${risk}</span>`;
}

// ---------- Overview ----------
async function loadOverview() {
  const summary = await fetch(`${API}/api/analytics/summary`).then(r => r.json());
  const grid = document.getElementById("stat-grid");
  grid.innerHTML = `
    <div class="stat-card"><div class="value">${summary.total_clients}</div><div class="label">Total clients</div></div>
    <div class="stat-card"><div class="value">${summary.active_sips}</div><div class="label">Active SIPs</div></div>
    <div class="stat-card"><div class="value">${summary.due_soon}</div><div class="label">Due soon</div></div>
    <div class="stat-card"><div class="value">${summary.missed_sips}</div><div class="label">Missed SIPs</div></div>
    <div class="stat-card"><div class="value">${summary.high_risk_clients}</div><div class="label">High risk clients</div></div>
    <div class="stat-card"><div class="value">${summary.premium_clients}</div><div class="label">Premium clients</div></div>
  `;

  const highRisk = await fetch(`${API}/api/clients?risk_level=High`).then(r => r.json());
  const tbody = document.querySelector("#attention-table tbody");
  tbody.innerHTML = highRisk.slice(0, 10).map(c => `
    <tr>
      <td>${c.investor_name}</td>
      <td>${c.scheme}</td>
      <td>${riskBadge(c.risk_level)}</td>
      <td>${c.recommendation.action}</td>
    </tr>
  `).join("") || `<tr><td colspan="4">No high-risk clients</td></tr>`;
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
  const c = await fetch(`${API}/api/clients/${ucc}`).then(r => r.json());
  const profile = document.getElementById("client-profile");
  profile.innerHTML = `
    <h2>${c.investor_name} <span style="font-weight:400;color:var(--text-secondary)">(${c.ucc})</span></h2>
    <div class="profile-grid">
      <div class="profile-field"><div class="label">Folio No</div><div class="value">${c.folio_no}</div></div>
      <div class="profile-field"><div class="label">Holding type</div><div class="value">${c.holding_type}</div></div>
      <div class="profile-field"><div class="label">Bank details</div><div class="value">${c.bank_details}</div></div>
      <div class="profile-field"><div class="label">Scheme</div><div class="value">${c.scheme}</div></div>
      <div class="profile-field"><div class="label">SIP amount</div><div class="value">₹${c.sip_amount}</div></div>
      <div class="profile-field"><div class="label">Frequency</div><div class="value">${c.frequency}</div></div>
      <div class="profile-field"><div class="label">SIP start</div><div class="value">${c.sip_start_date}</div></div>
      <div class="profile-field"><div class="label">SIP end</div><div class="value">${c.sip_end_date}</div></div>
      <div class="profile-field"><div class="label">Next due</div><div class="value">${c.next_due_date} (${c.days_to_due}d)</div></div>
      <div class="profile-field"><div class="label">Status</div><div class="value">${c.status}</div></div>
      <div class="profile-field"><div class="label">Risk level</div><div class="value">${riskBadge(c.risk_level)}</div></div>
      <div class="profile-field"><div class="label">Missed count</div><div class="value">${c.missed_count}</div></div>
      <div class="profile-field"><div class="label">Premium client</div><div class="value">${c.is_premium ? "Yes" : "No"}</div></div>
    </div>
    <div class="assistant-answer" style="display:block">
      <strong>AI recommendation:</strong> ${c.recommendation.action} — ${c.recommendation.reason}
    </div>
  `;
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
