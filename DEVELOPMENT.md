# Development Guidelines & Conventions

This document outlines the standards, workflows, and local execution conventions for the `ljpa_reworked` project.

## 1. Local Testing & Execution Policy

* **Local Host Execution:** All function calls, unit tests, module executions, and debugging tasks must be performed **directly on the local host machine** using `uv`.
* **Docker Container Policy:** Docker Compose services (`cloak-browser`, `linkedin-bot`) are intended for target deployment and VNC session holding. **Do NOT build or rebuild Docker images during routine local testing** unless explicitly instructed to test container builds.
* **Pre-built Docker Image Preference:** Always prioritize using existing, ready-to-use Docker images from Docker Hub in `compose.yml`. Avoid creating custom `Dockerfile`s unless no suitable pre-built image exists.

## 2. Dependency Management & Formatting

* **Dependency Management:** Managed via `uv`. Install project dependencies locally:
  ```bash
  uv pip install -e .
  ```
* **Code Quality:** Formatted and checked via `ruff`:
  ```bash
  uv run ruff format .
  uv run ruff check .
  ```

## 3. Database Migrations & Web Inspection (SQLite)

The application uses SQLite (`data/app.db`) managed via SQLAlchemy and Alembic.

Whenever modifying models in `src/ljpa_reworked/models/database_models.py`:
1. Update Python model definitions.
2. Generate an Alembic revision:
   ```bash
   uv run alembic revision --autogenerate -m "Description of changes"
   ```
3. Inspect the migration script in `src/ljpa_reworked/migrations/versions/`.
4. Apply the migration to `data/app.db`:
   ```bash
   uv run alembic upgrade head
   ```

### Web Database Inspection (`sqlite-ui`)
For visual database inspection in a web browser, start the optional `sqlite-ui` debug service:
```bash
docker compose --profile debug up -d sqlite-ui
```
Open `http://localhost:7901` in your browser to view, query, and edit the SQLite database via `sqlite-web`.

## 4. Interactive Browser Authentication & VNC

To perform initial or periodic LinkedIn session renewal:
1. Start the browser container: `docker compose up -d cloak-browser`.
2. Connect to the VNC session in your web browser: `http://localhost:6080`.
3. Perform the login manually in the open Chromium window.
4. Execute `src/operations/login_harness.py` to capture and verify `auth/state.json`.

## 5. Testing & Verification

Run tests locally using `pytest`:
```bash
uv run pytest
```
Ensure all harness components and database operations pass before completing features.


## 4. Local Execution & Docker Strategy

- **Development & Testing**: Execute Python modules, scripts, and tests directly on the local host machine during development.
- **Docker Deployment**: Docker containers are maintained for target deployment. Avoid building or running Docker images for routine testing tasks unless specifically testing the container build itself.
