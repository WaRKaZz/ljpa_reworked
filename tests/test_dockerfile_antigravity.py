def test_antigravity_dockerfile_copies_markitdown_mcp_from_docker_directory():
    from pathlib import Path

    content = Path("Dockerfile.antigravity").read_text(encoding="utf-8")
    assert (
        "COPY --chown=agent:agent src/ljpa_reworked/services/docker/markitdown_mcp.py "
        in content
    )


def test_antigravity_dockerfile_configures_workspace_symlink_and_gemini_md():
    from pathlib import Path

    content = Path("Dockerfile.antigravity").read_text(encoding="utf-8")
    assert "ln -sf /runtime/workspace /workspace" in content
    assert "`/runtime/workspace` is the persistent writable workspace volume" in content
    assert "`/workspace` is the persistent writable workspace volume" not in content


def test_antigravity_dockerfile_configures_markitdown_mcp_stdio():
    from pathlib import Path

    content = Path("Dockerfile.antigravity").read_text(encoding="utf-8")
    assert '"markitdown": {' in content
    assert '"command": "python3"' in content
    assert '"args": ["/home/agent/.local/lib/markitdown_mcp.py"]' in content
    assert "http://markitdown-mcp" not in content
