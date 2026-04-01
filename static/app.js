// ===== OmniTrack Public Clock Page JS =====

// Helpers
function $(id) { return document.getElementById(id); }
function safeAddClick(el, fn) { if (el) el.addEventListener("click", fn); }

// Public elements
const employeeCodeEl = $("employeeCode");
const verifyBtn = $("verifyBtn");
const employeeInfo = $("employeeInfo");
const employeeName = $("employeeName");
const employeeStatus = $("employeeStatus");
const actionBtn = $("actionBtn");
const msg = $("msg");
const loading = $("loading");

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

function setMsg(text, type = "info") {
  if (!msg) return;
  msg.textContent = text || "";
  msg.className = `message ${type}`;
}

function showLoading() { if (loading) loading.classList.remove("hidden"); }
function hideLoading() { if (loading) loading.classList.add("hidden"); }

function show(el) { if (el) el.classList.remove("hidden"); }
function hide(el) { if (el) el.classList.add("hidden"); }

function showActionButton(state) {
  if (!actionBtn) return;

  // Handle case where state is a string (error case)
  if (typeof state === 'string') {
    hide(actionBtn);
    nextAction = null;
    return;
  }

  if (state.next_action === "CLOCK_IN") {
    actionBtn.textContent = "🕐 CLOCK IN";
    show(actionBtn);
    nextAction = "CLOCK_IN";
  } else if (state.next_action === "CLOCK_OUT") {
    actionBtn.textContent = "🕑 CLOCK OUT";
    show(actionBtn);
    nextAction = "CLOCK_OUT";
  } else {
    // DONE_FOR_TODAY
    hide(actionBtn);
    nextAction = null;
    setMsg("✅ You are already clocked out for today.", "success");
  }
}

// ---- VERIFY ----
safeAddClick(verifyBtn, async () => {
  const code = (employeeCodeEl?.value || "").trim();

  setMsg("", "info");
  hide(actionBtn);
  hide(employeeInfo);
  showLoading();

  try {
    const res = await fetch("/api/public/verify", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ employee_code: code })
    });
    const data = await res.json();

    hideLoading();

    if (!data.ok) {
      setMsg(data.error || "Verification failed", "error");
      return;
    }

    currentCode = data.employee.employee_code;

    // Update employee info display
    if (employeeName) employeeName.textContent = data.employee.full_name;
    if (employeeStatus) employeeStatus.textContent = `Employee ID: ${currentCode}`;
    show(employeeInfo);

    showActionButton(data.state);
    setMsg("✅ Verified successfully. Ready to clock in/out.", "success");

  } catch (e) {
    hideLoading();
    setMsg("❌ Server error. Please try again.", "error");
  }
});

// ---- CLOCK IN / OUT ----
safeAddClick(actionBtn, async () => {
  if (!currentCode || !nextAction) {
    setMsg("❌ Please verify your employee code first.", "error");
    return;
  }

  setMsg("", "info");
  hide(actionBtn);
  showLoading();

  try {
    const res = await fetch("/api/public/clock", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ employee_code: currentCode, action: nextAction })
    });
    const data = await res.json();

    hideLoading();

    if (!data.ok) {
      setMsg(data.error || "Clock action failed", "error");
      showActionButton(data.state);
      return;
    }

    // Update employee info with new state
    if (employeeStatus) employeeStatus.textContent = `Employee ID: ${currentCode} - ${data.state}`;

    showActionButton(data.state);
    setMsg(`✅ ${data.message}`, "success");

  } catch (e) {
    hideLoading();
    setMsg("❌ Server error. Please try again.", "error");
    showActionButton("unknown");
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

