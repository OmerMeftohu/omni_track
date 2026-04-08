from flask import Flask, request, jsonify, render_template, Response, redirect, url_for, flash, session
from models import *
from utils import *
from config import Config
import csv
import io
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from werkzeug.security import generate_password_hash
from functools import wraps

app = Flask(__name__)

# ---------- Login rate limiting ----------
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_LOCKOUT_MINUTES = 15
_login_attempts = defaultdict(list)   # ip -> [datetime, ...]

def _check_rate_limit(ip):
    """Return (allowed, seconds_remaining). Clears expired entries."""
    cutoff = datetime.utcnow() - timedelta(minutes=_LOGIN_LOCKOUT_MINUTES)
    _login_attempts[ip] = [t for t in _login_attempts[ip] if t > cutoff]
    if len(_login_attempts[ip]) >= _LOGIN_MAX_ATTEMPTS:
        oldest = _login_attempts[ip][0]
        unlock_at = oldest + timedelta(minutes=_LOGIN_LOCKOUT_MINUTES)
        remaining = int((unlock_at - datetime.utcnow()).total_seconds())
        return False, max(remaining, 1)
    return True, 0

def _record_failed_attempt(ip):
    _login_attempts[ip].append(datetime.utcnow())

def _clear_attempts(ip):
    _login_attempts.pop(ip, None)


def _validate_password_strength(password):
    """Return an error string, or None if the password is strong enough."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    return None

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    role = SelectField('Role', choices=[('supervisor', 'Supervisor'), ('manager', 'Manager')])
    submit = SubmitField('Login')

def role_required(roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__  # Preserve original name
        return decorated_function
    return decorator
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'home'

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

# ---------- Auth Routes ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        ip = request.remote_addr
        allowed, remaining = _check_rate_limit(ip)
        if not allowed:
            flash(f'Too many failed attempts. Try again in {remaining} seconds.', 'danger')
            return render_template('login.html', form=form)
        user = verify_password(form.email.data, form.password.data)
        if user and user.role == form.role.data:
            _clear_attempts(ip)
            login_user(user)
            update_last_login(user.id)
            log_audit(user.id, 'login', 'User logged in', request.remote_addr)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            _record_failed_attempt(ip)
            log_audit(None, 'login_failed', f'Failed login for {form.email.data}', ip)
            flash('Invalid email, password, or role', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    log_audit(current_user.id, 'logout', 'User logged out', request.remote_addr)
    logout_user()
    return redirect(url_for('home'))

# ---------- Page Routes ----------
@app.route("/", methods=['GET', 'POST'])
def home():
    form = LoginForm()
    if form.validate_on_submit():
        ip = request.remote_addr
        allowed, remaining = _check_rate_limit(ip)
        if not allowed:
            flash(f'Too many failed attempts. Try again in {remaining} seconds.', 'danger')
            return render_template('index.html', form=form)
        user = verify_password(form.email.data, form.password.data)
        if user and user.role == form.role.data:
            _clear_attempts(ip)
            login_user(user)
            update_last_login(user.id)
            log_audit(user.id, 'login', 'User logged in', request.remote_addr)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            _record_failed_attempt(ip)
            log_audit(None, 'login_failed', f'Failed login for {form.email.data}', ip)
            flash('Invalid email, password, or role', 'danger')
    return render_template("index.html", form=form)

@app.get("/supervisor/dashboard")
@role_required(['supervisor', 'manager'])
def supervisor_dashboard():
    return render_template("supervisor_dashboard.html")

@app.get("/manager/dashboard")
@role_required(['manager'])
def manager_dashboard():
    return render_template("manager_dashboard.html")

# ---------- Admin (Temp) ----------
@app.post("/api/admin/create-employee")
@role_required(['supervisor', 'manager'])
def create_employee_route():
    data = request.get_json(silent=True) or {}
    full_name = (data.get("full_name") or "").strip()

    if not full_name:
        return jsonify({"ok": False, "error": "full_name is required"}), 400

    code = create_employee(full_name)
    # log_audit(current_user.id, 'create_employee', f'Created employee {code}', request.remote_addr)

    return jsonify({"ok": True, "employee_code": code, "full_name": full_name})

@app.post("/api/admin/set-employee-status")
@role_required(['supervisor', 'manager'])
def set_employee_status_route():
    data = request.get_json(silent=True) or {}
    code = (data.get("employee_code") or "").strip()
    status = (data.get("status") or "").strip().upper()

    if len(code) != 5 or not code.isdigit():
        return jsonify({"ok": False, "error": "employee_code must be 5 digits"}), 400

    if status not in ("ACTIVE", "INACTIVE"):
        return jsonify({"ok": False, "error": "status must be ACTIVE or INACTIVE"}), 400

    if set_employee_status(code, status):
        # log_audit(current_user.id, 'set_employee_status', f'Set employee {code} to {status}', request.remote_addr)
        return jsonify({"ok": True, "employee_code": code, "status": status})
    else:
        return jsonify({"ok": False, "error": "employee not found"}), 404

# ---------- Public ----------
@app.post("/api/public/verify")
def public_verify():
    data = request.get_json(silent=True) or {}
    code = (data.get("employee_code") or "").strip()

    if len(code) != 5 or not code.isdigit():
        return jsonify({"ok": False, "error": "Enter a valid 5-digit ID"}), 400

    emp = verify_employee(code)

    if emp is None:
        return jsonify({"ok": False, "error": "ID not found"}), 404

    if emp["status"] != "ACTIVE":
        return jsonify({"ok": False, "error": "ID is inactive"}), 403

    # Check for missed clock-out on a PREVIOUS day
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT work_date, clock_in_time
        FROM time_entries
        WHERE employee_id = ? AND work_date < ? AND clock_in_time IS NOT NULL AND clock_out_time IS NULL
        ORDER BY work_date DESC LIMIT 1
    """, (emp["id"], today_str()))
    missed = cur.fetchone()
    conn.close()

    if missed:
        record_missed_clockout(emp["id"], missed["work_date"], missed["clock_in_time"])

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

    success, message = clock_employee(code, action)

    if not success:
        return jsonify({"ok": False, "error": message}), 403

    # Get updated state after clocking
    emp = verify_employee(code)
    if emp:
        state = employee_current_state(emp["id"])
        return jsonify({"ok": True, "message": f"{action} successful", "state": state})
    else:
        return jsonify({"ok": True, "message": f"{action} successful"})

