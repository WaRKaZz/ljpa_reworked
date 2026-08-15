import os

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from ljpa_reworked.config import create_llm
from ljpa_reworked.models.crewai_pydantic_models import SubmissionReviewCrewAI

config_dir = os.path.join(os.path.dirname(__file__), "config")


@CrewBase
class SubmissionReviewCrew:
    agents: list[BaseAgent]
    tasks: list[Task]
    agents_config = os.path.join(config_dir, "agents.yaml")
    tasks_config = os.path.join(config_dir, "tasks.yaml")

    def __init__(
        self,
        llm_timeout: float | int | None = 120,
    ) -> None:
        self.llm_timeout = llm_timeout
        self.llm = create_llm(timeout=llm_timeout, max_tokens=1024)

    @agent
    def submission_review_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["submission_review_agent"],
            llm=self.llm,
            tools=[],
            allow_delegation=False,
        )

    @task
    def review_submission_task(self) -> Task:
        return Task(
            config=self.tasks_config["review_submission_task"],
            output_pydantic=SubmissionReviewCrewAI,
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
