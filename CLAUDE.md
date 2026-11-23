# PSL App (Django) — guide for working on this codebase

Internal workflow app for PSL (a survey company): track **sales enquiries → awarded jobs → invoices**, manage **clients/contacts**, and view **statistics**. Used daily in production at `psl-app.net`. **Do not break existing behaviour** — read this file before changing anything.

More detail lives in `docs/`:
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — apps, models, data flows, URLs, UI conventions
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — production server, deploy, backups, SSL
- [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) — known bugs and quirks (don't rediscover them)
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — what changed in each version

## Stack

Django 5.2.7 · Python 3.12 locally (3.11 in Docker) · PostgreSQL 15 · Gunicorn + Nginx in Docker Compose on AWS EC2 (eu-west-2). Function-based views, server-rendered templates with **inline CSS/JS in each template** (no frontend build, no static CSS files). Config via `python-decouple` reading `.env`.

## Local commands (Windows, PowerShell, from the repo root)

```powershell
.venv\Scripts\python.exe manage.py runserver          # http://127.0.0.1:8000
.venv\Scripts\python.exe manage.py test --noinput     # full test suite (~6 s)
.venv\Scripts\python.exe manage.py makemigrations     # after ANY model change, incl. choices
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py check
```

Local DB is Postgres on `localhost:5432` (settings in `.env`, see `.env.example`). Tests create and drop a separate `test_<DB_NAME>` database, so they never touch real data.

## Rules for every change

1. **Run the tests before and after.** `manage.py test --noinput` must end `OK`. If you find a bug you aren't fixing now, pin it with a `@unittest.expectedFailure` test and list it in KNOWN_ISSUES.
2. **Add/extend tests** in the app's `tests.py` for any behaviour you add or change. Shared factories are in `psl_app_project/test_utils.py` (`LoggedInTestCase`, `make_client`, `make_enquiry`, `make_award`, `make_invoice`, `messages_of`).
3. **Migrations:** any model change (fields, defaults, **choices**) needs `makemigrations` committed alongside it. `dashboard/tests.py::MigrationTests` fails if one is missing. Never edit or delete an already-applied migration — production has run them all. Data-changing migrations must be safe on both a fresh DB and production (see `clients/0005` for the pattern).
4. **Keep the sync logic intact** (details in ARCHITECTURE.md):
   - Sales enquiry status → `Awarded` creates a `MonthlyAward` **and** an `InvoicedJob` (from the award modal's `invoice_*` POST fields).
   - Status away from `Awarded` deletes the linked award(s) (invoices cascade).
   - Editing an awarded enquiry updates its award(s) and the first invoice; editing an award updates its linked sale.
   - Deleting an award reverts the sale to `Pending`.
5. **Clients are matched by exact (trimmed) company name**; contacts by name within a client. Use `get_or_create_client()` — it is **duplicated** in `sales_tracker/views.py` and `monthly_awards/views.py`; change both or consolidate.
6. **Preserve list state on redirects.** Add/edit/delete views carry `page`, `sort_by`, `search`, `per_page`, `scroll` (and `year`/`month` on Monthly Awards / Invoiced Jobs) through the query string and back. Keep this when touching those views/templates.
7. **Use `{% url 'name' %}` / `reverse()`**, never hard-coded paths. The project URL prefixes have no trailing slash (e.g. real path is `/sales-trackeradd/`); don't "fix" that without redirects, users have bookmarks.
8. **Adding a sector** (`clients.models.SECTOR_CHOICES`): also add a colour to `_palette` in `statistic_explorer/views.py` and create a migration. Tests check both.
9. All views must stay `@login_required` / `LoginRequiredMixin` (tested).
10. Don't commit `.env`, database dumps (`*.sql`, ignored) or anything under `logs/`.
11. **Sales Tracker rows live in `sales_tracker/templates/partials/table_body.html`** — shared by the page and the live-refresh endpoint. Add/change columns there (and the `<thead>` in `sales_tracker.html`).
12. **Changing `docker/Dockerfile` or system packages:** `scripts/deploy.sh` stops the live site *before* building, so a broken build means downtime. Build the image locally first (`docker build -f docker/Dockerfile .`).

## Git & deploy

- Remote: `github.com/Macdrap/psl_app_django`, branch `main`. Commit style: `feat: …` / `fix: …`; bigger releases are titled `Version X.Y.Z`.
- **Pushing to `main` does NOT deploy** (auto-deploy was disabled on 2026-11-19). Deploys are done by hand on the server or via the manual "Deploy to AWS EC2" GitHub Action — see DEPLOYMENT.md. Never deploy without the user asking.
- Always `git fetch` first: other sessions/PRs may have pushed to `main` (that happened before — local was 5 commits behind).
- Work on a branch for anything non-trivial; ask before pushing.

## Where things are

| Area | Code | Main template(s) |
|---|---|---|
| Dashboard (home) | `dashboard/views.py` | `dashboard/templates/dashboard.html` |
| Sales Tracker | `sales_tracker/` | `sales_tracker.html`, `partials/table_body.html` (rows), `sales_enquiry_form.html` (incl. award modal) |
| Monthly Awards | `monthly_awards/` | `monthly_awards_list.html`, `monthly_award_form.html` |
| Invoiced Jobs | `invoiced_jobs/` | `invoiced_jobs_list.html`, `invoiced_job_form.html` |
| Clients & Contacts | `clients/` (+ `management/commands/`) | `clients/templates/clients/*.html` |
| Statistic Explorer | `statistic_explorer/views.py` (one big `get_context_data`) | `statistic_explorer.html`, `statistic_explorer_pdf.html` |
| Layout / nav bar | — | `templates/base.html` |
| Settings / root URLs | `psl_app_project/settings.py`, `urls.py` | — |
