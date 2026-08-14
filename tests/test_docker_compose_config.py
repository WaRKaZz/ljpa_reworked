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

    if "linkedin-bot" in services:
        bot = services["linkedin-bot"]
        assert bot.get("container_name") == "linkedin-bot"

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
    assert dockerfile_path.exists(), "Dockerfile.antigravity must exist"

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "uv" in content, "Dockerfile.antigravity must install uv"


def test_compose_uses_imap_mcp_credentials_directly_from_env_file():
    config = yaml.safe_load(Path("compose.yml").read_text(encoding="utf-8"))
    cli = config["services"]["antigravity-cli"]
    assert cli["env_file"] == [".env"]
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_USERNAME" not in cli.get("environment", {})
    assert "IMAP_MCP_ACCOUNT_LJPA_GMAIL_IMAP_PASSWORD" not in cli.get("environment", {})
