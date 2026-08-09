# Agents and Crews Specifications

This document outlines the AI agents, crews, and tools utilized in the project.

## 1. Google Antigravity SDK (`agy`) Agents & Container Harnesses

All Harness agents are executed inside the dedicated **`antigravity-cli` (`agy`)** container, leveraging persistent skills, MCP servers (`.gemini`), session storage (`resources/state.json`), candidate resume (`resources/Danilov_Latest_CV.pdf`), and candidate personal profile (`resources/profile.md`).

- **`Harness 1: Post Search Agent`** (`linkedin_posts_agent.py`):
  - **Container & Engine**: `antigravity-cli` container (`antigravity-cli-dev`) executing the Google Antigravity SDK (`google.antigravity`) + MCP Unbrowse / Playwright server over `http://cloak-browser:9222`.
  - **Purpose**: Autonomous agent navigating LinkedIn feed (`https://www.linkedin.com/feed/`), extracting unformatted recruiter posts, validating contact credentials (email/apply link), and persisting Vacancy/LinkedinPost records to SQLite (`data/app.db`).

- **`Harness 2: Auto-Apply Web Application Agent`** (`auto_apply_agent.py`):
  - **Container & Engine**: `antigravity-cli` container (`antigravity-cli-dev`) executing Google Antigravity SDK + MCP Unbrowse / Playwright server over `http://cloak-browser:9222`.
  - **Purpose**: Autonomous agent taking job vacancy apply URLs directly from SQLite DB (`data/app.db`) and filling out external web application forms or LinkedIn Easy Apply using the candidate's RenderCV compiled PDF resume (`resources/Danilov_Latest_CV.pdf`) and candidate profile (`resources/profile.md`).
  - **Output**: Submits job application forms and updates vacancy status in SQLite database.

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