# Add more routes here for supervisor, manager, etc.

# ---------- Supervisor ----------
@app.get("/api/supervisor/missed-clockouts")
@role_required(['supervisor', 'manager'])
def supervisor_missed_clockouts():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT m.id, e.employee_code, e.full_name, m.work_date, m.clock_in_time, m.notified_at
        FROM missed_clockouts m
        JOIN employees e ON e.id = m.employee_id
        ORDER BY m.work_date DESC, e.full_name ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify({"ok": True, "missed": [dict(r) for r in rows]})


@app.get("/api/supervisor/today-logs")
@role_required(['supervisor', 'manager'])
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
@role_required(['supervisor', 'manager'])
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

    log_audit(current_user.id, 'daily_report', f'Submitted report for {today_str()}', request.remote_addr)
    conn.close()
    return jsonify({"ok": True})

@app.get("/api/manager/export/today-logs.csv")
@role_required(['manager'])
def export_today_logs_csv():
    page      = max(1, int(request.args.get('page', 1)))
    limit     = max(1, min(10000, int(request.args.get('limit', 100))))
    from_date = request.args.get('from_date', today_str())
    to_date   = request.args.get('to_date',   today_str())
    offset    = (page - 1) * limit

    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT t.work_date, e.full_name, e.employee_code, e.status AS emp_status,
               t.clock_in_time, t.clock_out_time, t.status AS entry_status
        FROM time_entries t
        JOIN employees e ON e.id = t.employee_id
        WHERE t.work_date BETWEEN ? AND ?
        ORDER BY t.work_date DESC, e.full_name ASC
        LIMIT ? OFFSET ?
    """, (from_date, to_date, limit, offset))
    rows = cur.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["work_date", "full_name", "employee_code", "employee_status",
                     "clock_in_time", "clock_out_time", "entry_status"])
    for r in rows:
        writer.writerow([r["work_date"], r["full_name"], r["employee_code"], r["emp_status"],
                         r["clock_in_time"], r["clock_out_time"], r["entry_status"]])

    log_audit(current_user.id, 'export_logs_csv',
              f'Exported {from_date} to {to_date} page {page} limit {limit}', request.remote_addr)
    fname = f"logs_{from_date}_to_{to_date}_p{page}.csv"
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.get("/api/manager/export/preview")
@role_required(['manager'])
def manager_export_preview():
    from_date = request.args.get('from_date', today_str())
    to_date   = request.args.get('to_date',   today_str())
    limit     = max(1, min(50, int(request.args.get('limit', 20))))

    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM time_entries WHERE work_date BETWEEN ? AND ?",
                (from_date, to_date))
    total = cur.fetchone()["cnt"]
    cur.execute("""
        SELECT t.work_date, e.full_name, e.employee_code,
               t.clock_in_time, t.clock_out_time, t.status AS entry_status
        FROM time_entries t
        JOIN employees e ON e.id = t.employee_id
        WHERE t.work_date BETWEEN ? AND ?
        ORDER BY t.work_date DESC, e.full_name ASC
        LIMIT ?
    """, (from_date, to_date, limit))
    rows = cur.fetchall()
    conn.close()
    return jsonify({"ok": True, "total": total, "rows": [dict(r) for r in rows]})

# ---------- Supervisor Account Management ----------
@app.post("/api/supervisor/change-password")
@role_required(['supervisor'])
def supervisor_change_password():
    data = request.get_json(silent=True) or {}
    current_password = (data.get("current_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()

    if not current_password:
        return jsonify({"ok": False, "error": "Current password is required"}), 400

    if not new_password:
        return jsonify({"ok": False, "error": "New password is required"}), 400

    strength_error = _validate_password_strength(new_password)
    if strength_error:
        return jsonify({"ok": False, "error": strength_error}), 400

    # Verify current password
    user = verify_password(current_user.email, current_password)
    if not user or user.id != current_user.id:
        return jsonify({"ok": False, "error": "Current password is incorrect"}), 400

    conn = get_db()
    cur = conn.cursor()

    password_hash = generate_password_hash(new_password)
    cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, current_user.id))
    conn.commit()
    conn.close()

    log_audit(current_user.id, 'change_password', 'Changed password', request.remote_addr)
    return jsonify({"ok": True})

# ---------- Manager Account Management ----------
@app.post("/api/manager/change-password")
@role_required(['manager'])
def change_password():
    data = request.get_json(silent=True) or {}
    current_password = (data.get("current_password") or "").strip()
    new_email = (data.get("new_email") or "").strip()
    new_password = (data.get("new_password") or "").strip()

    if not current_password:
        return jsonify({"ok": False, "error": "Current password is required"}), 400

    if not new_email and not new_password:
        return jsonify({"ok": False, "error": "At least one of new email or new password must be provided"}), 400

    # Verify current password
    user = verify_password(current_user.email, current_password)
    if not user or user.id != current_user.id:
        return jsonify({"ok": False, "error": "Current password is incorrect"}), 400

    conn = get_db()
    cur = conn.cursor()

    changes = []

    # Update email if provided
    if new_email:
        # Check if email is already taken by another user
        cur.execute("SELECT id FROM users WHERE email = ? AND id != ?", (new_email, current_user.id))
        if cur.fetchone():
            conn.close()
            return jsonify({"ok": False, "error": "Email is already in use"}), 400
        
        cur.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, current_user.id))
        changes.append(f"email to {new_email}")

    # Update password if provided
    if new_password:
        strength_error = _validate_password_strength(new_password)
        if strength_error:
            conn.close()
            return jsonify({"ok": False, "error": strength_error}), 400
        
        password_hash = generate_password_hash(new_password)
        cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, current_user.id))
        changes.append("password")

    conn.commit()
    conn.close()

    change_desc = "Changed " + " and ".join(changes)
    log_audit(current_user.id, 'change_account', change_desc, request.remote_addr)
    return jsonify({"ok": True})

@app.post("/api/manager/create-supervisor")
@role_required(['manager'])
def create_supervisor():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password required"}), 400

    if len(password) < 6:
        return jsonify({"ok": False, "error": "Password must be at least 6 characters"}), 400

    user_id = create_user(email, password, 'supervisor')
    if not user_id:
        return jsonify({"ok": False, "error": "Email already exists"}), 400

    log_audit(current_user.id, 'create_supervisor', f'Created supervisor {email}', request.remote_addr)
    return jsonify({"ok": True, "email": email})

@app.get("/api/manager/supervisors")
@role_required(['manager'])
def list_supervisors():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, email, created_at FROM users WHERE role = 'supervisor' ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()

    supervisors = [dict(r) for r in rows]
    return jsonify({"ok": True, "supervisors": supervisors})

@app.post("/api/manager/delete-supervisor")
@role_required(['manager'])
def delete_supervisor():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"ok": False, "error": "User ID required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE id = ? AND role = 'supervisor'", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "error": "Supervisor not found"}), 404

    email = row["email"]
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    log_audit(current_user.id, 'delete_supervisor', f'Deleted supervisor {email}', request.remote_addr)
    return jsonify({"ok": True})


# ---------- Manager Dashboard Data ----------
@app.get("/api/manager/kpis")
@role_required(['manager'])
def manager_kpis():
    today = today_str()
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM employees WHERE status = 'ACTIVE'")
    active_employees = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COUNT(*)
        FROM time_entries t
        JOIN employees e ON e.id = t.employee_id
        WHERE t.work_date = ?
          AND t.clock_in_time IS NOT NULL
          AND e.status = 'ACTIVE'
    """, (today,))
    clocked_in_today = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT COUNT(*)
        FROM time_entries t
        JOIN employees e ON e.id = t.employee_id
        WHERE t.work_date = ?
          AND t.clock_out_time IS NOT NULL
          AND e.status = 'ACTIVE'
    """, (today,))
    clocked_out_today = cur.fetchone()[0] or 0

    cur.execute("""
        SELECT clock_in_time, clock_out_time
        FROM time_entries
        WHERE work_date = ?
          AND clock_in_time IS NOT NULL
          AND clock_out_time IS NOT NULL
    """, (today,))
    rows = cur.fetchall()
    conn.close()

    total_hours_completed = round(sum(hours_between(r["clock_in_time"], r["clock_out_time"]) for r in rows), 2)
    avg_hours_per_completed = round(total_hours_completed / len(rows), 2) if rows else 0.0

    missing_clock_in = max(active_employees - clocked_in_today, 0)
    missing_clock_out = max(clocked_in_today - clocked_out_today, 0)
    attendance_rate = round((clocked_in_today / active_employees) * 100, 1) if active_employees else 0.0

    return jsonify({
        "ok": True,
        "date": today,
        "active_employees": active_employees,
        "clocked_in_today": clocked_in_today,
        "clocked_out_today": clocked_out_today,
        "missing_clock_in": missing_clock_in,
        "missing_clock_out": missing_clock_out,
        "total_hours_completed": total_hours_completed,
        "avg_hours_per_completed": avg_hours_per_completed,
        "attendance_rate": attendance_rate,
    })


@app.get("/api/manager/daily-reports")
@role_required(['manager'])
def manager_daily_reports():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT supervisor_name, report_date, summary, created_at
        FROM daily_reports
        ORDER BY report_date DESC, created_at DESC
        LIMIT 200
    """)
    rows = cur.fetchall()
    conn.close()

    return jsonify({"ok": True, "reports": [dict(r) for r in rows]})


