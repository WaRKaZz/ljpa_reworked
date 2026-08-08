# Agents and Crews Specifications

This document outlines the AI crews utilized in the project, their roles, and tools.

## 1. CrewAI Crews

- **`VacancyReviewCrew`**:
  - **Purpose**: Analyzes scraped job posts to extract structured vacancy information.
  - **Output**: JSON structures defining the job title, requirements, location, and company details.

- **`ResumeEvaluationCrew`**:
  - **Purpose**: Evaluates candidate suitability against the job vacancy.
  - **Output**: A scoring report or boolean decision on whether to proceed with applying.

- **`ResumeGenerationCrew`**:
  - **Purpose**: Adapts the base resume to perfectly match the target vacancy.
  - **Output**: A tailored resume formatted in Markdown or LaTeX.

- **`EmailGenerationCrew`**:
  - **Purpose**: Drafts a compelling cover letter/email to the recruiter.
  - **Output**: Text for the email body.

## 2. Custom CrewAI Tools

The project contains custom tools in the `tools/` directory. These enable agents to:
- Parse LinkedIn data.
- Search for contact information.
- Store results into the database.

## 3. Modifying Agents

When editing agents:
- Update `agents.yaml` for agent roles, goals, and backstories.
- Update `tasks.yaml` to redefine what the agents are expected to do.
- Follow prompt engineering best practices to ensure outputs remain strict and predictable.
- Always validate the outputs of agents using Pydantic models.
