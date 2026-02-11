// ===== OmniTrack Public Clock Page JS =====

// Helpers
function $(id) { return document.getElementById(id); }
function safeAddClick(el, fn) { if (el) el.addEventListener("click", fn); }

// Public elements
const employeeCodeEl = $("employeeCode");
const verifyBtn = $("verifyBtn");
const employeeInfo = $("employeeInfo");
const actionBtn = $("actionBtn");
const msg = $("msg");

// TEMP admin create employee (on public page details section)
const newEmpName = $("newEmpName");
const createEmpBtn = $("createEmpBtn");
const createdEmp = $("createdEmp");

// TEMP admin activate/deactivate
const statusEmpCode = $("statusEmpCode");
const statusValue = $("statusValue");
const setStatusBtn = $("setStatusBtn");
const statusMsg = $("statusMsg");

let currentCode = null;
let nextAction = null;

function setMsg(text, ok) {
  if (!msg) return;
  msg.textContent = text || "";
  msg.className = "msg " + (ok ? "ok" : "err");
}

function show(el) { if (el) el.classList.remove("hidden"); }
function hide(el) { if (el) el.classList.add("hidden"); }

function showActionButton(state) {
  if (!actionBtn) return;

  if (state.next_action === "CLOCK_IN") {
    actionBtn.textContent = "CLOCK IN";
    show(actionBtn);
    nextAction = "CLOCK_IN";
  } else if (state.next_action === "CLOCK_OUT") {
    actionBtn.textContent = "CLOCK OUT";
    show(actionBtn);
    nextAction = "CLOCK_OUT";
  } else {
    // DONE_FOR_TODAY
    hide(actionBtn);
    nextAction = null;
    setMsg("You are already clocked out for today.", true);
  }
}

// ---- VERIFY ----
safeAddClick(verifyBtn, async () => {
  const code = (employeeCodeEl?.value || "").trim();

  setMsg("", true);
  hide(actionBtn);
  hide(employeeInfo);

  try {
    const res = await fetch("/api/public/verify", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ employee_code: code })
    });
    const data = await res.json();

    if (!data.ok) {
      setMsg(data.error || "Verification failed", false);
      return;
    }

    currentCode = data.employee.employee_code;

    if (employeeInfo) {
      employeeInfo.textContent = `Verified: ${data.employee.full_name} (ID ${currentCode})`;
      show(employeeInfo);
    }

    showActionButton(data.state);
    setMsg("Verified. Ready.", true);

  } catch (e) {
    setMsg("Server error. Try again.", false);
  }
});

// ---- CLOCK IN / OUT ----
safeAddClick(actionBtn, async () => {
  if (!currentCode || !nextAction) return;
  setMsg("", true);

  try {
    const res = await fetch("/api/public/clock", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ employee_code: currentCode, action: nextAction })
    });
    const data = await res.json();

    if (!data.ok) {
      setMsg(data.error || "Action failed", false);
      return;
    }

    showActionButton(data.state);
    setMsg(data.message, true);

  } catch (e) {
    setMsg("Server error. Try again.", false);
  }
});

// ---- TEMP ADMIN: CREATE EMPLOYEE ----
safeAddClick(createEmpBtn, async () => {
  const name = (newEmpName?.value || "").trim();
  if (createdEmp) createdEmp.textContent = "";

  try {
    const res = await fetch("/api/admin/create-employee", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ full_name: name })
    });
    const data = await res.json();

    if (!data.ok) {
      if (createdEmp) createdEmp.textContent = data.error || "Failed";
      return;
    }

    if (createdEmp) createdEmp.textContent = `Created: ${data.full_name} — ID: ${data.employee_code}`;
    if (newEmpName) newEmpName.value = "";

  } catch (e) {
    if (createdEmp) createdEmp.textContent = "Server error";
  }
});

// ---- TEMP ADMIN: ACTIVATE / DEACTIVATE ----
safeAddClick(setStatusBtn, async () => {
  const code = (statusEmpCode?.value || "").trim();
  const status = statusValue?.value;
  if (statusMsg) statusMsg.textContent = "";

  try {
    const res = await fetch("/api/admin/set-employee-status", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ employee_code: code, status })
    });
    const data = await res.json();

    if (!data.ok) {
      if (statusMsg) statusMsg.textContent = data.error || "Failed";
      return;
    }

    if (statusMsg) statusMsg.textContent = `Updated: ${data.employee_code} → ${data.status}`;

  } catch (e) {
    if (statusMsg) statusMsg.textContent = "Server error";
  }
});