@app.post("/api/manager/todos")
@role_required(['manager'])
def manager_create_todo():
    data = request.get_json(silent=True) or {}
    scope = (data.get("scope") or "").strip().upper()
    title = (data.get("title") or "").strip()
    details = (data.get("details") or "").strip()
    due_date = (data.get("due_date") or "").strip() or None

    if scope not in ("DAILY", "WEEKLY", "MONTHLY"):
        return jsonify({"ok": False, "error": "scope must be DAILY, WEEKLY, or MONTHLY"}), 400

    if not title:
        return jsonify({"ok": False, "error": "title is required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO todos (scope, title, details, due_date, status, created_at)
        VALUES (?, ?, ?, ?, 'OPEN', ?)
    """, (scope, title, details, due_date, now_iso()))
    todo_id = cur.lastrowid
    conn.commit()
    conn.close()

    log_audit(current_user.id, 'create_todo', f'Created todo {todo_id}', request.remote_addr)
    return jsonify({"ok": True, "id": todo_id})


@app.get("/api/supervisor/employees")
@role_required(['supervisor', 'manager'])
def supervisor_employees():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT employee_code, full_name, status
        FROM employees
        ORDER BY full_name ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify({"ok": True, "employees": [dict(r) for r in rows]})


def _load_productivity_scores(employee_code):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, employee_code, score, created_at
        FROM productivity_scores
        WHERE employee_code = ?
        ORDER BY created_at ASC, id ASC
    """, (employee_code,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/manager/productivity-scores")
@role_required(['manager'])
def manager_add_productivity_score():
    data = request.get_json(silent=True) or {}
    employee_code = (data.get("employee_code") or "").strip()
    score = data.get("score")

    if len(employee_code) != 5 or not employee_code.isdigit():
        return jsonify({"ok": False, "error": "employee_code must be 5 digits"}), 400

    try:
        score_val = float(score)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "score must be numeric"}), 400

    if score_val < 0:
        return jsonify({"ok": False, "error": "score must be >= 0"}), 400

    if verify_employee(employee_code) is None:
        return jsonify({"ok": False, "error": "employee not found"}), 404

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO productivity_scores (employee_code, score, created_at)
        VALUES (?, ?, ?)
    """, (employee_code, round(score_val, 1), now_iso()))
    conn.commit()
    conn.close()

    log_audit(current_user.id, 'add_productivity_score', f'Employee {employee_code} score {round(score_val, 1)}', request.remote_addr)
    return jsonify({"ok": True, "scores": _load_productivity_scores(employee_code)})


@app.post("/api/manager/productivity-scores/delete-last")
@role_required(['manager'])
def manager_delete_last_productivity_score():
    data = request.get_json(silent=True) or {}
    employee_code = (data.get("employee_code") or "").strip()

    if len(employee_code) != 5 or not employee_code.isdigit():
        return jsonify({"ok": False, "error": "employee_code must be 5 digits"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id
        FROM productivity_scores
        WHERE employee_code = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
    """, (employee_code,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return jsonify({"ok": False, "error": "no scores to delete"}), 404

    cur.execute("DELETE FROM productivity_scores WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()

    log_audit(current_user.id, 'delete_last_productivity_score', f'Employee {employee_code}', request.remote_addr)
    return jsonify({"ok": True, "scores": _load_productivity_scores(employee_code)})


@app.get("/api/manager/productivity-score-timeseries")
@role_required(['manager'])
def manager_productivity_score_timeseries():
    employee_code = (request.args.get("employee_code") or "").strip()
    range_name = (request.args.get("range") or "daily").strip().lower()

    if len(employee_code) != 5 or not employee_code.isdigit():
        return jsonify({"ok": False, "error": "employee_code must be 5 digits"}), 400

    if range_name not in ("daily", "weekly", "monthly"):
        return jsonify({"ok": False, "error": "range must be daily, weekly, or monthly"}), 400

    scores = _load_productivity_scores(employee_code)
    grouped = defaultdict(list)

    for item in scores:
        dt = parse_iso(item["created_at"])
        if not dt:
            continue

        if range_name == "daily":
            key = dt.date().isoformat()
        elif range_name == "weekly":
            iso = dt.isocalendar()
            key = f"{iso.year}-W{iso.week:02d}"
        else:
            key = f"{dt.year:04d}-{dt.month:02d}"

        grouped[key].append(float(item["score"]))

    labels = []
    values = []

    for key in sorted(grouped.keys()):
        vals = grouped[key]
        avg = round(sum(vals) / len(vals), 2)

        if range_name == "daily":
            d = datetime.fromisoformat(key)
            label = d.strftime("%m/%d")
        elif range_name == "weekly":
            year_part, week_part = key.split("-W")
            label = f"W{int(week_part)}/{year_part[-2:]}"
        else:
            y, m = key.split("-")
            label = f"{m}/{y}"

        labels.append(label)
        values.append(avg)

    return jsonify({"ok": True, "labels": labels, "values": values})


@app.get("/api/supervisor/todos")
@role_required(['supervisor', 'manager'])
def supervisor_get_todos():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, scope, title, details, due_date, status, created_at
        FROM todos
        WHERE status = 'OPEN'
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify({"ok": True, "todos": [dict(r) for r in rows]})


@app.get("/api/manager/todos")
@role_required(['manager'])
def manager_get_todos():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, scope, title, details, due_date, status, created_at
        FROM todos
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify({"ok": True, "todos": [dict(r) for r in rows]})

if __name__ == "__main__":
    init_db()
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY
    app.run(debug=Config.DEBUG)