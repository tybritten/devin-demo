# Agent notes

- Python deps are managed with uv (`uv sync`, `uv add <pkg>`); never edit `uv.lock` by hand.
- Postgres is required for tests: `docker compose up -d db` (uses `.env` / `DATABASE_URL`).
- Before committing: `uv run ruff check . && uv run ruff format . && uv run pytest`.
  pre-commit runs ruff and a migrations check.
- Business rules go in each app's `services.py`; views stay thin. Every case state change
  must write a `CaseEvent`.
- New apps live in `apps/<name>` with `AppConfig.name = "apps.<name>"`.
- Read `docs/ARCHITECTURE.md` before structural changes.
