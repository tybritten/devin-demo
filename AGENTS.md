# Agent notes

- Python deps are managed with uv (`uv sync`, `uv add <pkg>`); never edit `uv.lock` by hand.
- Postgres is required for tests: `docker compose up -d db` (uses `.env` / `DATABASE_URL`).
- Before committing: `uv run ruff check . && uv run ruff format . && uv run pytest`.
  pre-commit runs ruff and a migrations check.
- Business rules go in each app's `services.py`; views stay thin. Every case state change
  must write a `CaseEvent`.
- Create new apps with `manage.py startopsapp <label> --model <Model> --title "<Title>"`, not by
  copying an existing app. App configs subclass `apps.core.registry.OpsAppConfig`; never wire an
  app into `config/urls.py`, the navbar or `apps/core/views.py` by hand.
- Model changes in ops apps are audited automatically. Call `apps.audit.log.log_view(request, obj)`
  in views that show sensitive records (PII, documents). Never write secrets into audit `changes`.
- Never delete users (a guard refuses it); deactivate them with `apps.core.users.deactivate`.
- Every URL must pass `apps/core/tests/test_access_boundaries.py`; only add to its allowlists for
  a reviewed reason.
- Read `docs/ARCHITECTURE.md` before structural changes.
