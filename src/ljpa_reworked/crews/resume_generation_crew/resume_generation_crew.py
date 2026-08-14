import json
import os

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai.tasks.task_output import TaskOutput

from ljpa_reworked.config import create_llm

config_dir = os.path.join(os.path.dirname(__file__), "config")


def resume_output_guardrail(task_output: TaskOutput) -> tuple[bool, str]:
    """Reject malformed resumes so CrewAI retries before returning output."""
    try:
        payload = json.loads(task_output.raw)
    except json.JSONDecodeError as error:
        return False, f"Return valid ResumeCrewAI JSON: {error}"

    if isinstance(payload.get("summary"), str):
        payload["summary"] = payload["summary"][:500]
    for skill in payload.get("skills", []):
        if "title" not in skill and "category" in skill:
            skill["title"] = skill.pop("category")
        if "elements" not in skill and "items" in skill:
            skill["elements"] = skill.pop("items")
        if isinstance(skill.get("elements"), str):
            skill["elements"] = [
                item.strip() for item in skill["elements"].split(",") if item.strip()
            ]

    for project in payload.get("projects", []):
        highlights = project.get("highlights", [])
        if "description" not in project and isinstance(highlights, list):
            project["description"] = " ".join(
                item for item in highlights if isinstance(item, str)
            )

    experience_required = (
        "title",
        "company",
        "location",
        "start_date",
        "end_date",
        "description",
    )
    for index, experience in enumerate(payload.get("experience", [])):
        missing = [field for field in experience_required if field not in experience]
        if missing:
            fields = ", ".join(f'"{field}"' for field in missing)
            return (
                False,
                f"HARD JSON REPAIR REQUIRED: experience[{index}] is missing {fields}. "
                "Every experience object must contain title, company, location, start_date, end_date, and description. "
                "Use only matching candidate-profile facts; do not invent dates or titles. "
                "Return only the complete JSON object, not an explanation.",
            )

    certifications = payload.get("certifications", [])
    if isinstance(certifications, list):
        payload["certifications"] = [
            {"title": certification}
            if isinstance(certification, str)
            else certification
            for certification in certifications
        ]

    for project in payload.get("projects", []):
        highlights = project.get("highlights", [])
        if not isinstance(highlights, list) or not 3 <= len(highlights) <= 4:
            count = len(highlights) if isinstance(highlights, list) else 0
            return (
                False,
                f"HARD JSON REPAIR REQUIRED: project '{project.get('title', 'untitled')}' previous output had {count} highlights. "
                "Replace its highlights field with exactly three or four distinct JSON strings. "
                'Required shape: "highlights": ["fact 1", "fact 2", "fact 3"]. '
                "Use candidate-profile facts only; do not omit the project. Return only the complete JSON object, not an explanation.",
            )

    if not isinstance(payload.get("summary"), str) or not payload["summary"].strip():
        return (
            False,
            "Provide a non-empty summary string and return only the complete JSON object.",
        )
    for index, experience in enumerate(payload.get("experience", [])):
        description = experience.get("description", [])
        if not isinstance(description, list) or len(description) < 3:
            return (
                False,
                f"Experience wording at index {index} needs at least 3 description bullets. "
                "Return only the complete JSON object.",
            )
    return True, json.dumps(payload, ensure_ascii=False)


@CrewBase
class ResumeGenerationCrew:
    agents: list[BaseAgent]
    tasks: list[Task]
    agents_config = os.path.join(config_dir, "agents.yaml")
    tasks_config = os.path.join(config_dir, "tasks.yaml")

    def __init__(
        self,
        llm_timeout: float | int | None = None,
        max_execution_time: int = 300,
        max_iter: int | None = None,
    ) -> None:
        self.llm_timeout = llm_timeout
        self.max_execution_time = max_execution_time
        self.max_iter = max_iter
        self.llm = create_llm(timeout=llm_timeout, max_tokens=4096)

    @agent
    def resume_agent(self) -> Agent:
        agent_kwargs = {
            "config": self.agents_config["resume_agent"],
            "llm": self.llm,
            "tools": [],
            "allow_delegation": False,
            "max_execution_time": self.max_execution_time,
        }
        if self.max_iter is not None:
            agent_kwargs["max_iter"] = self.max_iter
        return Agent(**agent_kwargs)

    @task
    def resume_generation_task(self) -> Task:
        return Task(
            config=self.tasks_config["resume_generation_task"],
            guardrail=resume_output_guardrail,
            guardrail_max_retries=8,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=False,
            max_rpm=10,
        )
