# Changelog

Reconstructed from git history. Newest first.

## Unreleased (next version)

## 2026-11-25 — Version 1.2.0
Survey types, Client Analysis, per-enquiry referral source with client default, new-client conversion stats. Deploy rehearsed on a replica of the server with live data (all migrations applied, no rows lost, no referral changed, 8 `new` clients → `current`).
- **Survey types (departments)**: CAD is renamed **MBS** (all existing CAD values are now MBS values — migration `invoiced_jobs/0010` renames the column in place); Utility, Topo and Contractor unchanged; new **Watercourse, CCTV Drainage, 3D Modelling, Drone Survey, Engineering**. One list in `sales_tracker/survey_types.py`.
- Each job can have one or more survey types, chosen on the enquiry add/edit form at any status (no need to award it) and on the Monthly Award form; kept in sync between an enquiry and its award. A department given a value on an invoice is added to the job's survey types automatically.
- New **Survey Type** column in Sales Tracker, Monthly Awards and Invoiced Jobs.
- Edit enquiry and Monthly Award forms: enter a **value per survey type**; the Total Value is their sum (read-only). Awarding copies it to the award and creates the invoice from it (the award modal now only asks for the projected invoice date). After that the enquiry is the quote and the award is what was awarded: they can differ, the award's values are edited on Monthly Awards (its form shows the quote), and only job number / location / client / contact stay in sync between them. **Previously editing either one copied its value to the other.** Awarding an enquiry, or adding a manual award, needs at least one survey type; old records with no survey type keep a typed-in value. Sales Tracker shows the split as a tooltip on the value; Statistic Explorer uses the enquiries' split for quoted £ and the awards' split for awarded £. Migrations `sales_tracker/0021` and `monthly_awards/0009` split existing values where it's known (single type, the linked enquiry's split, or invoices that add up).
- Invoice form has a value input per department. PSL value = everything except Contractor. Invoiced Jobs shows a total card per department.
- Migration `invoiced_jobs/0011` gives existing awarded jobs survey types from their invoice values.
- Statistic Explorer: **Survey Type Analysis** — per survey type enquiries, quotes, quoted, awarded count/value, win rate, pending, rejected, using each job's value by survey type (so the figures add up), with an awarded value total and charts; in the PDF export.
- Statistic Explorer: "Sales Enquiries by Status" shows Average, Lowest and Highest quote value for the selected period (also in the PDF export). £0 quotes are excluded as unpriced.
- Statistic Explorer: new **Client Analysis** section — one row per client quoted for (quotes, total quoted, awarded count/value, win rate, average quote, last quote), sortable, top 20 with "Show all", and a client search that opens a detail card (awarded/pending/rejected, win rate by count and value, link to the client's enquiries in Sales Tracker). Follows the date filter; top 20 in the PDF export. A quote = Pending/Awarded/Rejected enquiry over £0 (`SalesEnquiry.QUOTED_STATUSES`).
- Clients page: each client shows a "£X quoted" badge (all time) linking to its figures in Statistic Explorer (`?client=<name>`).
- Referral source is per enquiry and always shown on the add form. A new enquiry for an existing client defaults to the referral of that client's previous enquiry (pre-filled when the client is picked from the dropdown, and applied on save if left blank); it can be changed on add or edit without affecting the client's other enquiries. Logic in `sales_tracker/client_sync.py`.
- A `new` client automatically becomes `current` once it has more than one enquiry.
- Statistic Explorer: **New Client Conversion** in Referral Analysis — for new clients from Google / Recommendation / Other whose first enquiry was in the selected period: how many came back for another enquiry, how many won work, and how many converted (came back *and* awarded), with enquiries per client, awarded jobs/value, an outcome bar per source and a per-client list linking to Sales Tracker. Totals table in the PDF export.
- New referral source **Website Contact Form** (`website_form`, migration `sales_tracker/0018`); amber in Statistic Explorer charts.
- Migration `sales_tracker/0017` promotes existing `new` clients with 2+ enquiries to `current`. It does **not** change any referral source: existing referral data stays as it is.

## 2026-11-23 — Version 1.1.1
- Docs: `CLAUDE.md`, `docs/` (architecture, deployment, known issues, changelog), rewritten README, `.env.example`.
- Tests: first real test suite (59 tests across all apps).
- Fix: Sales Tracker live refresh works again (row template restored as a shared partial; poll honours 200 per page).
- Fix: Contacts page for a client (`/clients/<id>/contacts/`) no longer errors.
- Fix: invoices created by awarding a job get a valid follow-up status; migration `invoiced_jobs/0009` repairs existing rows.
- Fix: "cannot delete client" message mentions linked awards as well as enquiries.
- Fix: Statistic Explorer "Export PDF" produces a real PDF in production (WeasyPrint + system libraries in the Docker image).
- `clients/0006` migration recording the Flood Consultancy sector choice (no DB change).
- Database dumps excluded from git and Docker images.

## 2026-11-19 — security / ops (PRs #1, #2)
- Nginx: HTTP/2 disabled to mitigate NGINX HTTP/2 RCE (NCSC/Netcraft).
- `deploy.sh` pulls fresh base images and builds with `--pull`.
- Deploy workflow hardened (SSH opened only to runner IP, pinned actions) and **switched to manual-only** — push to `main` no longer deploys.

## 2026-04-23
- Clients: Flood Consultancy sector (+ chart colour), per-page selector 50/100/200 (default 100).
- Sales Tracker: referral column.
- Invoiced Jobs: read-only copyable location on edit form.

## 2026-04-22 — Version 1.1.0
- Clients/contacts normalised into the `clients` app (one Client per company, many Contacts), with data migration and dedup commands.
- Client sector & status, referral tracking on new-client enquiries; Statistic Explorer sections for sector, client status, referral.
- Fixes: migration 0005 safe on fresh DBs, dropdown close via mousedown, invoiced-jobs contact search, sticky filter/pagination bars, scroll position kept when editing/deleting invoices.

## 2025-12-30 — Version 1.0.7
- Sales Tracker: feedback field, "Not Quoted" status, award modal asks for projected invoice date + department values, scroll position restored, 200-per-page option.
- All: search by contact name, fixed top nav bar. Statistic Explorer: feedback stats. Invoiced Jobs: helper sums all columns.

## 2025-11-28 — Versions 1.0.5 / 1.0.6
- Sales Tracker: live update on delete, next job number auto-suggested.
- Invoiced Jobs: follow-up column; follow-up colour on the cell only. Nav order: Statistic Explorer last.

## 2025-11-27 — Version 1.0.4
- New Statistic Explorer; nav links to all pages.
- Sales Tracker: blue rows for pending with value 0, live update on edits/new jobs.
- Invoiced Jobs: per-department totals and PSL value; removed "push pending invoice to current month".
- All lists: 100 per page default, search by client, row selection with running total.

## 2025-10 / 11 — Versions 1.0.1–1.0.3
- Per-page choice, stay on current page after edit, nav buttons; notes on enquiries; 30-day backup retention.

## 2025-10-10 — First working version
