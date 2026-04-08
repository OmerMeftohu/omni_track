function $(id){ return document.getElementById(id); }

// KPI
let attendanceChartInstance = null;
let hoursChartInstance = null;

function alertBox(html) {
  const el = document.getElementById("kpiAlerts");
  el.innerHTML = html || "";
}

function makeAlerts(k) {
  const alerts = [];

  // You can tune these thresholds
  if (k.attendance_rate < 70) alerts.push(`⚠️ Attendance is low (${k.attendance_rate}%).`);
  if (k.missing_clock_out > 0) alerts.push(`⚠️ Missing clock-outs: ${k.missing_clock_out}.`);
  if (k.active_employees > 0 && k.clocked_in_today === 0) alerts.push(`⚠️ No one has clocked in today.`);
  if (k.clocked_out_today > 0 && k.avg_hours_per_completed < 6) alerts.push(`⚠️ Average completed hours is low (${k.avg_hours_per_completed}).`);

  if (alerts.length === 0) {
    return `<div class="msg ok">✅ KPIs look normal today.</div>`;
  }

  return `<div class="msg err">${alerts.map(a => `<div>${a}</div>`).join("")}</div>`;
}

function renderCharts(k) {
  // Destroy old charts to avoid duplicates on refresh
  if (attendanceChartInstance) attendanceChartInstance.destroy();
  if (hoursChartInstance) hoursChartInstance.destroy();

  // Attendance doughnut: clocked in vs not clocked in (active employees)
  const notClockedIn = Math.max(k.active_employees - k.clocked_in_today, 0);
  const attCtx = document.getElementById("attendanceChart").getContext("2d");

  attendanceChartInstance = new Chart(attCtx, {
    type: "doughnut",
    data: {
      labels: ["Clocked In", "Not Clocked In"],
      datasets: [{
        data: [k.clocked_in_today, notClockedIn]
      }]
    },
    options: {
      plugins: {
        title: { display: true, text: "Attendance (Active Employees)" }
      }
    }
  });

  // Hours bar: total completed hours + avg completed hours
  const hoursCtx = document.getElementById("hoursChart").getContext("2d");

  hoursChartInstance = new Chart(hoursCtx, {
    type: "bar",
    data: {
      labels: ["Total Hours (Completed)", "Avg Hours (Completed)"],
      datasets: [{
        data: [k.total_hours_completed, k.avg_hours_per_completed]
      }]
    },
    options: {
      plugins: {
        title: { display: true, text: "Work Hours (Completed Sessions)" }
      },
      scales: {
        y: { beginAtZero: true }
      }
    }
  });
}

document.getElementById("refreshKpisBtn").addEventListener("click", async () => {
  document.getElementById("kpis").textContent = "Loading...";
  alertBox("");

  try {
    const res = await fetch("/api/manager/kpis");
    const k = await res.json();

    if (!k.ok) {
      document.getElementById("kpis").textContent = "Failed to load KPIs";
      return;
    }

    // Text KPIs
    document.getElementById("kpis").innerHTML = `
      <div><strong>Date:</strong> ${k.date}</div>
      <div><strong>Active Employees:</strong> ${k.active_employees}</div>
      <div><strong>Clocked In Today:</strong> ${k.clocked_in_today} (${k.attendance_rate}%)</div>
      <div><strong>Clocked Out Today:</strong> ${k.clocked_out_today}</div>
      <div><strong>Missing Clock-In:</strong> ${k.missing_clock_in}</div>
      <div><strong>Missing Clock-Out:</strong> ${k.missing_clock_out}</div>
      <div><strong>Total Hours (completed):</strong> ${k.total_hours_completed}</div>
      <div><strong>Avg Hours (completed):</strong> ${k.avg_hours_per_completed}</div>
    `;

    // Alerts
    alertBox(makeAlerts(k));

    // Charts
    renderCharts(k);

  } catch (e) {
    document.getElementById("kpis").textContent = "Server error";
    alertBox(`<div class="msg err">⚠️ KPI API error. Check server.</div>`);
  }
});

