// Simple “session” via browser localStorage (security later)
const path = window.location.pathname;

function $(id) { return document.getElementById(id); }

if (path === "/supervisor") {
  const supLoginBtn = $("supLoginBtn");
  const supName = $("supName");
  const supMsg = $("supMsg");

  supLoginBtn.addEventListener("click", () => {
    const name = supName.value.trim();
    if (!name) {
      supMsg.textContent = "Enter supervisor name.";
      supMsg.className = "msg err";
      return;
    }
    localStorage.setItem("supervisor_name", name);
    window.location.href = "/supervisor/dashboard";
  });
}

if (path === "/supervisor/dashboard") {
  const name = localStorage.getItem("supervisor_name") || "Supervisor";
  $("welcome").textContent = `Welcome, ${name}`;

  // Create employee
  $("createEmpBtn2").addEventListener("click", async () => {
    const full_name = $("empName").value.trim();
    $("createMsg").textContent = "";
    if (!full_name) return;

    try {
      const res = await fetch("/api/admin/create-employee", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name })
      });
      const data = await res.json();

      if (!data.ok) {
        $("createMsg").textContent = data.error || "Failed";
        return;
      }

      $("createMsg").textContent = `Created ${data.full_name} — ID: ${data.employee_code}`;
      $("empName").value = "";
    } catch {
      $("createMsg").textContent = "Server error";
    }
  });

  // Manager To-Do list (requires backend /api/supervisor/todos)
  $("refreshTodosBtn").addEventListener("click", async () => {
    const box = $("todos");
    box.textContent = "Loading...";

    try {
      const res = await fetch("/api/supervisor/todos");
      const data = await res.json();

      if (!data.ok) { box.textContent = data.error || "Failed"; return; }
      if (!data.todos || data.todos.length === 0) { box.textContent = "No open tasks."; return; }

      box.innerHTML = data.todos.map(t =>
        `<div style="margin-bottom:10px;">
          <strong>${t.scope}</strong> — ${t.title}<br/>
          ${t.details || ""}<br/>
          <span class="muted">Due: ${t.due_date || "-"}</span>
        </div>`
      ).join("");
    } catch {
      box.textContent = "Server error";
    }
  });

  // Activate/deactivate
  $("setStatusBtn2").addEventListener("click", async () => {
    const employee_code = $("empCode2").value.trim();
    const status = $("status2").value;
    $("statusMsg2").textContent = "";

    try {
      const res = await fetch("/api/admin/set-employee-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ employee_code, status })
      });
      const data = await res.json();

      if (!data.ok) {
        $("statusMsg2").textContent = data.error || "Failed";
        return;
      }

      $("statusMsg2").textContent = `Updated: ${data.employee_code} → ${data.status}`;
    } catch {
      $("statusMsg2").textContent = "Server error";
    }
  });
// Load employee list
  $("refreshEmployeesBtn").addEventListener("click", async () => {
  const box = $("employeeList");
  box.textContent = "Loading...";

  try {
    const res = await fetch("/api/supervisor/employees");
    const data = await res.json();

    if (!data.ok) { box.textContent = data.error || "Failed"; return; }
    if (!data.employees || data.employees.length === 0) { box.textContent = "No employees yet."; return; }

    box.innerHTML = `
      <div style="overflow:auto;">
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Name</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">ID</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Status</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Today IN</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Today OUT</th>
              <th style="text-align:left;padding:8px;border-bottom:1px solid #eee;">Action</th>
            </tr>
          </thead>
          <tbody>
            ${data.employees.map(e => {
              const nextStatus = e.status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
              const btnLabel = e.status === "ACTIVE" ? "Deactivate" : "Activate";
              return `
                <tr>
                  <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.full_name}</td>
                  <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.employee_code}</td>
                  <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.status}</td>
                  <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.clock_in_time || "-"}</td>
                  <td style="padding:8px;border-bottom:1px solid #f3f3f3;">${e.clock_out_time || "-"}</td>
                  <td style="padding:8px;border-bottom:1px solid #f3f3f3;">
                    <button class="toggleStatusBtn" data-code="${e.employee_code}" data-status="${nextStatus}">
                      ${btnLabel}
                    </button>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;

    // attach click handlers to toggle buttons
    document.querySelectorAll(".toggleStatusBtn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const employee_code = btn.getAttribute("data-code");
        const status = btn.getAttribute("data-status");

        try {
          const res2 = await fetch("/api/admin/set-employee-status", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ employee_code, status })
          });
          const out = await res2.json();
          if (!out.ok) {
            alert(out.error || "Failed");
            return;
          }
          // refresh list after update
          $("refreshEmployeesBtn").click();
        } catch {
          alert("Server error");
        }
      });
    });

  } catch {
    box.textContent = "Server error";
  }
});


  // Submit daily report
  $("submitReportBtn").addEventListener("click", async () => {
    const supervisor_name = localStorage.getItem("supervisor_name") || "Supervisor";
    const summary = $("reportText").value.trim();
    const reportMsg = $("reportMsg");

    reportMsg.textContent = "";

    if (!summary) {
      reportMsg.textContent = "Write something before submitting.";
      return;
    }

    try {
      const res = await fetch("/api/supervisor/daily-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ supervisor_name, summary })
      });
      const data = await res.json();

      if (!data.ok) {
        reportMsg.textContent = data.error || "Failed to submit";
        return;
      }

      reportMsg.textContent = "✅ Daily report submitted.";
      $("reportText").value = "";
    } catch {
      reportMsg.textContent = "Server error";
    }
  });

  // Today logs
  $("refreshLogsBtn").addEventListener("click", async () => {
    $("logs").textContent = "Loading...";

    try {
      const res = await fetch("/api/supervisor/today-logs");
      const data = await res.json();

      if (!data.ok) {
        $("logs").textContent = data.error || "Failed to load logs";
        return;
      }

      if (!data.logs || data.logs.length === 0) {
        $("logs").textContent = "No logs yet today.";
        return;
      }

      $("logs").innerHTML = data.logs.map(x =>
        `<div>• ${x.full_name} (ID ${x.employee_code}) — IN: ${x.clock_in_time || "-"} OUT: ${x.clock_out_time || "-"}</div>`
      ).join("");
    } catch {
      $("logs").textContent = "Server error";
    }
  });

  // Change Password
  $("changePasswordBtn").addEventListener("click", async () => {
    const currentPassword = $("currentPassword").value.trim();
    const newPassword = $("newPassword").value.trim();
    const confirmNewPassword = $("confirmNewPassword").value.trim();
    const msgEl = $("changePasswordMsg");

    if (!currentPassword) {
      msgEl.textContent = "Current password is required.";
      return;
    }

    if (!newPassword) {
      msgEl.textContent = "New password is required.";
      return;
    }

    if (newPassword !== confirmNewPassword) {
      msgEl.textContent = "New passwords do not match.";
      return;
    }

    if (newPassword.length < 6) {
      msgEl.textContent = "New password must be at least 6 characters.";
      return;
    }

    try {
      const res = await fetch("/api/supervisor/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          current_password: currentPassword, 
          new_password: newPassword 
        })
      });
      const data = await res.json();
      if (!data.ok) {
        msgEl.textContent = data.error || "Failed to change password.";
        return;
      }
      msgEl.textContent = "Password changed successfully.";
      $("currentPassword").value = "";
      $("newPassword").value = "";
      $("confirmNewPassword").value = "";
    } catch {
      msgEl.textContent = "Server error.";
    }
  });
}


