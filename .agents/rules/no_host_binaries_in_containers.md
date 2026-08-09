# No Host Binaries in Container Builds Rule

**STRICT MANDATE:**
When building Docker / Podman containers or defining container compose configurations:
1. **NEVER** mount host binaries (e.g., `/home/warkazz/.local/bin/agy`, system executables, host CLI tools) into container volumes or container `$PATH`.
2. All containerized CLI tools, dependencies, and environments (including Google Antigravity SDK `google-antigravity`, Node.js, `unbrowse`, etc.) MUST be installed natively inside the container image or downloaded directly inside the Dockerfile.