// Optional: auto-load on page open
document.getElementById("refreshKpisBtn").click();

$("refreshKpisBtn").addEventListener("click", async () => {
  $("kpis").textContent = "Loading...";
  try {
    const res = await fetch("/api/manager/kpis");
    const data = await res.json();

    if (!data.ok) {
      $("kpis").textContent = "Failed to load KPIs";
      return;
    }

    $("kpis").innerHTML = `
      <div><strong>Date:</strong> ${data.date}</div>
      <div><strong>Active Employees:</strong> ${data.active_employees}</div>
      <div><strong>Clocked In Today:</strong> ${data.clocked_in_today} (${data.attendance_rate}%)</div>
      <div><strong>Clocked Out Today:</strong> ${data.clocked_out_today}</div>
      <div><strong>Missing Clock-In:</strong> ${data.missing_clock_in}</div>
      <div><strong>Missing Clock-Out:</strong> ${data.missing_clock_out}</div>
      <div><strong>Total Hours (completed):</strong> ${data.total_hours_completed}</div>
      <div><strong>Avg Hours (completed):</strong> ${data.avg_hours_per_completed}</div>
    `;
  } catch {
    $("kpis").textContent = "Server error";
  }
});

// Load time logs
$("refreshLogsBtn").addEventListener("click", async () => {
  $("logs").textContent = "Loading...";
  try {
    const res = await fetch("/api/supervisor/today-logs");
    const data = await res.json();

    if (!data.ok) {
      $("logs").textContent = "Failed to load logs";
      return;
    }

    if (!data.logs || data.logs.length === 0) {
      $("logs").textContent = "No logs today.";
      return;
    }

    $("logs").innerHTML = data.logs.map(x =>
      `<div>• ${x.full_name} (ID ${x.employee_code}) — IN: ${x.clock_in_time || "-"} OUT: ${x.clock_out_time || "-"}</div>`
    ).join("");
  } catch {
    $("logs").textContent = "Server error";
  }
});

// Load daily reports
$("refreshReportsBtn").addEventListener("click", async () => {
  $("reports").textContent = "Loading...";
  try {
    const res = await fetch("/api/manager/daily-reports");
    const data = await res.json();

    if (!data.ok) {
      $("reports").textContent = "Failed to load reports";
      return;
    }

    if (!data.reports || data.reports.length === 0) {
      $("reports").textContent = "No reports submitted.";
      return;
    }

    $("reports").innerHTML = data.reports.map(r =>
      `<div style="margin-bottom:10px;">
        <strong>${r.supervisor_name}</strong> (${r.report_date})<br/>
        ${r.summary}
      </div>`
    ).join("");
  } catch {
    $("reports").textContent = "Server error";
  }
});

// Create To-Do (requires backend /api/manager/todos)
document.getElementById("createTodoBtn").addEventListener("click", async () => {
  const scope = document.getElementById("todoScope").value;
  const title = document.getElementById("todoTitle").value.trim();
  const details = document.getElementById("todoDetails").value.trim();
  const due_date = document.getElementById("todoDue").value;

  const todoMsg = document.getElementById("todoMsg");
  todoMsg.textContent = "";

  if (!title) { todoMsg.textContent = "Title required"; return; }

  try {
    const res = await fetch("/api/manager/todos", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ scope, title, details, due_date })
    });
    const data = await res.json();

    if (!data.ok) { todoMsg.textContent = data.error || "Failed"; return; }

    todoMsg.textContent = "✅ To-Do created.";
    document.getElementById("todoTitle").value = "";
    document.getElementById("todoDetails").value = "";
    document.getElementById("todoDue").value = "";
  } catch {
    todoMsg.textContent = "Server error";
  }

  
});
// ---------- Productivity Score Calculator (per employee: totalScore += hours * priority per task) ----------
const productivityTasksByEmployee = {};
const productivityScoreHistoryByEmployee = {};
const productivityScoreTimeseriesByEmployee = {}; // { [employee_code]: { daily|weekly|monthly: {labels, values} } }
let productivityScoreRange = "daily";
let productivityScoreChartInstance = null;

