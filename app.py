from flask import Flask, request, jsonify, render_template
import sqlite3
from datetime import datetime
import random

from datetime import datetime, timedelta
from flask import Response
import csv
import io

app = Flask(__name__)
DB_PATH = "omni.db"

def week_range(d=None):
    d = d or datetime.now().date()
    # Monday start
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()

def parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None

def hours_between(start_iso, end_iso):
    s = parse_iso(start_iso)
    e = parse_iso(end_iso)
    if not s or not e:
        return 0.0
    return max((e - s).total_seconds() / 3600.0, 0.0)

def is_late(clock_in_iso, late_h=9, late_m=15):
    dt = parse_iso(clock_in_iso)
    if not dt:
        return False
    late_cutoff = dt.replace(hour=late_h, minute=late_m, second=0, microsecond=0)
    return dt > late_cutoff

def productivity_score(cin, cout, late_flag):
    # Simple MVP scoring
    score = 0
    if cin: score += 40
    if cout: score += 40
    if cin and cout: score += 20
    if late_flag: score -= 10
    return max(score, 0)


# ---------- DB Helpers ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Employees table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL
        )
    """)

    # Time entries table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            work_date TEXT NOT NULL,
            clock_in_time TEXT,
            clock_out_time TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            source TEXT NOT NULL DEFAULT 'PUBLIC',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(employee_id, work_date),
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        )
    """)

    # Daily reports table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supervisor_name TEXT NOT NULL,
            report_date TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(supervisor_name, report_date)
        )
    """)
    # Todos table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            title TEXT NOT NULL,
            details TEXT,
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'OPEN',
            created_at TEXT NOT NULL
        )
    """)


    conn.commit()
    conn.close()


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def today_str():
    return datetime.now().date().isoformat()


def generate_unique_employee_code():
    conn = get_db()
    cur = conn.cursor()

    while True:
        code = str(random.randint(10000, 99999))
        cur.execute("SELECT 1 FROM employees WHERE employee_code = ?", (code,))
        if cur.fetchone() is None:
            conn.close()
            return code


def employee_current_state(employee_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, clock_in_time, clock_out_time
        FROM time_entries
        WHERE employee_id = ? AND work_date = ?
    """, (employee_id, today_str()))
    row = cur.fetchone()
    conn.close()

    if row is None or row["clock_in_time"] is None:
        return {"next_action": "CLOCK_IN"}

    if row["clock_out_time"] is None:
        return {"next_action": "CLOCK_OUT"}

    return {"next_action": "DONE_FOR_TODAY"}


# ---------- Page Routes ----------
@app.get("/")
def home():
    return render_template("index.html")


@app.get("/supervisor")
def supervisor_login():
    return render_template("supervisor_login.html")


@app.get("/supervisor/dashboard")
def supervisor_dashboard():
    return render_template("supervisor_dashboard.html")


@app.get("/manager/dashboard")
def manager_dashboard():
    return render_template("manager_dashboard.html")


# ---------- Admin (Temp) ----------
@app.post("/api/admin/create-employee")
def create_employee():
    data = request.get_json(silent=True) or {}
    full_name = (data.get("full_name") or "").strip()

    if not full_name:
        return jsonify({"ok": False, "error": "full_name is required"}), 400

    code = generate_unique_employee_code()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO employees (employee_code, full_name, status, created_at)
        VALUES (?, ?, 'ACTIVE', ?)
    """, (code, full_name, now_iso()))
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "employee_code": code, "full_name": full_name})


