---
trigger: always_on
---

# Local Testing & Execution Rule

During active development and testing, adhere strictly to the following execution policy:

1. **Local Host Execution**: All function calls, module tests, script executions, and debugging tasks must be performed directly on the local host machine.
2. **Docker Container Policy**: Docker containers and Compose setups are intended for target deployment. **Do NOT build or rebuild Docker images during routine testing or development** unless explicitly instructed by the user to test the container image build itself.