function getProductivityEmployeeCode() {
  const sel = $("productivityEmployee");
  return sel ? sel.value : "";
}

function getProductivityTasksList() {
  const code = getProductivityEmployeeCode();
  if (!code) return [];
  if (!productivityTasksByEmployee[code]) productivityTasksByEmployee[code] = [];
  return productivityTasksByEmployee[code];
}

function renderProductivityTaskList() {
  const list = getProductivityTasksList();
  const el = $("productivityTaskList");
  const outEl = $("productivityScoreOut");
  const msgEl = $("productivityScoreMsg");
  if (!el || !outEl) return;

  let totalScore = 0;
  list.forEach((t) => { totalScore += t.hours * t.priority; });

  if (list.length === 0) {
    el.innerHTML = "";
    outEl.textContent = "";
    if (msgEl) msgEl.textContent = "Add tasks to see productivity score.";
    return;
  }

  el.innerHTML = `
    <table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
      <thead>
        <tr>
          <th style="text-align:left;padding:6px;border-bottom:1px solid var(--border);">Task</th>
          <th style="text-align:right;padding:6px;border-bottom:1px solid var(--border);">Hours</th>
          <th style="text-align:right;padding:6px;border-bottom:1px solid var(--border);">Priority</th>
          <th style="text-align:right;padding:6px;border-bottom:1px solid var(--border);">Contribution</th>
        </tr>
      </thead>
      <tbody>
        ${list.map((t) => `
          <tr>
            <td style="padding:6px;border-bottom:1px solid var(--border);">${escapeHtml(t.taskName)}</td>
            <td style="text-align:right;padding:6px;border-bottom:1px solid var(--border);">${t.hours}</td>
            <td style="text-align:right;padding:6px;border-bottom:1px solid var(--border);">${t.priority}</td>
            <td style="text-align:right;padding:6px;border-bottom:1px solid var(--border);"><strong>${(t.hours * t.priority).toFixed(1)}</strong></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
  outEl.textContent = `Total Productivity Score: ${totalScore.toFixed(1)}`;
  if (msgEl) msgEl.textContent = `Formula: sum of (hours × priority) for ${list.length} task(s).`;
}

