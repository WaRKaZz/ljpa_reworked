# Development and Conventions

This document outlines the development standards, workflows, and conventions for the `ljpa_reworked` project.

## 1. Code Standards & Dependency Management

- **Dependency Management**: We use `uv` for lightning-fast dependency management. Install dependencies via `uv pip install -r requirements.txt` (or equivalent `uv` commands).
- **Code Formatting & Linting**: We use `ruff` to maintain code quality.
  - To format code: `uv run ruff format .`
  - To check for linting errors: `uv run ruff check .`

## 2. Database Migrations Workflow

Whenever changes are made to SQLAlchemy models in `src/ljpa_reworked/models/`:
1. Modify the Python classes.
2. Generate an Alembic revision:
   ```bash
   alembic revision --autogenerate -m "Description of changes"
   ```
3. Inspect the generated migration file in `src/ljpa_reworked/migrations/versions/` to ensure correctness.
4. Apply the migration to the database:
   ```bash
   alembic upgrade head
   ```

## 3. Testing and Debugging

- **Unit and Integration Tests**: Ensure tests are run before merging. You can find tests under `src/ljpa_reworked/tests/`.
- **Debugging**: When debugging agents, it may be useful to run them independently of the scraping pipeline to save time and API costs.
