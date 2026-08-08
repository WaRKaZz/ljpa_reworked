---
name: crewai-debug
description: Instructions and scripts for locally debugging a single CrewAI crew without running the full web scraping pipeline.
---

# CrewAI Debugging Skill

This skill assists in debugging and testing individual CrewAI crews (e.g., `VacancyReviewCrew`, `ResumeEvaluationCrew`) in isolation.

## When to use

Use this skill when you need to test prompts, tool execution, or output formatting for a specific agent without waiting for the entire LinkedIn scraping pipeline to run.

## Instructions

1. **Identify the Crew**: Determine which crew you want to test.
2. **Mock the Input Data**: Create a dummy JSON or dictionary matching the input expected by the crew (e.g., a mock scraped LinkedIn post).
3. **Write a Debug Script**: Create a temporary script in the root directory (e.g., `debug_crew.py`) that imports the crew, instantiates it with the mock data, and calls the `kickoff()` method.
4. **Run and Observe**: Execute `uv run python debug_crew.py` to see the agent's thought process and final output.
5. **Adjust and Repeat**: Tweak `agents.yaml` or `tasks.yaml` as needed until the output matches expectations.
6. **Clean Up**: Remove or gitignore the debug script once finished.
