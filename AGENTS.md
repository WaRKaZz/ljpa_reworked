# Agents and Crews Specifications

This document outlines the AI agents, crews, and tools utilized in the project.

## 1. Google Antigravity SDK (`agy`) Agents & Container Harnesses

All Harness agents are executed inside the dedicated **`antigravity-cli` (`agy`)** container, leveraging persistent skills, MCP servers (`.gemini`), session storage (`resources/state.json`), candidate resume (`resources/Danilov_Latest_CV.pdf`), and candidate personal profile (`resources/profile.md`).

- **`Harness 1: Post Search Agent`**:
  - **Container & Engine**: `antigravity-cli` container (`antigravity-cli-dev`) executing the Google Antigravity SDK (`agy` CLI) via `podman exec` / `docker exec` + MCP Unbrowse / Playwright server.
  - **Prompt Execution**: Triggered via `agy --print --dangerously-skip-permissions "<prompt>"`.
  - **Prompt Instructions**:
    1. Reads candidate profile from `resources/profile.md` and expands candidate target job titles across multiple relevant roles (e.g. Senior Python Developer, Backend Engineer, AI/ML Engineer, Fullstack Engineer, Tech Lead).
    2. Connects to `http://cloak-browser:9222` to navigate LinkedIn Posts feed.
    3. Extracts the **10 most recent vacancy posts with high candidate skills matching**.
    4. Maps fields and persists records into SQLite (`data/app.db`) following SQLAlchemy ORM schema:
       - `Vacancy` table (`title`, `text`, `credentials`, `url`, `source`="LinkedIn", `visa_status`="NOT_SPECIFIED", `processed`=False, `deleted`=False)
       - `LinkedinPost` table (`text`, `url`, `screenshot_path`, `vacancy_id`, `processed`=False, `deleted`=False)
  - **Output**: Validated SQLAlchemy records stored directly into SQLite (`data/app.db`).

- **`Harness 2: Official Job Postings Scraper`**:
  - **Container & Engine**: `antigravity-cli` container (`agy` CLI) executing `python-jobspy` ETL pipeline.
  - **Purpose**: API-level collection and deduplication of official LinkedIn job postings.
  - **Output**: Validated vacancy records saved to SQLite (`data/app.db`).

- **`Harness 3: Web Application Agent`**:
  - **Container & Engine**: `antigravity-cli` container (`agy` CLI) + MCP Unbrowse / Playwright server.
  - **Purpose**: Fallback web application agent for job vacancies lacking recruiter email addresses.
  - **Context**: Uses candidate profile (`resources/profile.md`) and ATS resume (`resources/Danilov_Latest_CV.pdf`).
  - **Output**: Submits job application forms via external web portals or LinkedIn Easy Apply using the user's RenderCV PDF resume.

## 2. CrewAI Crews

- **`VacancyReviewCrew`**:
  - **Purpose**: Analyzes scraped job posts to extract structured vacancy information.
  - **Output**: Pydantic validated JSON structure defining job title, requirements, location, and company details.

- **`ResumeEvaluationCrew`**:
  - **Purpose**: Evaluates candidate suitability against the job vacancy using `resources/profile.md`.
  - **Output**: Scoring report and boolean decision on whether to apply.

- **`ResumeGenerationCrew`**:
  - **Purpose**: Adapts the candidate's base profile (`resources/profile.md`) to match target vacancy requirements.
  - **Output**: Strictly formatted **YAML** string matching the `RenderCV` schema for automated PDF compilation.

- **`EmailGenerationCrew`**:
  - **Purpose**: Drafts a tailored cover letter / application email to the recruiter.
  - **Output**: Plain text email subject and body.

## 3. Custom Tools & MCP Integrations

- **MCP Browser Server (`mcp-unbrowse`)**: Exposes Playwright/CloakBrowser actions (`navigate`, `click`, `fill_form`, `extract`) as standardized MCP tools to `agy` agents inside the `antigravity-cli` container.
- **RenderCV Integration Service**: Python wrapper taking YAML output from `ResumeGenerationCrew` and generating ATS-compliant PDF resumes.
- **JobSpy ETL Tool**: Direct API fetcher for classic LinkedIn job postings.

## 4. Agent Editing Guidelines

- Update `agents.yaml` for agent roles, goals, and backstories.
- Update `tasks.yaml` to redefine task definitions and schema expectations.
- Always enforce strict output validation using **Pydantic models** (`crewai_pydantic_models.py`).
