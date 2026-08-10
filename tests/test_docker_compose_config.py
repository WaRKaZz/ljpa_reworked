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
    assert any("./resources:/app/resources" in v for v in volumes), (
        "antigravity-cli must mount ./resources:/app/resources"
    )
    assert any("./data:/app/data" in v for v in volumes), (
        "antigravity-cli must mount ./data:/app/data"
    )
    assert any("./.gemini:/home/agent/.gemini" in v for v in volumes), (
        "antigravity-cli must mount .gemini to /home/agent/.gemini"
    )


def test_dockerfile_antigravity_config():
    dockerfile_path = Path("Dockerfile.antigravity")
    assert dockerfile_path.exists(), "Dockerfile.antigravity must exist"

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "uv" in content, "Dockerfile.antigravity must install uv"
