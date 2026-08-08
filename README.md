# LinkedIn Job Processing Automation (LJPA) Reworked

LJPA Reworked is an autonomous AI-driven pipeline that automates the process of finding relevant job vacancies on LinkedIn, evaluating candidate suitability, generating perfectly tailored ATS resumes, and organizing applications.

Built with **CrewAI**, **Playwright**, and containerized for consistency using **Podman/Docker**, this tool brings autonomous agentic behavior to the job search process.

## 🚀 Key Features

*   **Intelligent Job Scraping:** Uses Playwright to interactively (via VNC) authenticate and traverse LinkedIn without getting blocked.
*   **Vacancy Processing & Evaluation:** CrewAI agents (`VacancyReviewCrew`, `ResumeEvaluationCrew`) read job descriptions and decide if a vacancy is a good match based on your baseline resume.
*   **Tailored ATS Resumes:** The `ResumeGenerationCrew` dynamically adapts your resume and outputs a format ready to be compiled into a pristine PDF using `RenderCV`.
*   **Automated Cover Letters:** Generates customized cover letters/emails for each specific recruiter (`EmailGenerationCrew`).
*   **Cost-Effective AI:** Supports any OpenAI-compatible API (e.g., vLLM, OpenRouter, Together AI) by configuring a custom `base_url`.

## 🛠️ Architecture & Technologies

*   **Python 3.10+** (Managed via `uv`)
*   **CrewAI** for multi-agent orchestration
*   **Playwright & Selenium (Chromium VNC)** for browser automation
*   **SQLAlchemy + Alembic** for PostgreSQL database state management
*   **Docker / Podman Compose** for infrastructure

## 📦 Installation & Setup

1. **Clone the repository and prepare environments:**
   ```bash
   git clone <your-repo>
   cd ljpa_reworked
   cp .env.example .env
   ```
   *Edit `.env` to add your `OPENAI_API_KEY`, `OPENAI_API_BASE` (if using a custom provider), and LinkedIn credentials.*

2. **Start the Container Infrastructure:**
   We use a Selenium standalone image with an integrated noVNC server to safely handle browser automation.
   
   If you want to run the bot locally (Development Mode):
   ```bash
   podman-compose -f compose.dev.yml up -d
   ```
   *(Use `docker-compose` if you are using Docker instead of Podman)*

3. **Install Python Dependencies (if running locally):**
   ```bash
   pip install uv
   uv sync
   ```

## 🔐 LinkedIn Authentication (VNC)

Before agents can scrape LinkedIn, you must authenticate. LJPA uses an interactive VNC session to safely handle 2FA and Captchas and saves the session state for headless agents.

1. Run the interactive login wrapper:
   ```bash
   ./scripts/linkedin_relogin.sh
   ```
2. Open your browser and navigate to: **http://localhost:7900/vnc.html**
3. Log into LinkedIn manually in the VNC window. The script will detect the successful login, save the session to `auth/state.json`, and close automatically.

## ⚙️ Usage

Once authenticated, you can trigger the main application pipeline:

```bash
uv run python src/ljpa_reworked/main.py
```
*(Or, if running fully containerized, it will start automatically inside the `linkedin-bot` container).*

## 🧠 Customizing Your Agents

*   **Agents Config:** `src/ljpa_reworked/config/agents.yaml`
*   **Tasks Config:** `src/ljpa_reworked/config/tasks.yaml`
*   **Custom Tools:** Inside the `tools/` directory (e.g., custom LinkedIn parsers).

## 📄 License

Check the `LICENSE.md` file for details.
