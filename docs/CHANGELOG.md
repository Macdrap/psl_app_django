# Changelog

Reconstructed from git history. Newest first.

## Unreleased (next version)
- Statistic Explorer: "Sales Enquiries by Status" shows Average, Lowest and Highest quote value for the selected period (also in the PDF export). £0 quotes are excluded as unpriced.
- Statistic Explorer: new **Client Analysis** section — one row per client quoted for (quotes, total quoted, awarded count/value, win rate, average quote, last quote), sortable, top 20 with "Show all", and a client search that opens a detail card (awarded/pending/rejected, win rate by count and value, link to the client's enquiries in Sales Tracker). Follows the date filter; top 20 in the PDF export. A quote = Pending/Awarded/Rejected enquiry over £0 (`SalesEnquiry.QUOTED_STATUSES`).
- Clients page: each client shows a "£X quoted" badge (all time) linking to its figures in Statistic Explorer (`?client=<name>`).

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
