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
// Export CSVs
$("exportTodayCsvBtn").addEventListener("click", () => {
  window.location.href = "/api/manager/export/today-logs.csv";
});

$("exportWeeklyCsvBtn").addEventListener("click", () => {
  window.location.href = "/api/manager/export/weekly-summary.csv";
});

$("refreshRankingBtn").addEventListener("click", async () => {
  $("ranking").textContent = "Loading...";
  try {
    const res = await fetch("/api/manager/employee-ranking-today");
    const data = await res.json();
    if (!data.ok) { $("ranking").textContent = "Failed"; return; }

    $("ranking").innerHTML = `
      <div><strong>Date:</strong> ${data.date}</div>
      <div style="overflow:auto;margin-top:8px;">
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Rank</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Name</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">ID</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Status</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Hours</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Late</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Score</th>
            </tr>
          </thead>
          <tbody>
            ${data.employees.map((e, i) => `
              <tr>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${i + 1}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.full_name}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.employee_code}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.status}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.hours_today}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.late ? "YES" : "NO"}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;"><strong>${e.score}</strong></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch {
    $("ranking").textContent = "Server error";
  }
});

$("refreshWeeklyBtn").addEventListener("click", async () => {
  $("weekly").textContent = "Loading...";
  try {
    const res = await fetch("/api/manager/weekly-summary");
    const data = await res.json();
    if (!data.ok) { $("weekly").textContent = "Failed"; return; }

    $("weekly").innerHTML = `
      <div><strong>Week:</strong> ${data.week_start} → ${data.week_end}</div>
      <div><strong>Total Hours (completed):</strong> ${data.total_hours_completed}</div>
      <div><strong>Attendance Rate (week):</strong> ${data.attendance_rate_week}%</div>
      <div><strong>Total Late Events:</strong> ${data.total_late_events}</div>
      <div><strong>Total Missing Clock-Out:</strong> ${data.total_missing_clock_out}</div>

      <div style="overflow:auto;margin-top:10px;">
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Name</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">ID</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Days IN</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Days Completed</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Missing OUT</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Late</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Hours</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Flag</th>
            </tr>
          </thead>
          <tbody>
            ${data.employees.map(e => `
              <tr>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.full_name}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.employee_code}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.days_clocked_in}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.days_completed}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.missing_clock_out}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.late_count}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.weekly_hours}</td>
                <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.underperforming ? "⚠️" : "OK"}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch {
    $("weekly").textContent = "Server error";
  }
});

$("refreshRankingBtn").click();
$("refreshWeeklyBtn").click();

