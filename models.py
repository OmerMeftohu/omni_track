import sqlite3
from config import Config
from utils import now_iso, today_str, generate_unique_employee_code
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, email, role, employee_id=None, password_hash=None):
        self.id = id
        self.email = email
        self.role = role
        self.employee_id = employee_id
        self.password_hash = password_hash

    @staticmethod
    def get(user_id):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, email, role, employee_id, password_hash FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return User(row["id"], row["email"], row["role"], row["employee_id"], row["password_hash"])
        return None

    @staticmethod
    def get_by_email(email):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, email, role, employee_id, password_hash FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        conn.close()
        if row:
            return User(row["id"], row["email"], row["role"], row["employee_id"], row["password_hash"])
        return None

def get_db():
    conn = sqlite3.connect(Config.DB_PATH)
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

    # Productivity scores table (per employee, persisted for manager score progression)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS productivity_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_code TEXT NOT NULL,
            score REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Users table for authentication
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            employee_id INTEGER,
            created_at TEXT NOT NULL,
            last_login TEXT,
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        )
    """)

    # Audit logs table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    # Missed clock-outs notifications table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS missed_clockouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            work_date TEXT NOT NULL,
            clock_in_time TEXT NOT NULL,
            notified_at TEXT NOT NULL,
            UNIQUE(employee_id, work_date),
            FOREIGN KEY(employee_id) REFERENCES employees(id)
        )
    """)

    # Create default users if none exist
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        supervisor_hash = generate_password_hash('admin123')
        manager_hash = generate_password_hash('12345')
        cur.execute("""
            INSERT INTO users (email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?)
        """, ('supervisor@example.com', supervisor_hash, 'supervisor', now_iso()))
        cur.execute("""
            INSERT INTO users (email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?)
        """, ('omff4129@gmail.com', manager_hash, 'manager', now_iso()))

    conn.commit()
    conn.close()

def employee_current_state(employee_id: int):
    """Return the clock state for TODAY only — previous days never block a new day."""
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


def record_missed_clockout(employee_id: int, work_date: str, clock_in_time: str):
    """Insert a missed clock-out record (ignored if already recorded)."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT OR IGNORE INTO missed_clockouts (employee_id, work_date, clock_in_time, notified_at)
            VALUES (?, ?, ?, ?)
        """, (employee_id, work_date, clock_in_time, now_iso()))
        conn.commit()
    finally:
        conn.close()

def create_employee(full_name):
    code = generate_unique_employee_code()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO employees (employee_code, full_name, status, created_at)
        VALUES (?, ?, 'ACTIVE', ?)
    """, (code, full_name, now_iso()))
    conn.commit()
    conn.close()
    return code

def set_employee_status(code, status):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE employees SET status = ? WHERE employee_code = ?", (status, code))
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return changed > 0

def verify_employee(code):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, status FROM employees WHERE employee_code = ?", (code,))
    emp = cur.fetchone()
    conn.close()
    return emp

def clock_employee(code, action):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, status FROM employees WHERE employee_code = ?", (code,))
    emp = cur.fetchone()

    if emp is None or emp["status"] != "ACTIVE":
        conn.close()
        return False, "Invalid or inactive ID"

    state = employee_current_state(emp["id"])

    if state["next_action"] != action:
        conn.close()
        return False, "Action not allowed"

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
    return True, "Success"

    return True

def log_audit(user_id, action, details, ip_address):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO audit_logs (user_id, action, details, ip_address, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, action, details, ip_address, now_iso()))
    conn.commit()
    conn.close()

def create_user(email, password, role='employee', employee_id=None):
    password_hash = generate_password_hash(password)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users (email, password_hash, role, employee_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (email, password_hash, role, employee_id, now_iso()))
        conn.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return None
    conn.close()
    return user_id

def verify_password(email, password):
    user = User.get_by_email(email)
    if user and check_password_hash(user.password_hash, password):
        return user
    return None

def update_last_login(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET last_login = ? WHERE id = ?", (now_iso(), user_id))
    conn.commit()
    conn.close()

# Add more model functions as needed for other endpoints