function getCurrentProductivityTotalScore() {
  const list = getProductivityTasksList();
  return list.reduce((acc, t) => acc + t.hours * t.priority, 0);
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

async function loadProductivityEmployees() {
  const sel = $("productivityEmployee");
  const histSel = $("productivityHistoryEmployee");
  if (!sel && !histSel) return;
  try {
    const res = await fetch("/api/supervisor/employees");
    const data = await res.json();
    if (!data.ok || !data.employees) return;
    const optsHtml = data.employees
      .map((e) => `<option value="${escapeHtml(e.employee_code)}">${escapeHtml(e.full_name)} (${e.employee_code})</option>`)
      .join("");
    if (sel) {
      sel.innerHTML = '<option value="">— Select employee —</option>' + optsHtml;
    }
    if (histSel) {
      histSel.innerHTML = '<option value="">— Select employee —</option>' + optsHtml;
    }
  } catch {
    if (sel) sel.innerHTML = '<option value="">— Load failed —</option>';
    if (histSel) histSel.innerHTML = '<option value="">— Load failed —</option>';
  }
}

$("productivityEmployee").addEventListener("change", () => {
  renderProductivityTaskList();
  const code = getProductivityEmployeeCode();
  const histSel = $("productivityHistoryEmployee");
  if (histSel && (!histSel.value || histSel.value === "")) {
    histSel.value = code;
  }
  const histCode = getProductivityHistoryEmployeeCode();
  if (histCode) fetchAndSetProductivityHistory(histCode);
  else renderProductivityScoreChart();
});

$("addProductivityTaskBtn").addEventListener("click", () => {
  const code = getProductivityEmployeeCode();
  if (!code) {
    ($("productivityScoreMsg") || $("productivityTaskList")).textContent = "Select an employee first.";
    return;
  }
  const taskName = ($("productivityTask") && $("productivityTask").value || "").trim();
  const hoursRaw = $("productivityHours") && $("productivityHours").value;
  const priorityRaw = $("productivityPriority") && $("productivityPriority").value;
  const hours = parseFloat(hoursRaw);
  const priority = parseInt(priorityRaw, 10);

  if (!taskName) {
    ($("productivityScoreMsg") || $("productivityTaskList")).textContent = "Enter a task name.";
    return;
  }
  if (isNaN(hours) || hours < 0) {
    ($("productivityScoreMsg") || $("productivityTaskList")).textContent = "Enter valid hours (≥ 0).";
    return;
  }
  if (isNaN(priority) || priority < 1 || priority > 10) {
    ($("productivityScoreMsg") || $("productivityTaskList")).textContent = "Enter priority between 1 and 10.";
    return;
  }

  getProductivityTasksList().push({ taskName, hours, priority });
  if ($("productivityTask")) $("productivityTask").value = "";
  if ($("productivityHours")) $("productivityHours").value = "";
  if ($("productivityPriority")) $("productivityPriority").value = "";
  ($("productivityScoreMsg") || $("productivityTaskList")).textContent = "";
  renderProductivityTaskList();
});

$("clearProductivityTasksBtn").addEventListener("click", () => {
  const code = getProductivityEmployeeCode();
  if (!code) return;
  productivityTasksByEmployee[code] = [];
  renderProductivityTaskList();
});

loadProductivityEmployees();
renderProductivityTaskList();
renderProductivityScoreChart();

function setProductivityScoreRange(range) {
  productivityScoreRange = range;

  const monthlyBtn = $("productivityScoreRangeMonthly");
  const weeklyBtn = $("productivityScoreRangeWeekly");
  const dailyBtn = $("productivityScoreRangeDaily");

  const updateBtn = (btn, isActive) => {
    if (!btn) return;
    btn.classList.toggle("ok", isActive);
    btn.classList.toggle("secondary", !isActive);
  };

  updateBtn(monthlyBtn, range === "monthly");
  updateBtn(weeklyBtn, range === "weekly");
  updateBtn(dailyBtn, range === "daily");

  const code = getProductivityHistoryEmployeeCode();
  if (code) {
    fetchAndSetProductivityHistory(code);
  } else {
    renderProductivityScoreChart();
  }
}

const monthlyBtn = $("productivityScoreRangeMonthly");
if (monthlyBtn) monthlyBtn.addEventListener("click", () => setProductivityScoreRange("monthly"));
const weeklyBtn = $("productivityScoreRangeWeekly");
if (weeklyBtn) weeklyBtn.addEventListener("click", () => setProductivityScoreRange("weekly"));
const dailyBtn = $("productivityScoreRangeDaily");
if (dailyBtn) dailyBtn.addEventListener("click", () => setProductivityScoreRange("daily"));

// Default selected range: Daily
setProductivityScoreRange(productivityScoreRange);

function getProductivityHistoryEmployeeCode() {
  const histSel = $("productivityHistoryEmployee");
  if (histSel && histSel.value) return histSel.value;
  return getProductivityEmployeeCode();
}

function getProductivityHistory() {
  const code = getProductivityHistoryEmployeeCode();
  if (!code) return [];
  return productivityScoreHistoryByEmployee[code] || [];
}

function renderProductivityScoreChart() {
  const code = getProductivityHistoryEmployeeCode();
  const msgEl = $("productivityScoreHistoryMsg");
  const canvas = $("productivityScoreChart");

  if (!canvas) return;

  if (productivityScoreChartInstance) {
    productivityScoreChartInstance.destroy();
    productivityScoreChartInstance = null;
  }

  if (!code) {
    const ctx = canvas.getContext("2d");
    if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (msgEl) msgEl.textContent = "Select an employee to log and view scores.";
    return;
  }

  const seriesObj = productivityScoreTimeseriesByEmployee[code]
    && productivityScoreTimeseriesByEmployee[code][productivityScoreRange];

  if (!seriesObj) {
    const ctx = canvas.getContext("2d");
    if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (msgEl) msgEl.textContent = "Loading scores...";
    return;
  }

  const labels = seriesObj.labels || [];
  const scores = seriesObj.values || [];

  if (labels.length === 0 || scores.length === 0) {
    const ctx = canvas.getContext("2d");
    if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (msgEl) msgEl.textContent = `No scores recorded for this employee (${productivityScoreRange}).`;
    return;
  }

  const xTitleMap = {
    daily: "Date (MM/DD)",
    weekly: "Week Num/Month",
    monthly: "Month (MM/YYYY)"
  };

  const datasetLabelMap = {
    daily: "Daily Avg Score",
    weekly: "Weekly Avg Score",
    monthly: "Monthly Avg Score"
  };

  const ctx = canvas.getContext("2d");
  productivityScoreChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: datasetLabelMap[productivityScoreRange] || "Productivity Score",
        data: scores,
        borderColor: "rgba(255,255,255,0.8)",
        backgroundColor: "rgba(255,255,255,0.15)",
        tension: 0.25,
        pointRadius: 3
      }]
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `Avg Score: ${ctx.parsed.y}`
          }
        }
      },
      scales: {
        x: { display: true, title: { display: true, text: xTitleMap[productivityScoreRange] || "Date" } },
        y: { beginAtZero: true, title: { display: true, text: "Score" } }
      }
    }
  });

  if (msgEl) msgEl.textContent = `Showing ${labels.length} ${productivityScoreRange} point(s) for employee ${code}.`;
}

