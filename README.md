# Ops Apps

Internal operations apps built on Django + PostgreSQL, replacing Microsoft Power Apps.
First app: **KYC review queue**. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Docker (for Postgres).

```bash
cp .env.example .env
docker compose up -d db
uv sync
uv run pre-commit install
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py seed_kyc_demo     # optional: demo users reviewer/demo, approver/demo
uv run python manage.py runserver
```

Open http://localhost:8000.

## Common commands

```bash
uv run pytest                      # tests (needs Postgres running)
uv run ruff check . && uv run ruff format .
uv run python manage.py makemigrations
docker compose --profile full up   # run the production image locally on :8000
```

## Configuration

All configuration is via environment variables; see [.env.example](.env.example).
Production needs at least `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS`, `SECURE_SSL_REDIRECT=true` and `SECURE_HSTS_SECONDS`.
The container runs `gunicorn` on port 8000; run `python manage.py migrate` on deploy.
Uploaded documents are written to `MEDIA_ROOT` (`/app/media` in the image), which **must** be a
persistent volume until document storage moves to blob storage.
