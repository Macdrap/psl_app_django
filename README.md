# PSL Workflow System

Internal Django app for PSL to track work from first enquiry to invoice:

**Sales Tracker → Monthly Awards → Invoiced Jobs**, plus **Clients & Contacts** and a **Statistic Explorer**.

- **Sales Tracker** — enquiries with job number, client/contact, value, status (Pending / Awarded / Rejected / Not Quoted), feedback, notes and referral source. Marking a job *Awarded* asks for the projected invoice date and department split, and creates the Monthly Award and Invoiced Job automatically.
- **Monthly Awards** — awarded jobs by month, with warnings for awards with no invoice or whose invoices don't add up to the award value. Edits sync back to the sales enquiry.
- **Invoiced Jobs** — invoices by month (several per award allowed) split into Utility / CAD / Topo / Contractor, with PSL value (= Utility + CAD + Topo), monthly totals, invoiced vs pending, and follow-up tracking.
- **Clients** — one record per company with sector and status, multiple contacts each; autocomplete on all forms.
- **Statistic Explorer** — win/loss, feedback, sector, client-status and referral statistics for all time, a month, or a date range; printable export.

## Quick start (local, Windows)

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # then edit DB settings / SECRET_KEY
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

Requires a local PostgreSQL 15+. Open http://127.0.0.1:8000.

## Tests

```powershell
.venv\Scripts\python.exe manage.py test --noinput
```

## Documentation

- [CLAUDE.md](CLAUDE.md) — rules and orientation for anyone (human or AI) changing the code
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — apps, models, data flows, URLs
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — production on AWS EC2, deploying, backups, SSL
- [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) — known bugs and quirks
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — version history

## Stack

Django 5.2 · PostgreSQL 15 · Gunicorn · Nginx · Docker Compose · AWS EC2 · GitHub Actions (manual deploy).

Private — All Rights Reserved.
