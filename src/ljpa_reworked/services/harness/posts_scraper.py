import logging
import os
import subprocess

from ljpa_reworked.config import AGY_BIN_PATH, GEMINI_DIR

logger = logging.getLogger(__name__)


def run_agy_harness_1(prompt: str | None = None, container_name: str = "antigravity-cli-dev") -> str:
    """
    Harness 1 AGY Agent Runner:
    Delegates post searching and navigation task to the Google Antigravity SDK (`agy` CLI) agent
    running inside the dedicated container harness with strict Guard-Rails and Self-Verification audit loop.
    """
    binary = AGY_BIN_PATH
    prompt_file = os.path.join("data", "harness_prompt.txt")
    fallback_prompt_file = os.path.join("prompts", "harness_1_linkedin_posts.md")
    
    if prompt:
        task_prompt = prompt
    elif os.path.exists(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as f:
            task_prompt = f.read()
    elif os.path.exists(fallback_prompt_file):
        with open(fallback_prompt_file, "r", encoding="utf-8") as f:
            task_prompt = f.read()
    else:
        task_prompt = "/goal Discover and audit 10 LinkedIn vacancies into data/app.db"

    logger.info("Executing Harness 1 agy agent locally using binary '%s' and isolated home '%s'...", binary, GEMINI_DIR)
    cmd = [
        binary,
        "--print",
        "--print-timeout",
        "15m",
        "--dangerously-skip-permissions",
        task_prompt,
    ]
    env = {
        **os.environ,
        "HOME": GEMINI_DIR,
        "DBUS_SESSION_BUS_ADDRESS": ""
    }
    try:
        res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        logger.error("Error executing local agy harness: %s", e.stderr)
        raise


def run_agy_harness_sdk(prompt: str | None = None, verbose: bool = False) -> str:
    """
    Programmatic Harness 1 runner that delegates to a python proxy inside the container.
    """
    import sys
    logger.info("Delegating to Python SDK internal proxy via podman exec...")
    
    cmd = [
        "podman", "exec", "-i", "antigravity-cli-dev", 
        "python", "/app/agy_sdk.py"
    ]
    if prompt:
        # Pass custom prompt via stdin
        input_data = prompt
    else:
        # agy_sdk.py will read the mounted prompts/harness_1_linkedin_posts.md by default
        input_data = None

    if verbose:
        cmd.append("--verbose")
    
    try:
        if verbose:
            res = subprocess.run(cmd, input=input_data, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, check=True)
            return res.stdout.strip()
        else:
            res = subprocess.run(cmd, input=input_data, capture_output=True, text=True, check=True)
            return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_msg = getattr(e, 'stderr', None) or str(e)
        logger.error("Error executing internal python proxy: %s", error_msg)
        raise