async function fetchAndSetProductivityHistory(code) {
  const msgEl = $("productivityScoreHistoryMsg");
  if (!code) {
    if (msgEl) msgEl.textContent = "Select an employee to log and view scores.";
    return;
  }

  const expectedRange = productivityScoreRange;
  try {
    if (msgEl) msgEl.textContent = "Loading scores...";
    const res = await fetch(`/api/manager/productivity-score-timeseries?employee_code=${encodeURIComponent(code)}&range=${encodeURIComponent(expectedRange)}`);
    const data = await res.json();
    if (!data.ok) {
      if (msgEl) msgEl.textContent = data.error || "Failed to load scores.";
      productivityScoreTimeseriesByEmployee[code] = productivityScoreTimeseriesByEmployee[code] || {};
      productivityScoreTimeseriesByEmployee[code][expectedRange] = { labels: [], values: [] };
      renderProductivityScoreChart();
      return;
    }

    // If user switched ranges while request was in-flight, ignore stale response.
    if (expectedRange !== productivityScoreRange) return;

    productivityScoreTimeseriesByEmployee[code] = productivityScoreTimeseriesByEmployee[code] || {};
    productivityScoreTimeseriesByEmployee[code][expectedRange] = {
      labels: data.labels || [],
      values: data.values || []
    };
    renderProductivityScoreChart();
  } catch {
    if (msgEl) msgEl.textContent = "Server error while loading scores.";
  }
}

