def test_antigravity_dockerfile_copies_markitdown_mcp_from_docker_directory():
    from pathlib import Path

    content = Path("Dockerfile.antigravity").read_text(encoding="utf-8")
    assert (
        "COPY --chown=agent:agent src/ljpa_reworked/services/docker/markitdown_mcp.py "
        in content
    )
