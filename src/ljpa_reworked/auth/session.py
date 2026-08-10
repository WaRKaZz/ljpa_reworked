import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path("resources/state.json")

def verify_auth_state(state_path: str | Path = DEFAULT_STATE_PATH) -> bool:
    """Validates whether the Playwright storage_state JSON file exists, is well-formed,
    and contains required authentication cookies (such as 'li_at' for LinkedIn).
    """
    path = Path(state_path)
    if not path.exists():
        # Fallback check for auth/state.json if default resources/state.json not found
        fallback = Path("auth/state.json")
        if path == DEFAULT_STATE_PATH and fallback.exists():
            path = fallback
        else:
            logger.warning(f"Auth state file does not exist: {path}")
            return False

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning(f"Auth state file content is not a JSON object: {path}")
            return False

        cookies = data.get("cookies", [])
        if not isinstance(cookies, list) or len(cookies) == 0:
            logger.warning(f"Auth state file contains no cookies: {path}")
            return False

        # Check if li_at cookie or any linkedin cookie is present
        has_li_cookie = any(
            isinstance(c, dict) and "linkedin.com" in c.get("domain", "")
            for c in cookies
        )
        if not has_li_cookie:
            logger.warning(f"Auth state file does not contain LinkedIn cookies: {path}")
            return False

        return True
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to read or parse auth state file {path}: {e}")
        return False

def load_auth_state(state_path: str | Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    """Loads and returns the storage_state dictionary from state_path.
    Raises ValueError if state file is invalid.
    """
    path = Path(state_path)
    if not verify_auth_state(path) and path == DEFAULT_STATE_PATH and Path("auth/state.json").exists():
        path = Path("auth/state.json")

    if not verify_auth_state(path):
        raise ValueError(f"Invalid or missing auth state file at {path}")
    return json.loads(path.read_text(encoding="utf-8"))
