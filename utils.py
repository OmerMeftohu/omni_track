from datetime import datetime, timedelta
import random

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

def iso_seconds(dt: datetime) -> str:
    # SQLite stores created_at as ISO string; keep formatting consistent for BETWEEN comparisons.
    return dt.replace(microsecond=0).isoformat(timespec="seconds")

def week_start_for_date(d):
    # Monday start.
    return d - timedelta(days=d.weekday())

def add_months_to_date(d, months: int):
    # Always return a date on the 1st (used for month bucket starts).
    base = d.replace(day=1)
    month_index = (base.month - 1) + months
    year = base.year + (month_index // 12)
    month = (month_index % 12) + 1
    return base.replace(year=year, month=month, day=1)

def to_iso_datetime_range(start_date, end_date):
    min_dt = datetime.combine(start_date, datetime.min.time()).replace(microsecond=0)
    max_dt = datetime.combine(end_date, datetime.max.time()).replace(microsecond=0)
    return iso_seconds(min_dt), iso_seconds(max_dt)

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

def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def today_str():
    return datetime.now().date().isoformat()

def generate_unique_employee_code():
    return str(random.randint(10000, 99999))