# Deployment & operations

## Production

- **Host:** AWS EC2, region eu-west-2, app checked out at `/opt/psl-app`. Domain `psl-app.net`.
- **Containers** (`docker/docker-compose.prod.yml`): `db` (postgres:15-alpine, volume `postgres_data`), `web` (Gunicorn, 3 workers, built from `docker/Dockerfile`), `nginx` (nginx:alpine, ports 80/443, serves `/static/` and proxies to `web:8000`).
- **Config:** `/opt/psl-app/.env` (`SECRET_KEY`, `DEBUG=False`, `DB_*`, `DB_HOST=db`, `ALLOWED_HOSTS`). With `DEBUG=False` settings turn on HTTPS redirect, secure cookies and HSTS.
- **SSL:** Let's Encrypt via certbot (webroot `/opt/psl-app/certbot/www`). `scripts/renew.sh` renews, copies certs into `certbot/conf/` and restarts nginx.
- **Logs:** `docker-compose ... logs -f`; Django errors also go to `logs/django.log` inside the container.

## Deploying (manual)

**Pushing to `main` does not deploy.** Auto-deploy was turned off on 2026-11-19 (PR #2). Two ways to deploy:

1. **On the server:**
   ```bash
   cd /opt/psl-app
   sudo git fetch origin main && sudo git reset --hard origin/main
   sudo bash scripts/deploy.sh
   ```
2. **GitHub Actions → "Deploy to AWS EC2" → Run workflow** (`.github/workflows/deploy.yml`, `workflow_dispatch` only). It temporarily opens SSH on security group `sg-0f9ae77e7d2f2fe50` to the runner's IP only, rewrites `.env` from repo secrets, runs `scripts/deploy.sh`, then removes the rule.

`scripts/deploy.sh`: `down` → remove local images → `pull` db/nginx (picks up security patches) → `build --pull --no-cache` → `up -d` → wait 15 s → `migrate` → `collectstatic --clear` → show status/logs. The web container's start script (`scripts/start.sh`) also runs `migrate` and `collectstatic` before Gunicorn.

### Next deploy after 2026-11-23
- The image now installs WeasyPrint + Pango/fonts (PDF export), so the first build takes a little longer and the image is larger. It was test-built locally and produced a correct PDF.
- Migrations `clients/0006` (no SQL) and `invoiced_jobs/0009` (changes follow-up status `"N/A"` → `"n_a"` on existing invoices) run automatically. Take a backup first.

### Before deploying
1. Tests pass locally (`manage.py test --noinput`).
2. `manage.py makemigrations --check --dry-run` reports nothing.
3. Take a backup (below) if the release has migrations.
4. After deploying, open the site and click through Sales Tracker, Monthly Awards, Invoiced Jobs, Clients, Statistic Explorer.

## Backups

`scripts/backup-database.sh` (run on the server): `pg_dump` from the `db` container → gzip into `/opt/psl-app/backups/` → upload to `s3://psl-app-db-backups` → delete local and S3 backups older than 30 days. Restore with `gunzip -c <file> | docker-compose ... exec -T db psql -U $DB_USER $DB_NAME`.

Local dumps (e.g. `backup.sql` in the repo root) contain client contact data — they are git-ignored (`*.sql`) and must never be committed.

## Security notes

- 2026-11-19: HTTP/2 disabled in `nginx/nginx.conf` as mitigation for an NGINX HTTP/2 RCE (NCSC/Netcraft issue 99004939). Re-enable `http2 on;` only once `docker exec <nginx-container> nginx -v` shows a patched release.
- GitHub Actions are pinned to commit SHAs; the workflow has `contents: read` only and a concurrency lock.

## Local development

1. Python venv in `.venv` (`python -m venv .venv`, `.venv\Scripts\pip install -r requirements.txt`).
2. Postgres running locally; copy `.env.example` to `.env` and fill it in (`DEBUG=True`, `DB_HOST=localhost`).
3. `manage.py migrate`, `manage.py createsuperuser`, `manage.py runserver`.
4. For tests the DB user needs permission to create databases (`ALTER USER <user> CREATEDB;`).

Docker alternative: `docker/docker-compose.yml` (dev, runserver with code mounted).
