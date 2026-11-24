# Architecture

## Overview

```
                 ┌──────────────┐
                 │   Client     │ (unique name, sector, client_status)
                 │   └ Contact  │ (name unique per client, email, phone)
                 └──────┬───────┘
          PROTECT FK    │     SET_NULL FK (contact)
      ┌─────────────────┼──────────────────┐
      ▼                                    ▼
┌──────────────┐  sale FK (CASCADE)  ┌──────────────┐  award FK (CASCADE)  ┌──────────────┐
│ SalesEnquiry │ ◄────────────────── │ MonthlyAward │ ◄─────────────────── │ InvoicedJob  │
│ (sales_      │   optional; manual  │              │   required; many     │              │
│  tracker)    │   awards have none  │              │   invoices per award │              │
└──────────────┘                     └──────────────┘                      └──────────────┘
```

Django apps (all in `INSTALLED_APPS`):

| App | Purpose | Models |
|---|---|---|
| `dashboard` | Home page with cards linking to each section | none |
| `clients` | Company + contact records, autocomplete APIs, cleanup commands | `Client`, `Contact` |
| `sales_tracker` | Enquiries/quotes and their status | `SalesEnquiry` |
| `monthly_awards` | Awarded jobs, browsed by month | `MonthlyAward` |
| `invoiced_jobs` | Invoices against awards, browsed by month | `InvoicedJob` |
| `statistic_explorer` | Charts/stats over enquiries + PDF/print export | none |

Auth: Django's built-in login (`/login/`, `templates/registration/login.html`). Every view requires login. Users are created in Django admin (`/admin/`). There are no per-user permissions — every logged-in user can do everything.

## Models

### `clients.Client`
- `name` — **unique**. This is how clients are matched when typing a company name in any form.
- `sector` — `SECTOR_CHOICES`: architects, local_authority, consulting_engineer, construction, flood_consultancy, government_agency, retail, other (default `other`).
- `client_status` — `CLIENT_STATUS_CHOICES`: current (default), new, dormant.

### `clients.Contact`
- `client` FK (CASCADE, `related_name='contacts'`), `name`, `email`, `phone`.
- `unique_together = (client, name)` — two companies can both have a "John Doe".

