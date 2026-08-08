import yaml
from pathlib import Path

def test_env_example_has_cdp_url():
    env_ex = Path(".env.example")
    assert env_ex.exists(), ".env.example must exist"
    content = env_ex.read_text(encoding="utf-8")
    assert "CDP_URL" in content, ".env.example must define CDP_URL"

def test_compose_yml_structure():
    compose_path = Path("compose.yml")
    assert compose_path.exists(), "compose.yml must exist"
    
    with open(compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    services = config.get("services", {})
    assert "cloak-browser" in services, "compose.yml must contain service 'cloak-browser'"
    assert "linkedin-bot" in services, "compose.yml must contain service 'linkedin-bot'"
    
    cloak = services["cloak-browser"]
    assert cloak.get("image") == "cloakhq/cloakbrowser:latest", "cloak-browser image must be cloakhq/cloakbrowser:latest"
    
    ports = cloak.get("ports", [])
    ports_str = [str(p) for p in ports]
    assert any("9222" in p for p in ports_str), "cloak-browser must expose CDP port 9222"
    assert any("6080" in p for p in ports_str), "cloak-browser must expose noVNC port 6080"
    assert any("5900" in p for p in ports_str), "cloak-browser must expose VNC port 5900"
    
    bot = services["linkedin-bot"]
    env = bot.get("environment", {})
    if isinstance(env, list):
        env = dict(item.split("=", 1) for item in env)
    cdp_url = env.get("CDP_URL", "")
    assert cdp_url in ["http://cloak-browser:9222", "${CDP_URL}", "${CDP_URL:-http://cloak-browser:9222}"] or cdp_url.startswith("${CDP_URL"), f"Unexpected CDP_URL: {cdp_url}"
    
    volumes = bot.get("volumes", [])
    v_str = [str(v) for v in volumes]
    assert any("./auth:/app/auth" in v for v in v_str), "linkedin-bot must mount ./auth:/app/auth"
    assert any("./data:/app/data" in v for v in v_str), "linkedin-bot must mount ./data:/app/data"