$("addProductivityScorePointBtn").addEventListener("click", async () => {
  const code = getProductivityEmployeeCode();
  const msgEl = $("productivityScoreHistoryMsg");

  if (!code) {
    if (msgEl) msgEl.textContent = "Select an employee before logging a score.";
    return;
  }

  const totalScore = getCurrentProductivityTotalScore();

  if (!Number.isFinite(totalScore)) {
    if (msgEl) msgEl.textContent = "Current score is not valid.";
    return;
  }

  try {
    const res = await fetch("/api/manager/productivity-scores", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ employee_code: code, score: Number(totalScore.toFixed(1)) })
    });
    const data = await res.json();
    if (!data.ok) {
      if (msgEl) msgEl.textContent = data.error || "Failed to save score.";
      return;
    }
    productivityScoreHistoryByEmployee[code] = data.scores || [];
    const histSel = $("productivityHistoryEmployee");
    if (histSel) histSel.value = code;
    delete productivityScoreTimeseriesByEmployee[code]; // refresh chart for current range
    if (msgEl) msgEl.textContent = `Logged score ${totalScore.toFixed(1)} for employee ${code}.`;
    fetchAndSetProductivityHistory(code);
  } catch {
    if (msgEl) msgEl.textContent = "Server error while saving score.";
  }
});

const histSelect = $("productivityHistoryEmployee");
if (histSelect) {
  histSelect.addEventListener("change", () => {
    const code = getProductivityHistoryEmployeeCode();
    if (!code) {
      renderProductivityScoreChart();
    } else {
      fetchAndSetProductivityHistory(code);
    }
  });
}

const deleteLastBtn = $("deleteLastProductivityScoreBtn");
if (deleteLastBtn) {
  deleteLastBtn.addEventListener("click", async () => {
    const code = getProductivityHistoryEmployeeCode();
    const msgEl = $("productivityScoreHistoryMsg");
    if (!code) {
      if (msgEl) msgEl.textContent = "Select an employee to delete a score.";
      return;
    }
    try {
      const res = await fetch("/api/manager/productivity-scores/delete-last", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ employee_code: code })
      });
      const data = await res.json();
      if (!data.ok) {
        if (msgEl) msgEl.textContent = data.error || "Failed to delete last score.";
        return;
      }
      productivityScoreHistoryByEmployee[code] = data.scores || [];
      delete productivityScoreTimeseriesByEmployee[code]; // refresh chart for current range
      if (msgEl) msgEl.textContent = "Last score deleted.";
      fetchAndSetProductivityHistory(code);
    } catch {
      if (msgEl) msgEl.textContent = "Server error while deleting last score.";
    }
  });
}

// Initial: just render empty chart state; history will be fetched when an employee is selected
renderProductivityScoreChart();

// Change Password
$("changePasswordBtn").addEventListener("click", async () => {
  const currentPassword = $("currentPassword").value.trim();
  const newEmail = $("newEmail").value.trim();
  const newPassword = $("newPassword").value.trim();
  const confirmNewPassword = $("confirmNewPassword").value.trim();
  const msgEl = $("changePasswordMsg");

  if (!currentPassword) {
    msgEl.textContent = "Current password is required.";
    return;
  }

  if (!newEmail && !newPassword) {
    msgEl.textContent = "At least one of new email or new password must be provided.";
    return;
  }

  // Validate email if provided
  if (newEmail) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(newEmail)) {
      msgEl.textContent = "Please enter a valid email address.";
      return;
    }
  }

  // Validate password if provided
  if (newPassword) {
    if (newPassword !== confirmNewPassword) {
      msgEl.textContent = "New passwords do not match.";
      return;
    }
    if (newPassword.length < 6) {
      msgEl.textContent = "New password must be at least 6 characters.";
      return;
    }
  } else if (confirmNewPassword) {
    msgEl.textContent = "Please enter a new password or leave confirm password empty.";
    return;
  }

  try {
    const res = await fetch("/api/manager/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        current_password: currentPassword, 
        new_email: newEmail || null,
        new_password: newPassword || null 
      })
    });
    const data = await res.json();
    if (!data.ok) {
      msgEl.textContent = data.error || "Failed to update account.";
      return;
    }
    msgEl.textContent = "Account updated successfully. Please log in again if you changed your email.";
    $("currentPassword").value = "";
    $("newEmail").value = "";
    $("newPassword").value = "";
    $("confirmNewPassword").value = "";
  } catch {
    msgEl.textContent = "Server error.";
  }
});