@app.post("/api/admin/set-employee-status")
def set_employee_status():
    data = request.get_json(silent=True) or {}
    code = (data.get("employee_code") or "").strip()
    status = (data.get("status") or "").strip().upper()

    if len(code) != 5 or not code.isdigit():
        return jsonify({"ok": False, "error": "employee_code must be 5 digits"}), 400

    if status not in ("ACTIVE", "INACTIVE"):
        return jsonify({"ok": False, "error": "status must be ACTIVE or INACTIVE"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE employees SET status = ? WHERE employee_code = ?", (status, code))
    conn.commit()
    changed = cur.rowcount
    conn.close()

    if changed == 0:
        return jsonify({"ok": False, "error": "employee not found"}), 404

    return jsonify({"ok": True, "employee_code": code, "status": status})


# ---------- Public ----------
@app.post("/api/public/verify")
def public_verify():
    data = request.get_json(silent=True) or {}
    code = (data.get("employee_code") or "").strip()

    if len(code) != 5 or not code.isdigit():
        return jsonify({"ok": False, "error": "Enter a valid 5-digit ID"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, status FROM employees WHERE employee_code = ?", (code,))
    emp = cur.fetchone()
    conn.close()

    if emp is None:
        return jsonify({"ok": False, "error": "ID not found"}), 404

    if emp["status"] != "ACTIVE":
        return jsonify({"ok": False, "error": "ID is inactive"}), 403

    state = employee_current_state(emp["id"])

    return jsonify({
        "ok": True,
        "employee": {"employee_code": code, "full_name": emp["full_name"]},
        "state": state
    })


@app.post("/api/public/clock")
def public_clock():
    data = request.get_json(silent=True) or {}
    code = (data.get("employee_code") or "").strip()
    action = (data.get("action") or "").strip().upper()

    if action not in ("CLOCK_IN", "CLOCK_OUT"):
        return jsonify({"ok": False, "error": "Invalid action"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, status FROM employees WHERE employee_code = ?", (code,))
    emp = cur.fetchone()

    if emp is None or emp["status"] != "ACTIVE":
        conn.close()
        return jsonify({"ok": False, "error": "Invalid or inactive ID"}), 403

    state = employee_current_state(emp["id"])

    if state["next_action"] != action:
        conn.close()
        return jsonify({"ok": False, "error": "Action not allowed"}), 409

    ts = now_iso()
    work_date = today_str()

    cur.execute("""
        INSERT OR IGNORE INTO time_entries (employee_id, work_date, created_at, updated_at)
        VALUES (?, ?, ?, ?)
    """, (emp["id"], work_date, ts, ts))

    if action == "CLOCK_IN":
        cur.execute("""
            UPDATE time_entries
            SET clock_in_time = ?, updated_at = ?
            WHERE employee_id = ? AND work_date = ?
        """, (ts, ts, emp["id"], work_date))

    if action == "CLOCK_OUT":
        cur.execute("""
            UPDATE time_entries
            SET clock_out_time = ?, updated_at = ?
            WHERE employee_id = ? AND work_date = ?
        """, (ts, ts, emp["id"], work_date))

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "message": f"{action} successful"})


# ---------- Supervisor ----------
@app.get("/api/supervisor/today-logs")
def supervisor_today_logs():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.employee_code, e.full_name, t.clock_in_time, t.clock_out_time
        FROM employees e
        LEFT JOIN time_entries t
        ON t.employee_id = e.id AND t.work_date = ?
        ORDER BY e.full_name ASC
    """, (today_str(),))
    rows = cur.fetchall()
    conn.close()

    logs = []
    for r in rows:
        logs.append(dict(r))

    return jsonify({"ok": True, "logs": logs})


@app.post("/api/supervisor/daily-report")
def supervisor_daily_report():
    data = request.get_json(silent=True) or {}
    supervisor_name = data.get("supervisor_name")
    summary = data.get("summary")

    if not supervisor_name or not summary:
        return jsonify({"ok": False, "error": "Missing fields"}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO daily_reports (supervisor_name, report_date, summary, created_at)
            VALUES (?, ?, ?, ?)
        """, (supervisor_name, today_str(), summary, now_iso()))
        conn.commit()
    except sqlite3.IntegrityError:
        cur.execute("""
            UPDATE daily_reports
            SET summary = ?, created_at = ?
            WHERE supervisor_name = ? AND report_date = ?
        """, (summary, now_iso(), supervisor_name, today_str()))
        conn.commit()

    conn.close()
    return jsonify({"ok": True})


@app.get("/api/manager/daily-reports")
def manager_daily_reports():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT supervisor_name, report_date, summary, created_at
        FROM daily_reports
        ORDER BY report_date DESC
    """)
    rows = cur.fetchall()
    conn.close()

    return jsonify({
        "ok": True,
        "reports": [dict(r) for r in rows]
    })
# ---------- Manager api---------- 
@app.post("/api/manager/todos")
def manager_create_todo():
    data = request.get_json(silent=True) or {}
    scope = (data.get("scope") or "").strip().upper()
    title = (data.get("title") or "").strip()
    details = (data.get("details") or "").strip() or None
    due_date = (data.get("due_date") or "").strip() or None

    if scope not in ("DAILY", "WEEKLY", "MONTHLY"):
        return jsonify({"ok": False, "error": "scope must be DAILY/WEEKLY/MONTHLY"}), 400
    if not title:
        return jsonify({"ok": False, "error": "title required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO todos (scope, title, details, due_date, status, created_at)
        VALUES (?, ?, ?, ?, 'OPEN', ?)
    """, (scope, title, details, due_date, now_iso()))
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "message": "Todo created"})

