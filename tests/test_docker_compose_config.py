from pathlib import Path

import yaml


def test_compose_yml_structure():
    compose_path = Path("compose.yml")
    assert compose_path.exists(), "compose.yml must exist"

    with open(compose_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    services = config.get("services", {})
    assert "cloak-browser" in services, (
        "compose.yml must contain service 'cloak-browser'"
    )
    assert "antigravity-cli" in services, (
        "compose.yml must contain service 'antigravity-cli'"
    )

    cloak = services["cloak-browser"]
    assert cloak.get("image") == "docker.io/cloakhq/cloakbrowser:latest"
    assert "ports" not in cloak, "CDP must stay inside the Compose network"

    assert "linkedin-bot" in services, "compose.yml must contain service 'linkedin-bot'"
    assert "linkedin-bot-collect" not in services
    assert "linkedin-bot-url-process" not in services
    assert "linkedin-bot-email-process" not in services

    bot = services["linkedin-bot"]
    assert bot.get("build") == ".", "linkedin-bot must define build context"
    assert bot["userns_mode"] == "keep-id"
    assert "./data:/app/data" in bot["volumes"]
    assert bot["command"] == [
        "sh",
        "-c",
        "mkdir -p /app/data && touch /app/data/bot.log && tail -F /app/data/bot.log",
    ]

    cli = services["antigravity-cli"]
    volumes = [str(v) for v in cli.get("volumes", [])]
    assert volumes == ["./runtime:/runtime", "./resources:/inputs/resources:ro"]
    assert "agy-workspace" not in config.get("volumes", {})
    assert cli["command"] == ["python3", "/app/harness/harness_server.py"]
    assert cli["environment"]["HARNESS_DATA_DIR"] == "/runtime/harness-scraper"
    assert cli["environment"]["HARNESS_RESOURCES_DIR"] == "/inputs/resources"
    assert cli["environment"]["GEMINI_DIR"] == "/runtime/gemini"


def test_dockerfile_antigravity_config():
    dockerfile_path = Path("Dockerfile.antigravity")
    assert dockerfile_path.exists(), "Dockerfile.antigravity must install uv"

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "uv" in content, "Dockerfile.antigravity must install uv"


def test_compose_uses_imap_mcp_credentials_directly_from_env_file():
    config = yaml.safe_load(Path("compose.yml").read_text(encoding="utf-8"))
    cli = config["services"]["antigravity-cli"]
    assert cli["env_file"] == [".env"]
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_USERNAME" not in cli.get("environment", {})
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_PASSWORD" not in cli.get("environment", {})


def test_linkedin_bot_dockerfile_copies_only_existing_dependency_manifests():
    content = Path("Dockerfile").read_text(encoding="utf-8")

    assert "COPY pyproject.toml uv.lock ./" in content
    assert "alembic.ini" not in content


def test_cloak_browser_keeps_image_entrypoint_that_starts_xvfb():
    config = yaml.safe_load(Path("compose.yml").read_text(encoding="utf-8"))
    cloak = config["services"]["cloak-browser"]

    assert "entrypoint" not in cloak
    assert cloak["command"] == ["/bin/sh", "/init_cloak.sh"]


def test_antigravity_playwright_mcp_is_pinned_to_cloak_cdp():
    content = Path("Dockerfile.antigravity").read_text(encoding="utf-8")

    assert '"playwright": {' in content
    assert '"args": ["--cdp-endpoint", "http://cloak-browser:9222"]' in content


def test_submit_prompt_forbids_local_browser_fallbacks():
    prompt = Path("prompts/harness_submit.md").read_text(encoding="utf-8")

    assert (
        "The configured `playwright` MCP is already pinned to `http://cloak-browser:9222`."
        in prompt
    )
    assert (
        "Do not run `npx playwright install`, `unbrowse setup`, or a local CDP proxy."
        in prompt
    )


def test_antigravity_entrypoint_waits_for_cloak_cdp():
    entrypoint = Path(
        "src/ljpa_reworked/services/docker/antigravity-entrypoint.sh"
    ).read_text(encoding="utf-8")

    assert '"/json/version"' in entrypoint
    assert "Cloak Browser CDP did not become ready" in entrypoint
