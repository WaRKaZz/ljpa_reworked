import yaml
from pathlib import Path

def test_compose_yml_structure():
    compose_path = Path("compose.yml")
    assert compose_path.exists(), "compose.yml must exist"
    
    with open(compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    services = config.get("services", {})
    assert "cloak-browser" in services, "compose.yml must contain service 'cloak-browser'"
    assert "linkedin-bot" in services, "compose.yml must contain service 'linkedin-bot'"
    
    cloak = services["cloak-browser"]
    assert cloak.get("image") == "cloakhq/cloakbrowser:latest"
    ports = [str(p) for p in cloak.get("ports", [])]
    assert any("9222" in p for p in ports), "cloak-browser must expose CDP port 9222"
    assert not any("6080" in p for p in ports), "VNC port 6080 must be removed"
    assert not any("5900" in p for p in ports), "VNC port 5900 must be removed"
    
    bot = services["linkedin-bot"]
    volumes = [str(v) for v in bot.get("volumes", [])]
    assert any("./resources:/app/resources" in v for v in volumes), "linkedin-bot must mount ./resources:/app/resources"
    assert any("./data:/app/data" in v for v in volumes), "linkedin-bot must mount ./data:/app/data"

def test_compose_dev_yml_structure():
    compose_dev_path = Path("compose.dev.yml")
    assert compose_dev_path.exists(), "compose.dev.yml must exist"

    with open(compose_dev_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    services = config.get("services", {})
    assert "antigravity-cli-dev" in services, "compose.dev.yml must contain service 'antigravity-cli-dev'"

    dev_service = services["antigravity-cli-dev"]
    volumes = [str(v) for v in dev_service.get("volumes", [])]
    
    assert any("./src/ljpa_reworked/services/harness" in v and ":ro" in v for v in volumes), "must mount harness directory or files read-only"

def test_dockerfile_antigravity_config():
    dockerfile_path = Path("Dockerfile.antigravity")
    assert dockerfile_path.exists(), "Dockerfile.antigravity must exist"

    content = dockerfile_path.read_text(encoding="utf-8")
    assert "python-jobspy" in content, "Dockerfile.antigravity must install python-jobspy"

