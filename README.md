**project structer**

OmniTrack — Workforce Time Tracking System
OmniTrack is a web-based employee time tracking application built with Python/Flask. It allows employees to clock in and out using a 5-digit employee code, while supervisors and managers monitor attendance, productivity, and daily operations through dedicated dashboards.

**Features**
Employee Clock Page

- Clock in / clock out with a 5-digit employee code
- Page resets fresh every day — previous day's state never carries over
- Missed clock-out detection (flagged automatically on next login)

Supervisor Dashboard

- View today's time logs for all employees
- Create and manage employees (activate / deactivate)
- Submit daily reports
- View todos assigned by the manager
- See missed clock-out alerts in real time
- Change account password

Manager Dashboard

- KPI dashboard with attendance and hours charts (Chart.js)
- View and create supervisors
- Create and assign todos (Daily / Weekly / Monthly scope) synced to supervisors
- Add and track employee productivity scores with time-series chart
- Export time logs as CSV with date range picker and preview table
- View all manager daily reports

**Automated Maintenance**

Every 90 days: exports all time entries and audit logs as CSV attachments, emails them to all manager accounts, then permanently deletes records older than 90 days

**Security**

- Passwords hashed with pbkdf2:sha256 (Werkzeug)
- Role-based access control — supervisor and manager roles enforced on every route
- CSRF protection via Flask-WTF on all forms
- Login brute-force lockout — 5 failed attempts triggers a 15-minute IP block
- Password strength enforced — minimum 8 characters, 1 uppercase, 1 number
- Auto-generated 256-bit secret key stored locally (never committed to git)
- Full audit log of all logins, failed attempts, and actions
- 1-hour session timeout

**Tech Stack**
- Backend: Python 3, Flask 3, Flask-Login, Flask-WTF, SQLite, APScheduler
- Frontend: Vanilla JS, Chart.js, plain CSS
- Auth: Session-based with CSRF tokens 


Setup

**Deployed** at Pythonanywhere.com

Default accounts (change immediately after first login):

- Role	Email	Password
- Manager	omff4129@gmail.com	12345
- Supervisor	supervisor@example.com	admin123

**Environment variables for production:**

Core Features

- Employee clock in/out with 5-digit codes, fresh reset every day
- Supervisor dashboard — employee management, daily reports, todo sync, missed clock-out alerts
- Manager dashboard — KPIs + charts, productivity scores, CSV export with date range, supervisor management

**Security**

- Role-based auth on every route (Flask-Login + CSRF)
- Brute-force lockout (5 attempts → 15 min block)
- Password strength enforcement (8 chars, uppercase, number)
- Auto-generated 256-bit secret key
  
**Automation**

90-day data cleanup with CSV archive emailed to manager before deletion
Tested & Deployed

43/43 pre-deployment tests passed
Running live on PythonAnywhere


