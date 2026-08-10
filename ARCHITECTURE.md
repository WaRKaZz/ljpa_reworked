# Architecture Overview

This project is an automated job search, candidate evaluation, resume generation, and job application pipeline powered by Python, the Google Antigravity CLI (`agy`), CrewAI, RenderCV, Playwright/CloakBrowser, and SQLite.

## 1. System Pipeline Overview

The end-to-end execution flow consists of seven distinct stages:

1. **Authentication (Stage 1):** Interactive login to LinkedIn via the `cloak-browser` container using noVNC (`http://localhost:6080`). Saves session state to `./auth/state.json`.
2. **Job Discovery (Harness 1 & 2):**
   * *Harness 1 (Posts Scraper):* `agy` Agent uses MCP Unbrowse server to navigate LinkedIn Posts feed via `ws://cloak-browser:9222`.
   * *Harness 2 (JobSpy ETL):* `python-jobspy` pulls job postings directly from API endpoints.
3. **Data Ingestion & Deduplication:** Job vacancies are normalized and stored in SQLite (`data/app.db`) via SQLAlchemy.
4. **Vacancy Review & Evaluation:** `VacancyReviewCrew` parses raw job data, and `ResumeEvaluationCrew` scores vacancy fit.
5. **ATS Resume Generation:** `ResumeGenerationCrew` outputs strict YAML data, which `RenderCV` compiles into an ATS-compliant PDF resume.
6. **Application Email Generation:** `EmailGenerationCrew` drafts personalized cover letters/emails.
7. **Application Submission & Fallback:**
   * *Primary:* Sends application email with attached RenderCV PDF resume to the recruiter.
   * *Fallback (Harness 3):* If no email is available, an `agy` agent navigates the web application portal via `ws://cloak-browser:9222` to submit the application form automatically.

## 2. Docker Container Topology

The deployment environment consists of two isolated containers orchestrated via Docker Compose:

```text
===================================================================================================
                   MULTI-CONTAINER TOPOLOGY (DOCKER COMPOSE)
===================================================================================================

[ HOST MACHINE ]
  │
  └─► Access VNC Browser ─────────────────► http://localhost:6080 (or port 5900)
                                                    │
                                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CONTAINER 1: cloak-browser (Browser Sidecar)                                                     │
│                                                                                                  │
│  [ Xvfb Virtual Display (Non-headless) ] ◄──► [ x11vnc / noVNC Web Server (Port 6080) ]          │
│                       ▲                                                                          │
│                       │                                                                          │
│  [ CloakBrowser Chromium ] ─────────────────► Remote CDP WebSocket: ws://cloak-browser:9222        │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                    ▲
                                                    │ CDP Protocol Connection
                                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ CONTAINER 2: linkedin-bot (Application Container)                                                │
│                                                                                                  │
│  [ Python App (ljpa_reworked) ]                                                                  │
│    ├── agy Agent + MCP Unbrowse Server ─────► Connects to ws://cloak-browser:9222               │
│    ├── Harness 2 (JobSpy ETL)                                                                    │
│    ├── CrewAI Crews & RenderCV Pipeline                                                          │
│    └── SQLAlchemy ORM ──────────────────────► Writes directly to SQLite (/app/data/app.db)   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│ OPTIONAL DEBUG CONTAINER: sqlite-ui (Profile: "debug")                                           │
│                                                                                                  │
│  [ sqlite-web Server ] ─────────────────────────► Web UI Access: http://localhost:7901           │
│    └── Reads SQLite DB directly from mounted /data volume                                        │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
===================================================================================================
[ PERSISTENT VOLUMES ]
  ├── ./auth ──► /app/auth/state.json (Authentication cookies & storage state)
  └── ./data ──► /app/data/app.db     (SQLite Database file shared between Host and Containers)
===================================================================================================
```

## 3. Technology Stack Summary

- **Core:** Python 3.11+ managed with `uv`.
- **Agent Engines:** Google Antigravity CLI (`agy`) & `crewai`.
- **Browser Automation:** Playwright, `CloakBrowser` (Anti-detect Chromium), Xvfb, noVNC.
- **Resume Compilation:** `RenderCV` (YAML to ATS PDF engine).
- **Database & Migrations:** SQLite (`sqlite:///data/app.db`), SQLAlchemy ORM, Alembic migrations.
- **LLM Provider:** OpenAI-Compatible API endpoints (`OPENAI_API_BASE`).

## 4. Codebase Layout

Source code is organized inside [`src/ljpa_reworked/`](src/ljpa_reworked/):

- `crews/`: CrewAI crew definitions (`vacancy_review_crew`, `resume_evaluation_crew`, `resume_generation_crew`, `email_generation_crew`).
- `models/`: SQLAlchemy ORM schemas (`database_models.py`) and Pydantic validation models (`crewai_pydantic_models.py`).
- `operations/`: Business logic, ETL scripts, and harness implementations (`login_harness.py`, `harness1_posts.py`, `harness2_jobspy.py`, `harness3_apply.py`).
- `services/`: External service connectors (RenderCV runner, Telegram notifications, Email client).
- `tools/`: Custom CrewAI tools and MCP browser server bindings.
- `workflow.py`: End-to-end execution pipeline orchestrator.