// Create Supervisor
$("createSupervisorBtn").addEventListener("click", async () => {
  const email = $("supervisorEmail").value.trim();
  const password = $("supervisorPassword").value.trim();
  const msgEl = $("createSupervisorMsg");

  if (!email || !password) {
    msgEl.textContent = "Email and password are required.";
    return;
  }
  if (password.length < 6) {
    msgEl.textContent = "Password must be at least 6 characters.";
    return;
  }

  try {
    const res = await fetch("/api/manager/create-supervisor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: password })
    });
    const data = await res.json();
    if (!data.ok) {
      msgEl.textContent = data.error || "Failed to create supervisor.";
      return;
    }
    msgEl.textContent = `Supervisor created: ${email}`;
    $("supervisorEmail").value = "";
    $("supervisorPassword").value = "";
  } catch {
    msgEl.textContent = "Server error.";
  }
});

// Manage Supervisors
async function loadSupervisors() {
  const listEl = $("supervisorsList");
  try {
    const res = await fetch("/api/manager/supervisors");
    const data = await res.json();
    if (!data.ok) {
      listEl.innerHTML = data.error || "Failed to load supervisors.";
      return;
    }
    if (data.supervisors.length === 0) {
      listEl.innerHTML = "No supervisors found.";
      return;
    }
    listEl.innerHTML = `
      <table style="width:100%;border-collapse:collapse;font-size:0.9rem;">
        <thead>
          <tr>
            <th style="text-align:left;padding:6px;border-bottom:1px solid var(--border);">Email</th>
            <th style="text-align:left;padding:6px;border-bottom:1px solid var(--border);">Created</th>
            <th style="text-align:left;padding:6px;border-bottom:1px solid var(--border);">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${data.supervisors.map(s => `
            <tr>
              <td style="padding:6px;border-bottom:1px solid var(--border);">${escapeHtml(s.email)}</td>
              <td style="padding:6px;border-bottom:1px solid var(--border);">${s.created_at}</td>
              <td style="padding:6px;border-bottom:1px solid var(--border);">
                <button onclick="deleteSupervisor(${s.id}, '${escapeHtml(s.email)}')">Delete</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  } catch {
    listEl.innerHTML = "Server error.";
  }
}

async function deleteSupervisor(id, email) {
  if (!confirm(`Delete supervisor ${email}?`)) return;
  try {
    const res = await fetch("/api/manager/delete-supervisor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: id })
    });
    const data = await res.json();
    if (!data.ok) {
      alert(data.error || "Failed to delete supervisor.");
      return;
    }
    loadSupervisors();
  } catch {
    alert("Server error.");
  }
}

$("refreshSupervisorsBtn").addEventListener("click", loadSupervisors);

// Load supervisors on page load
loadSupervisors();

// Set default dates for CSV to today
(function () {
  const today = new Date().toISOString().slice(0, 10);
  $("csvFromDate").value = today;
  $("csvToDate").value   = today;
})();

// Export CSV
function _csvDates() {
  const today = new Date().toISOString().slice(0, 10);
  const from  = $("csvFromDate").value || today;
  const to    = $("csvToDate").value   || today;
  return { from, to };
}