### `sales_tracker.SalesEnquiry`
- `job_number` (char, 20) — free text, usually numeric like `1234` or `1234.2`.
- `date`, `value` (Decimal), `location`, `note`.
- `status`: `Pending` (default), `Rejected`, `Awarded`, `Not_Quoted`.
- `feedback`: Price / Timeframe / Capability / Other, plus `other_feedback` text.
- `referral`: google / recommendation / website_form (Website Contact Form) / other — adding a source also needs a colour in `_REFERRAL_PALETTE` (`statistic_explorer/views.py`, tested) and a migration — **a client-level value stored on every enquiry**: all enquiries of a client share it (see flow 9). Entered on the add form only when Client Status is `new`; editable on the edit form.
- `client` FK (**PROTECT** — a client with enquiries can't be deleted), `contact` FK (SET_NULL).
- `created_by`, `created_at`, `updated_at` (the last is used by live-refresh polling).

### `monthly_awards.MonthlyAward`
- `sale` FK to SalesEnquiry (**optional**, CASCADE). Null = a manually created award.
- Copies of `job_number`, `location`, `client` (PROTECT), `contact`, `value` — kept in sync with the sale (see below).
- `date` = award date (auto-awards use today's date).
- Helpers: `get_invoice_count()`, `has_no_invoices()`, `has_value_mismatch()`, `get_total_invoiced()`.

### `invoiced_jobs.InvoicedJob`
- `award` FK (required, CASCADE, `related_name='invoiced_jobs'`). **Many invoices per award** are allowed (staged invoicing).
- `description`, `date` (invoice date — the month it shows under).
- Department values: `utility_value`, `cad_value`, `topo_value`, `contractor_value`.
- `psl_value` — **auto-calculated in `save()` as utility + cad + topo** (i.e. everything except contractor). Not editable.
- `status`: Pending / Invoiced. `follow_up_status`: `n_a` / `to_follow` / `followed_up` (+ `followed_up_date`); default `n_a` (before migration 0009 the default was the invalid `"N/A"`).
- **Mismatch** = sum of *all* invoices' four values for an award ≠ award value (rounded to 2 dp). Shown as a warning on Monthly Awards and Invoiced Jobs.

## Key data flows

All in `sales_tracker/views.py::edit_sales_enquiry` unless noted.

1. **Enquiry added** (`add_sales_enquiry`): status Pending. `get_or_create_client()` finds/creates the Client by trimmed company name (sector/status only applied to a *new* client) and the Contact by name within it; existing contact email/phone are overwritten with what was typed. Job number is pre-filled as highest numeric job number + 1.
2. **Status → Awarded**: the form shows a modal asking for projected invoice date and department values (`invoice_date`, `invoice_utility_value`, `invoice_cad_value`, `invoice_topo_value`, `invoice_contractor_value` in the POST). The view creates one `MonthlyAward` (date = today) and one `InvoicedJob` (status Pending) from them. Blank/invalid values → today / 0.
3. **Edit while still Awarded**: all linked awards get the enquiry's job_number/location/client/contact/value; the **first** invoice of the first award gets any non-blank `invoice_*` values.
4. **Status Awarded → anything else**: all linked awards deleted → their invoices cascade-delete.
5. **Edit a Monthly Award** (`monthly_awards/views.py::edit_monthly_award`): copies job_number/location/client/contact/value back to the linked sale.
6. **Delete a Monthly Award**: linked sale's status set back to `Pending`; invoices cascade.
7. **Delete a Sales Enquiry**: its awards and their invoices cascade-delete.
8. **Manual award** (`add_monthly_award`): no sale, no invoice — invoices are added from the awards page (`add_invoice_to_award`) or the Invoiced Jobs page.
9. **Client referral & status** (`sales_tracker/client_sync.py`, called by `add_sales_enquiry`, `edit_sales_enquiry` and `edit_monthly_award`):
   - Add: a referral given (Client Status `new`) is applied to all the client's enquiries; otherwise the new enquiry inherits the client's existing referral.
   - Edit: the enquiry's referral (including blank) is applied to all the client's enquiries. If the enquiry moved to another client and the referral wasn't changed, it takes the new client's referral (if that client has one).
   - A `new` client with more than one enquiry becomes `current` (never touches `dormant`, never goes back to `new`).

## List pages — shared conventions

- Default **100 rows per page**. Sales Tracker allows up to 200; Monthly Awards / Invoiced Jobs cap at 100; Clients accepts exactly 50/100/200.
- **Search** (`?search=`) covers job number, location, client name, contact name (and contact email on Sales/Awards).
- **Sort** (`?sort_by=`): `date` (default), `job_number` (version-aware: `9999.10` > `9999.2`; non-numeric job numbers sort first), `value` (Awards/Invoices).
- Monthly Awards and Invoiced Jobs filter by `?year=&month=` (default current month; year dropdown 2020 → next year).
- **State round-trip**: add/edit/delete links carry `page`, `sort_by`, `search`, `per_page`, `scroll` (+`year`/`month`) and the view redirects back with them so users return to the same scroll position.
- **Row selection helper**: clicking rows sums values in a floating helper (JS in each list template).
- **Sticky bars**: filter bar and pagination use `position: fixed` (commits 6a4b0f7–6b50f4f).
- Sales Tracker row colours: pending, **pending with value 0 = light blue**, awarded, rejected/not quoted.
- **Live refresh** (Sales Tracker only): JS polls `sales_tracker_poll` every 3 s with `last_update` (max `updated_at`) and `last_count`; when either changed, the endpoint returns the re-rendered rows (`partials/table_body.html`, the same partial the page includes) and the JS swaps the `<tbody>` contents, keeping selected rows. Polling pauses while the tab is hidden and when a link/form is used.
- Client fields on forms use an autocomplete dropdown backed by `client_autocomplete` and `client_contacts_api` (JSON); dropdowns close on mousedown outside.

## Invoiced Jobs totals (per month)

`total_invoiced` (status Invoiced) + `total_pending` = `total_value`; `total_psl_value = total_value − contractor`; plus per-department totals and counts. Computed in Python in `invoiced_jobs_list`.

## Statistic Explorer

`StatisticExplorerView.get_context_data` (≈400 lines) computes, over **SalesEnquiry** records filtered by `filter_type` = `all` | `month` (`year`,`month`) | `range` (`date_from`,`date_to`): status breakdown (count/value/%, plus average/lowest/highest quote value over quotes with value > £0), feedback reasons, sector breakdown (with win rates), client-status breakdown, referral sources. **Client Analysis**: `client_quote_stats()` returns one row per client from Pending/Awarded/Rejected enquiries over £0 (`SalesEnquiry.QUOTED_STATUSES`), sorted by total quoted; win rate = awarded ÷ quotes (pending included, as elsewhere on the page). The page renders every row and the JS shows the top 20 (`CLIENT_TABLE_TOP_N`), sorts columns, and filters by the search box; the detail card reads the rows from a `json_script` block. `?client=<name>` pre-fills the search (used by the "£X quoted" badge on the Clients page, whose total uses the same rule). **New Client Conversion** (inside Referral Analysis): `referral_conversion_stats()` takes clients with a referral source whose *first-ever* enquiry falls in the filtered period (the filter picks when the client was won) and follows each up to today: came back = 2+ enquiries (any status), won work = 1+ Awarded enquiry, converted = both. One summary row per source plus an "All sources" total, an outcome bar per source, and a collapsible per-client list; the totals table is in the PDF under `show_referral`. Clients with no referral recorded (pre-referral legacy clients) are left out. Chart data is passed as lists to Chart.js in the template. Sector colours come from `_palette` indexed by `SECTOR_CHOICES` order. `StatisticExplorerPDFView` re-uses that context and renders `statistic_explorer_pdf.html` (pure HTML/CSS with `@page` rules, no JS) to a PDF with WeasyPrint. If WeasyPrint or its Pango system libraries are unavailable (`ImportError`/`OSError`, e.g. on Windows) it returns the same page as printable HTML with a Print button.

## URLs

Root `psl_app_project/urls.py` includes each app with prefixes **without trailing slashes**, so real paths are e.g. `/sales-tracker` (list), `/sales-trackeradd/`, `/sales-trackeredit/5/`, `/monthly-awardsedit/5/`, `/invoiced-jobsawards/5/add-invoice/`. Always reverse by name:

| Name | View |
|---|---|
| `dashboard`, `login`, `logout` | home, auth |
| `sales_tracker`, `add_sales_enquiry`, `edit_sales_enquiry`, `delete_sales_enquiry`, `sales_tracker_poll` | sales_tracker |
| `monthly_awards_list`, `add_monthly_award`, `edit_monthly_award`, `delete_monthly_award` | monthly_awards |
| `invoiced_jobs_list`, `add_invoiced_job`, `edit_invoiced_job`, `delete_invoiced_job`, `add_invoice_to_award` | invoiced_jobs |
| `statistic_explorer`, `statistic_explorer_pdf` | statistic_explorer |
| `clients_list`, `client_add`, `client_edit`, `client_delete`, `client_autocomplete`, `contact_list`, `contact_add`, `contact_edit`, `contact_delete`, `client_contacts_api` | clients |

## Management commands (clients app)

Used during the 1.1.0 client normalisation; safe to re-run, all support `--dry-run` except `diagnose_client`:

- `deduplicate_clients [--dry-run]` — merge Client rows with the same name.
- `fix_contact_data [--dry-run]` — merge duplicate contacts per client, report enquiries/awards with no client/contact.
- `diagnose_client "<name fragment>"` — show matching clients and their linked counts.

## Migration history notes

- `sales_tracker` 0012–0015 / `monthly_awards` 0004–0006: moved free-text client fields into `Client`/`Contact` (add FK → data migration `sales_tracker/0013` → drop old fields → add contact FK).
- `clients/0005` renames a column with guarded raw SQL so it's a no-op where already applied — pattern to copy for any risky migration.
- `clients/0006` (2026-11-23): records the Flood Consultancy choice; choices-only, no SQL.
- `sales_tracker/0017` (2026-11-23): data-only — copies each client's referral to all its enquiries (earliest enquiry's value wins on conflict) and promotes `new` clients with >1 enquiry to `current`. Re-runnable; reverse is a no-op.

## Tests

`python manage.py test` — one `tests.py` per app, shared helpers in `psl_app_project/test_utils.py`. Coverage: login protection and smoke-render of every page, missing-migration check, enquiry add/client matching, the full award/un-award/sync/cascade flows, award list flags, invoice PSL/mismatch/monthly totals, client CRUD/protection/APIs/contacts page, live-refresh endpoint, follow-up status migration, statistic explorer filters/colours/PDF (real and fallback paths), client analysis figures, new-client conversion by referral source. Bugs not yet fixed should be pinned with `@unittest.expectedFailure`.
