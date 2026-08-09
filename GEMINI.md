# Project Overview

This project is an automated job discovery, resume tailoring, and job application system. It integrates the **Google Antigravity SDK (`agy`)** and **CrewAI** for autonomous agent workflows, **Playwright / CloakBrowser** for anti-detect web scraping, **RenderCV** for ATS-compliant resume PDF generation, and **SQLite** for lightweight local data persistence.

## Key Technologies

* **Python:** Core application programming language managed via `uv`.
* **Google Antigravity SDK (`agy`):** Autonomous agent engine and MCP integration.
* **CrewAI:** Multi-agent orchestration for vacancy evaluation and response generation.
* **Playwright & CloakBrowser:** Anti-detect browser engine running in a dedicated container (`cloak-browser`) with `Xvfb` and VNC support (`http://localhost:6080`).
* **RenderCV:** Data-driven resume PDF compiler using YAML schemas.
* **SQLAlchemy & Alembic:** Database ORM and migration tool configured for SQLite (`data/app.db`).
* **sqlite-web / sqlite-ui:** Optional web dashboard container (`http://localhost:7901`, `profile: debug`) for visual database inspection.
* **OpenAI-Compatible API:** External LLM integration via configurable base URLs.

## System Architecture

The application pipeline operates through the following steps:

1. **Browser Authentication (Stage 1):** Interactive login to LinkedIn performed via noVNC (`http://localhost:6080`) on the `cloak-browser` container. Session credentials are persisted in `./auth/state.json`.
2. **Job Discovery:**
   * *Harness 1 (Post Search Agent):* Executed inside `antigravity-cli` container (`antigravity-cli-dev`) via `podman exec`. Reads `resources/profile.md`, expands job titles, navigates LinkedIn Posts feed via MCP Unbrowse over `http://cloak-browser:9222`, extracts recent recruiter posts, and persists records to SQLite (`data/app.db`) in `Vacancy` and `LinkedinPost` tables.
   * *JobSpy Service (`services/jobspy.py`):* Standard Python ETL pipeline using `python-jobspy` to fetch official job postings directly from API endpoints without browser automation or LLM.
3. **Data Ingestion:** Extracted vacancies are normalized and deduplicated in SQLite (`data/app.db`).
4. **Vacancy Review & Evaluation:** `VacancyReviewCrew` and `ResumeEvaluationCrew` evaluate job fit against candidate profile.
5. **Resume Generation:** `ResumeGenerationCrew` outputs strict YAML tailored to the job, which `RenderCV` compiles into an ATS-compliant PDF.
6. **Application Submission:** `EmailGenerationCrew` drafts candidate applications via email. For web form or LinkedIn Easy Apply vacancies, **Harness 2 (Auto-Apply Web Application Agent)** navigates the portal via MCP Unbrowse to submit the candidate's resume directly.

## Development & Execution Rules

* **Local Testing Policy:** Execute and test code directly on the local machine using `uv` during routine development. **Do NOT build or rebuild Docker images during local testing** unless explicitly testing container image builds.
* **Docker Image Selection Policy:** Prioritize using existing, pre-built Docker Hub images (e.g., official Playwright or pre-built CloakBrowser containers) in `compose.yml`. **Do NOT write or maintain custom Dockerfiles unless strictly necessary.**
* **Database Management:** The database uses SQLite (`sqlite:///data/app.db`). Any model modifications in `src/ljpa_reworked/models/` require generating an Alembic migration (`uv run alembic revision --autogenerate -m "..."`) and applying it (`uv run alembic upgrade head`).
* **Code Formatting:** Maintain code quality via `ruff`: `uv run ruff format .` and `uv run ruff check .`.