$("previewCsvBtn").addEventListener("click", async () => {
  const { from, to } = _csvDates();
  const limit  = Math.min(50, parseInt($("csvLimit").value) || 20);
  const msgEl  = $("exportCsvMsg");
  const tblEl  = $("csvPreviewTable");
  msgEl.textContent = "Loading preview...";
  tblEl.innerHTML   = "";
  try {
    const res  = await fetch(`/api/manager/export/preview?from_date=${from}&to_date=${to}&limit=${limit}`);
    const data = await res.json();
    if (!data.ok) { msgEl.textContent = data.error || "Failed to load preview."; return; }
    msgEl.textContent = `${data.total} total record(s) between ${from} and ${to}. Showing up to ${limit}.`;
    if (data.rows.length === 0) { tblEl.innerHTML = "<p class='muted'>No records in this range.</p>"; return; }
    tblEl.innerHTML = `
      <table style="width:100%;border-collapse:collapse;font-size:0.85rem;">
        <thead>
          <tr>
            <th style="padding:6px;border-bottom:1px solid var(--border);text-align:left;">Date</th>
            <th style="padding:6px;border-bottom:1px solid var(--border);text-align:left;">Name</th>
            <th style="padding:6px;border-bottom:1px solid var(--border);text-align:left;">Code</th>
            <th style="padding:6px;border-bottom:1px solid var(--border);text-align:left;">Clock In</th>
            <th style="padding:6px;border-bottom:1px solid var(--border);text-align:left;">Clock Out</th>
            <th style="padding:6px;border-bottom:1px solid var(--border);text-align:left;">Status</th>
          </tr>
        </thead>
        <tbody>
          ${data.rows.map(r => `
            <tr>
              <td style="padding:5px;border-bottom:1px solid var(--border);">${r.work_date}</td>
              <td style="padding:5px;border-bottom:1px solid var(--border);">${escapeHtml(r.full_name)}</td>
              <td style="padding:5px;border-bottom:1px solid var(--border);">${r.employee_code}</td>
              <td style="padding:5px;border-bottom:1px solid var(--border);">${r.clock_in_time || "-"}</td>
              <td style="padding:5px;border-bottom:1px solid var(--border);">${r.clock_out_time || "-"}</td>
              <td style="padding:5px;border-bottom:1px solid var(--border);">${r.entry_status}</td>
            </tr>`).join("")}
        </tbody>
      </table>`;
  } catch {
    msgEl.textContent = "Server error during preview.";
  }
});

$("exportCsvBtn").addEventListener("click", () => {
  const { from, to } = _csvDates();
  const page  = parseInt($("csvPage").value)  || 1;
  const limit = parseInt($("csvLimit").value) || 100;
  const msgEl = $("exportCsvMsg");
  if (page < 1 || limit < 1) { msgEl.textContent = "Page and limit must be at least 1."; return; }
  msgEl.textContent = "Downloading...";
  window.location.href = `/api/manager/export/today-logs.csv?from_date=${from}&to_date=${to}&page=${page}&limit=${limit}`;
  setTimeout(() => { msgEl.textContent = ""; }, 3000);
});

// Load all todos (manager view)
async function loadTodosList() {
  const listEl = $("todosList");
  listEl.textContent = "Loading...";
  try {
    const res  = await fetch("/api/manager/todos");
    const data = await res.json();
    if (!data.ok) { listEl.textContent = data.error || "Failed."; return; }
    if (data.todos.length === 0) { listEl.textContent = "No todos yet."; return; }
    listEl.innerHTML = data.todos.map(t => `
      <div style="margin-bottom:10px;padding:8px;border:1px solid var(--border);border-radius:8px;">
        <strong>[${t.scope}]</strong> ${escapeHtml(t.title)}
        <span style="float:right;font-size:0.8rem;" class="muted">${t.status}</span><br/>
        ${t.details ? `<span class="muted">${escapeHtml(t.details)}</span><br/>` : ""}
        <span class="muted">Due: ${t.due_date || "—"} &nbsp;|&nbsp; Created: ${t.created_at.slice(0,10)}</span>
      </div>`).join("");
  } catch {
    listEl.textContent = "Server error.";
  }
}

$("refreshTodosListBtn").addEventListener("click", loadTodosList);
loadTodosList();
