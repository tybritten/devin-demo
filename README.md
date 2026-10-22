# Ops Apps

Internal operations apps built on Django + PostgreSQL, replacing Microsoft Power Apps.
Apps: **KYC review queue** (`/kyc/`), **Refunds** (`/refunds/`) and **Feature flags** (`/flags/`). See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Docker (for Postgres).

```bash
cp .env.example .env
docker compose up -d db
uv sync
uv run pre-commit install
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py seed_demo         # optional, local only: demo data + users reviewer,
                                          # approver, finance, engineer, auditor, integrator (password: demo)
uv run python manage.py runserver
```

Open http://localhost:8000.

## Common commands

```bash
uv run pytest                      # tests (needs Postgres running)
uv run ruff check . && uv run ruff format .
uv run python manage.py makemigrations
uv run python manage.py startopsapp <label> --model <Model> --title "<Title>"  # new app
uv run python manage.py purge_audit_log   # delete audit entries past retention; schedule daily
uv run python manage.py run_import --list # importers from Dataverse/SharePoint; --all to run
uv run python manage.py check_integration <slug>  # test an external system's credentials
docker compose --profile full up   # run the production image locally on :8000
```

## Configuration

All configuration is via environment variables; see [.env.example](.env.example).
Production needs at least `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS`, `SECURE_SSL_REDIRECT=true` and `SECURE_HSTS_SECONDS`.
The container runs `gunicorn` on port 8000; run `python manage.py migrate` on deploy.
Uploaded documents are written to `MEDIA_ROOT` (`/app/media` in the image), which **must** be a
persistent volume until document storage moves to blob storage.

The audit log keeps entries for `AUDIT_RETENTION_DAYS` (default `365`); run `purge_audit_log`
daily from a scheduled job. Behind a proxy (Azure Front Door / App Service) set
`AUDIT_PROXY_COUNT` so client IPs are recorded correctly.

Refunds above `REFUND_APPROVAL_LIMIT` (default `1000`, in `REFUND_CURRENCY`, default `USD`)
need a member of **Refunds Senior Approver**.

## Feature-flag API

Services read flags over a read-only JSON API. Create a client in **Admin → API clients**; the
token is shown once (only its hash is stored). Then:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/flags/api/v1/flags/
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/flags/api/v1/flags/checkout.new_flow/?target=customer-1001"
```

The list endpoint returns each flag's `enabled`, `rollout_percentage` and `targets` so clients
can cache and evaluate locally; the bucketing rule is `int(sha256(f"{key}:{target}")[:8], 16) % 100`.