# ---------- Supervisor api----------
@app.get("/api/supervisor/todos")
def supervisor_get_todos():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, scope, title, details, due_date, status, created_at
        FROM todos
        WHERE status = 'OPEN'
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()

    return jsonify({
        "ok": True,
        "todos": [dict(r) for r in rows]
    })

#---------- KPI ----------
from datetime import datetime  # you already have this

def hours_between(start_iso, end_iso):
    if not start_iso or not end_iso:
        return 0.0
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
        diff = end - start
        return max(diff.total_seconds() / 3600.0, 0.0)
    except Exception:
        return 0.0


@app.get("/api/manager/kpis")
def manager_kpis():
    today = today_str()

    conn = get_db()
    cur = conn.cursor()

    # Active employee count
    cur.execute("SELECT COUNT(*) AS c FROM employees WHERE status='ACTIVE'")
    active_employees = cur.fetchone()["c"]

    # Today’s entries (active employees only)
    cur.execute("""
        SELECT e.employee_code, e.full_name, t.clock_in_time, t.clock_out_time
        FROM employees e
        LEFT JOIN time_entries t
            ON t.employee_id = e.id AND t.work_date = ?
        WHERE e.status='ACTIVE'
    """, (today,))
    rows = cur.fetchall()
    conn.close()

    total_hours = 0.0
    clocked_in_count = 0
    clocked_out_count = 0
    missing_clock_in = 0
    missing_clock_out = 0

    for r in rows:
        cin = r["clock_in_time"]
        cout = r["clock_out_time"]

        if cin:
            clocked_in_count += 1
        else:
            missing_clock_in += 1

        if cin and cout:
            clocked_out_count += 1
            total_hours += hours_between(cin, cout)
        elif cin and not cout:
            missing_clock_out += 1

    attendance_rate = (clocked_in_count / active_employees * 100.0) if active_employees else 0.0
    avg_hours_per_completed = (total_hours / clocked_out_count) if clocked_out_count else 0.0

    return jsonify({
        "ok": True,
        "date": today,
        "active_employees": active_employees,
        "clocked_in_today": clocked_in_count,
        "clocked_out_today": clocked_out_count,
        "missing_clock_in": missing_clock_in,
        "missing_clock_out": missing_clock_out,
        "total_hours_completed": round(total_hours, 2),
        "avg_hours_per_completed": round(avg_hours_per_completed, 2),
        "attendance_rate": round(attendance_rate, 1)
    })

#---------- Supervisor employee list with today's activity ----------
@app.get("/api/supervisor/employees")
def supervisor_employees():
    conn = get_db()
    cur = conn.cursor()

    # list employees + today's activity (clock in/out) if exists
    cur.execute("""
        SELECT
            e.employee_code,
            e.full_name,
            e.status,
            e.created_at,
            t.clock_in_time,
            t.clock_out_time
        FROM employees e
        LEFT JOIN time_entries t
            ON t.employee_id = e.id AND t.work_date = ?
        ORDER BY e.full_name ASC
    """, (today_str(),))

    rows = cur.fetchall()
    conn.close()

    return jsonify({
        "ok": True,
        "employees": [dict(r) for r in rows]
    })
