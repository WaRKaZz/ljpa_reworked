import os
import os.path
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Environment Variables
# =============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
EMAIL_SIGNATURE = os.getenv("EMAIL_SIGNATURE")
LINKEDIN_SEARCH_URL = os.getenv("LINKEDIN_SEARCH_URL")
LINKEDIN_URL = os.getenv("LINKEDIN_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://id-vps:20128/v1")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
EMBED_PROVIDER = os.getenv("EMBED_PROVIDER")
EMBED_MODEL = os.getenv("EMBED_MODEL")
EMBED_API_KEY = os.getenv("EMBED_API_KEY")
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL")
# Selenium configuration
SELENIUM_HOST = os.getenv("SELENIUM_HOST")
SELENIUM_PORT = os.getenv("SELENIUM_PORT")

LINKEDIN_PROFILE_URL = os.getenv("LINKEDIN_PROFILE_URL")

AGY_BIN_PATH = os.getenv("AGY_BIN_PATH", "/home/warkazz/.local/bin/agy")
GEMINI_DIR = os.getenv("GEMINI_DIR", os.path.expanduser("~/.gemini_alt"))

SELENIUM_COMMAND_EXECUTOR = f"http://{SELENIUM_HOST}:{SELENIUM_PORT}/wd/hub"

# =============================================================================
# File Paths and Resource Settings
# =============================================================================
BASE_DIR = Path(__file__).resolve().parents[2]
RESOURCES_DIR = str(BASE_DIR / "resources")
SCREENSHOTS_DIR = os.path.join("/tmp", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


DATA_DIR = str(BASE_DIR / "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "app.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

CV_FILE_NAME = os.getenv("CV_FILE_NAME")

CV_FILE_PATH = os.path.join(RESOURCES_DIR, CV_FILE_NAME) if CV_FILE_NAME else None
PROFILE_FILE_PATH = os.path.join(RESOURCES_DIR, "profile.md")



def create_llm(timeout: float | int | None = None):
    """Build the project LLM client for the configured OpenAI-compatible gateway."""
    from crewai import LLM

    model = LLM_MODEL if LLM_MODEL.startswith("openai/") else f"openai/{LLM_MODEL}"
    kwargs = {
        "model": model,
        "api_key": LLM_API_KEY,
        "base_url": LLM_BASE_URL,
        "custom_openai": True,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    return LLM(**kwargs)
