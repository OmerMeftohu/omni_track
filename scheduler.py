import csv
import io
import logging
import smtplib
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from models import get_db

log = logging.getLogger(__name__)


def _get_manager_emails():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE role = 'manager'")
    rows = cur.fetchall()
    conn.close()
    return [r["email"] for r in rows]


def _build_csv(rows, fieldnames):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in fieldnames})
    return buf.getvalue().encode("utf-8")


def _send_email(to_list, subject, body, attachments):
    """attachments: list of (filename, bytes_data)"""
    if not Config.MAIL_EMAIL or not Config.MAIL_PASSWORD:
        log.warning("Mail credentials not configured — skipping cleanup email.")
        return

    msg = MIMEMultipart()
    msg["From"] = Config.MAIL_EMAIL
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    for filename, data in attachments:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

    try:
        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
            if Config.MAIL_USE_TLS:
                server.starttls()
            server.login(Config.MAIL_EMAIL, Config.MAIL_PASSWORD)
            server.sendmail(Config.MAIL_EMAIL, to_list, msg.as_string())
        log.info("Cleanup archive email sent to: %s", to_list)
    except Exception as exc:
        log.error("Failed to send cleanup email: %s", exc)


def cleanup_and_email():
    cutoff_date = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
    cutoff_iso = cutoff_date + "T00:00:00"

    conn = get_db()
    cur = conn.cursor()

    # Time entries older than 90 days (by work_date)
    cur.execute("""
        SELECT te.id, e.employee_code, e.full_name, te.work_date,
               te.clock_in_time, te.clock_out_time, te.status, te.source, te.created_at
        FROM time_entries te
        JOIN employees e ON e.id = te.employee_id
        WHERE te.work_date < ?
    """, (cutoff_date,))
    time_rows = cur.fetchall()

    # Audit logs older than 90 days
    cur.execute("""
        SELECT al.id, u.email, al.action, al.details, al.ip_address, al.created_at
        FROM audit_logs al
        LEFT JOIN users u ON u.id = al.user_id
        WHERE al.created_at < ?
    """, (cutoff_iso,))
    audit_rows = cur.fetchall()

    conn.close()

    if not time_rows and not audit_rows:
        log.info("Cleanup job: nothing older than 90 days to archive.")
        return

    # Build CSV attachments
    attachments = []
    if time_rows:
        fields = [
            "id", "employee_code", "full_name", "work_date",
            "clock_in_time", "clock_out_time", "status", "source", "created_at"
        ]
        attachments.append((
            f"time_entries_archive_{cutoff_date}.csv",
            _build_csv(time_rows, fields)
        ))

    if audit_rows:
        fields = ["id", "email", "action", "details", "ip_address", "created_at"]
        attachments.append((
            f"audit_logs_archive_{cutoff_date}.csv",
            _build_csv(audit_rows, fields)
        ))

    # Email all managers
    managers = _get_manager_emails()
    if managers:
        run_date = datetime.utcnow().strftime("%Y-%m-%d")
        _send_email(
            to_list=managers,
            subject=f"OmniTrack — 90-day archive before cleanup ({run_date})",
            body=(
                f"Hi,\n\n"
                f"Attached are all records older than 90 days (before {cutoff_date}) "
                f"that are about to be permanently deleted from OmniTrack.\n\n"
                f"  - Time entries: {len(time_rows)} rows\n"
                f"  - Audit logs:   {len(audit_rows)} rows\n\n"
                f"These records have now been removed from the live database.\n\n"
                f"-- OmniTrack automated cleanup"
            ),
            attachments=attachments,
        )

    # Delete old records
    conn = get_db()
    cur = conn.cursor()
    if time_rows:
        cur.execute("DELETE FROM time_entries WHERE work_date < ?", (cutoff_date,))
    if audit_rows:
        cur.execute("DELETE FROM audit_logs WHERE created_at < ?", (cutoff_iso,))
    conn.commit()
    conn.close()

    log.info(
        "Cleanup job complete: deleted %d time entries and %d audit logs older than %s.",
        len(time_rows), len(audit_rows), cutoff_date
    )


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        cleanup_and_email,
        trigger="interval",
        days=90,
        id="cleanup_and_email",
        replace_existing=True,
    )
    scheduler.start()
    log.info("Cleanup scheduler started — runs every 90 days.")
    return scheduler