#---------- Manager view employee ranking ----------
@app.get("/api/manager/employee-ranking-today")
def manager_employee_ranking_today():
    today = today_str()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.employee_code, e.full_name, e.status,
               t.clock_in_time, t.clock_out_time
        FROM employees e
        LEFT JOIN time_entries t
          ON t.employee_id = e.id AND t.work_date = ?
        ORDER BY e.full_name ASC
    """, (today,))
    rows = cur.fetchall()
    conn.close()

    items = []
    for r in rows:
        cin = r["clock_in_time"]
        cout = r["clock_out_time"]
        late_flag = is_late(cin)
        hours = round(hours_between(cin, cout), 2) if (cin and cout) else 0.0
        score = productivity_score(cin, cout, late_flag)
        items.append({
            "employee_code": r["employee_code"],
            "full_name": r["full_name"],
            "status": r["status"],
            "clock_in_time": cin,
            "clock_out_time": cout,
            "hours_today": hours,
            "late": late_flag,
            "score": score
        })

    items.sort(key=lambda x: (x["score"], x["hours_today"]), reverse=True)
    return jsonify({"ok": True, "date": today, "employees": items})

#---------- Manager weekly summary ----------
@app.get("/api/manager/weekly-summary")
def manager_weekly_summary():
    start, end = week_range()

    conn = get_db()
    cur = conn.cursor()

    # Active count
    cur.execute("SELECT COUNT(*) AS c FROM employees WHERE status='ACTIVE'")
    active = cur.fetchone()["c"]

    # Per-employee weekly rollup (completed sessions only)
    cur.execute("""
        SELECT e.employee_code, e.full_name, e.status,
               COUNT(t.id) AS entries,
               SUM(CASE WHEN t.clock_in_time IS NOT NULL THEN 1 ELSE 0 END) AS days_clocked_in,
               SUM(CASE WHEN t.clock_in_time IS NOT NULL AND t.clock_out_time IS NOT NULL THEN 1 ELSE 0 END) AS days_completed,
               SUM(CASE WHEN t.clock_in_time IS NOT NULL AND t.clock_out_time IS NULL THEN 1 ELSE 0 END) AS missing_clock_out
        FROM employees e
        LEFT JOIN time_entries t
          ON t.employee_id = e.id
         AND t.work_date BETWEEN ? AND ?
        GROUP BY e.id
        ORDER BY e.full_name ASC
    """, (start, end))
    base_rows = cur.fetchall()

    # Pull all time rows in week to compute hours + late
    cur.execute("""
        SELECT e.employee_code, t.work_date, t.clock_in_time, t.clock_out_time
        FROM employees e
        JOIN time_entries t ON t.employee_id = e.id
        WHERE t.work_date BETWEEN ? AND ?
    """, (start, end))
    time_rows = cur.fetchall()
    conn.close()

    # compute hours + late per employee_code
    hours_map = {}
    late_map = {}
    for tr in time_rows:
        code = tr["employee_code"]
        cin = tr["clock_in_time"]
        cout = tr["clock_out_time"]
        if cin and cout:
            hours_map[code] = hours_map.get(code, 0.0) + hours_between(cin, cout)
        if cin and is_late(cin):
            late_map[code] = late_map.get(code, 0) + 1

    employees = []
    total_hours = 0.0
    total_lates = 0
    total_missing_out = 0

    for r in base_rows:
        code = r["employee_code"]
        weekly_hours = round(hours_map.get(code, 0.0), 2)
        lates = late_map.get(code, 0)
        total_hours += weekly_hours
        total_lates += lates
        total_missing_out += int(r["missing_clock_out"] or 0)

        # Simple underperformance flag:
        # - less than 3 days clocked in OR weekly_hours < 20 OR too many lates
        under = (int(r["days_clocked_in"] or 0) < 3) or (weekly_hours < 20) or (lates >= 2)

        employees.append({
            "employee_code": code,
            "full_name": r["full_name"],
            "status": r["status"],
            "days_clocked_in": int(r["days_clocked_in"] or 0),
            "days_completed": int(r["days_completed"] or 0),
            "missing_clock_out": int(r["missing_clock_out"] or 0),
            "late_count": int(lates),
            "weekly_hours": weekly_hours,
            "underperforming": under
        })

    attendance_rate_week = round((sum(1 for e in employees if e["days_clocked_in"] > 0) / active * 100.0), 1) if active else 0.0

    return jsonify({
        "ok": True,
        "week_start": start,
        "week_end": end,
        "active_employees": active,
        "total_hours_completed": round(total_hours, 2),
        "attendance_rate_week": attendance_rate_week,
        "total_late_events": total_lates,
        "total_missing_clock_out": total_missing_out,
        "employees": employees
    })

@app.get("/api/manager/export/today-logs.csv")
def export_today_logs_csv():
    today = today_str()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.full_name, e.employee_code, e.status, t.clock_in_time, t.clock_out_time
        FROM employees e
        LEFT JOIN time_entries t
          ON t.employee_id = e.id AND t.work_date = ?
        ORDER BY e.full_name ASC
    """, (today,))
    rows = cur.fetchall()
    conn.close()

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["date", "full_name", "employee_code", "status", "clock_in_time", "clock_out_time"])
    for r in rows:
        w.writerow([today, r["full_name"], r["employee_code"], r["status"], r["clock_in_time"], r["clock_out_time"]])

    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=today_logs_{today}.csv"})

