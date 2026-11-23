# Known issues & quirks

Reviewed 2026-11-23. If you fix something here, add a regression test and move it to "Fixed".

## Open bugs

None known.

## Quirks (behaviour users rely on — change only on purpose)

- URL prefixes lack a trailing slash → paths like `/sales-trackeradd/`. Always use URL names.
- Sorting by job number puts non-numeric job numbers before numeric ones.
- Editing an awarded enquiry only updates the **first** invoice of the **first** award with the modal values.
- Award date for auto-created awards is "today" in UTC (`TIME_ZONE='UTC'`), so an award made just after midnight UK summer time is dated the previous day.
- `get_or_create_client()` is copy-pasted in `sales_tracker/views.py` and `monthly_awards/views.py`.
- Typing an existing contact's name with a blank email/phone **clears** their stored email/phone.
- Monthly Awards / Invoiced Jobs add/edit views default `per_page` to `'10'` in the redirect when the link didn't pass it (list defaults are 100).
- On Windows dev machines "Export PDF" returns the printable HTML page instead of a PDF (WeasyPrint's Pango libraries aren't installed there). Production (Docker) produces real PDFs.

## Housekeeping

- `STATICFILES_STORAGE` in settings is ignored by Django ≥ 5.1 (replaced by `STORAGES`), so WhiteNoise compression/manifest isn't active. Harmless today since nginx serves `/static/`; if switching, use `STORAGES = {"staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}, "default": {...}}` and test `collectstatic`.
- `invoiced_jobs/forms.py` has an unused `from email.policy import default` import.
- Old Claude worktree branches `claude/goofy-cerf` and `claude/naughty-albattani` are fully merged into `main` and can be deleted.

## Fixed (2026-11-23)

| Bug | Fix | Regression test |
|---|---|---|
| Sales Tracker live refresh 500'd every 3 s (`partials/table_body.html` deleted in v1.0.7) | Recreated the partial; `sales_tracker.html` now `{% include %}`s it so page and live refresh share one row template | `sales_tracker.tests.PollEndpointTests` |
| Poll capped `per_page` at 100 while the page allows 200 | Poll caps at 200, same as the page | `test_poll_honours_200_per_page_like_main_view` |
| `/clients/<id>/contacts/` 500'd (template missing) | Added `clients/contact_list.html` | `clients.tests.ClientCrudTests.test_contact_list_page*` |
| Auto-created invoices stored invalid follow-up status `"N/A"` | Model default → `'n_a'`; migration `invoiced_jobs/0009` converts existing `"N/A"` rows | `invoiced_jobs.tests` (default + migration), award-flow test |
| Client delete error only counted enquiries | Message lists enquiries and/or awards | `test_client_with_only_awards_cannot_be_deleted_and_message_says_why` |
| "Export PDF" never produced a PDF (WeasyPrint not installed) | `weasyprint==66.0` in requirements, Pango/HarfBuzz/fonts in Dockerfile; view also falls back on `OSError` (libs missing) | `statistic_explorer.tests` (PDF, ImportError and OSError paths) |
| Database dumps could be committed / copied into the Docker image | `*.sql`, `*.sql.gz`, `backups/` in `.gitignore` and `.dockerignore` | — |
| Missing migration for the Flood Consultancy sector choice | `clients/0006` (no SQL) | `dashboard.tests.MigrationTests` |
