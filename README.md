# LinkedIn Job Processing Automation (LJPA) Reworked

LJPA Reworked is an autonomous AI-driven pipeline that automates the process of finding relevant job vacancies on LinkedIn, evaluating candidate suitability, generating perfectly tailored ATS resumes, and organizing applications.

Built with **CrewAI**, **Playwright**, and containerized for consistency using **Podman/Docker**, this tool brings autonomous agentic behavior to the job search process.

## 🚀 Key Features

*   **Intelligent Job Scraping:** Uses Playwright to interactively (via VNC) authenticate and traverse LinkedIn without getting blocked.
*   **Vacancy Processing & Evaluation:** CrewAI agents (`VacancyReviewCrew`, `ResumeEvaluationCrew`) read job descriptions and decide if a vacancy is a good match based on your baseline resume and visa requirements.
*   **Tailored ATS Resumes:** The `ResumeGenerationCrew` dynamically adapts your resume and outputs a format ready to be compiled into a pristine PDF using `RenderCV`.
*   **Automated Cover Letters & Direct Submissions:** Generates customized cover letters/emails for recruiters or submits applications directly through web application forms via Google Antigravity CLI harness.
*   **Cost-Effective AI:** Supports any OpenAI-compatible API (e.g., vLLM, OpenRouter, Together AI) by configuring a custom `base_url`.

## 🛠️ Architecture & Technologies

*   **Python 3.12+** (Managed via `uv`)
*   **Google Antigravity CLI (`agy`)** container harness for autonomous browser operations
*   **CrewAI** for multi-agent orchestration
*   **Playwright & CloakBrowser** for anti-detect browser automation with noVNC (`http://localhost:6080`)
*   **RenderCV** for ATS-compliant resume compilation
*   **SQLAlchemy + Alembic** for SQLite database state management (`data/app.db`)
*   **Podman / Docker Compose** for container orchestration

## 📦 Installation & Setup

1. **Clone the repository and prepare environments:**
   ```bash
   git clone <your-repo>
   cd ljpa_reworked
   cp .env.example .env
   ```
   *Edit `.env` to add your `OPENAI_API_KEY`, `OPENAI_API_BASE` (if using a custom provider), and LinkedIn credentials.*

2. **Start the Base Infrastructure:**
   Start the persistent background containers (CloakBrowser, Antigravity CLI harness, SQLite UI):
   ```bash
   podman compose up -d
   ```
   *(Or `docker compose up -d`)*

3. **Authenticate LinkedIn (Stage 1):**
   Open noVNC at `http://localhost:6080` (or the configured VNC port) and log in to LinkedIn interactively. The session will be saved.

4. **Install Python Dependencies (for local host runs):**
   ```bash
   pip install uv
   uv sync
   ```

## ⚙️ Execution Modes

LJPA is organized into three distinct, independent workflows that can be run as needed:

### 1. Collect Mode (`collect` / `linkedin-bot-collect`)
Scrapes recruiter posts on LinkedIn feed via Antigravity harness and searches official vacancies with JobSpy, then performs initial suitability evaluations (`evaluate_unrated_vacancies`).
```bash
# Run in background container:
podman compose --profile modes up -d --no-deps linkedin-bot-collect

# Or run locally:
uv run python -m ljpa_reworked.main --mode collect
```

### 2. Email Process Mode (`email_process` / `linkedin-bot-email-process`)
Evaluates unreviewed vacancies, generates tailored ATS resumes, and sends email applications with customized cover letters and PDF resumes.
- **Stopping condition:** Runs continuously until **all** vacancies with `score = rating - age_tax - visa_tax >= 50.0` have received an application.
```bash
# Run in background container:
podman compose --profile modes up -d --no-deps linkedin-bot-email-process

# Or run locally:
uv run python -m ljpa_reworked.main --mode email_process
```

### 3. URL Process Mode (`url_process` / `linkedin-bot-url-process`)
Evaluates unreviewed vacancies, generates tailored ATS resumes, and submits external web application forms or LinkedIn Easy Apply vacancies via the autonomous browser harness.
- **Stopping condition:** Iterates through top-ranked eligible vacancies as long as the remaining Gemini quota is **> 7%** (`usage > 7%` / `quota > 0.07`). Pauses when quota reaches the threshold or queue is exhausted.
```bash
# Run in background container:
podman compose --profile modes up -d --no-deps linkedin-bot-url-process

# Or run locally:
uv run python -m ljpa_reworked.main --mode url_process
```

## 🧠 Customizing Your Agents

*   **Agents Config:** `src/ljpa_reworked/config/agents.yaml`
*   **Tasks Config:** `src/ljpa_reworked/config/tasks.yaml`
*   **Candidate Profile:** `resources/profile.md`
*   **Submission Prompts:** `prompts/harness_submit.md`

## 📄 License

Check the `LICENSE.md` file for details.