# For the weekly summary CSV export, we reuse the same logic as the JSON endpoint but format it as CSV.

@app.get("/api/manager/export/weekly-summary.csv")
def export_weekly_summary_csv():
    # reuse weekly summary endpoint logic quickly by calling internal helpers
    start, end = week_range()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.employee_code, e.full_name, e.status,
               SUM(CASE WHEN t.clock_in_time IS NOT NULL THEN 1 ELSE 0 END) AS days_clocked_in,
               SUM(CASE WHEN t.clock_in_time IS NOT NULL AND t.clock_out_time IS NOT NULL THEN 1 ELSE 0 END) AS days_completed,
               SUM(CASE WHEN t.clock_in_time IS NOT NULL AND t.clock_out_time IS NULL THEN 1 ELSE 0 END) AS missing_clock_out
        FROM employees e
        LEFT JOIN time_entries t
          ON t.employee_id = e.id
         AND t.work_date BETWEEN ? AND ?
        GROUP BY e.id
        ORDER BY e.full_name ASC
    """, (start, end))
    base_rows = cur.fetchall()

    cur.execute("""
        SELECT e.employee_code, t.clock_in_time, t.clock_out_time
        FROM employees e
        JOIN time_entries t ON t.employee_id = e.id
        WHERE t.work_date BETWEEN ? AND ?
    """, (start, end))
    time_rows = cur.fetchall()
    conn.close()

    hours_map = {}
    late_map = {}
    for tr in time_rows:
        code = tr["employee_code"]
        cin = tr["clock_in_time"]
        cout = tr["clock_out_time"]
        if cin and cout:
            hours_map[code] = hours_map.get(code, 0.0) + hours_between(cin, cout)
        if cin and is_late(cin):
            late_map[code] = late_map.get(code, 0) + 1

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["week_start", "week_end", "full_name", "employee_code", "status",
                "days_clocked_in", "days_completed", "missing_clock_out", "late_count", "weekly_hours"])

    for r in base_rows:
        code = r["employee_code"]
        w.writerow([
            start, end, r["full_name"], code, r["status"],
            int(r["days_clocked_in"] or 0),
            int(r["days_completed"] or 0),
            int(r["missing_clock_out"] or 0),
            int(late_map.get(code, 0)),
            round(hours_map.get(code, 0.0), 2)
        ])

    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=weekly_summary_{start}_to_{end}.csv"})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
