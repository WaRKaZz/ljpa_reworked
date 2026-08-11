import os

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from ljpa_reworked.config import create_llm
from ljpa_reworked.models.crewai_pydantic_models import ResumeCrewAI

config_dir = os.path.join(os.path.dirname(__file__), "config")


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
        super().__init__()
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
            "max_execution_time": self.max_execution_time,
        }
        if self.max_iter is not None:
            agent_kwargs["max_iter"] = self.max_iter
        return Agent(**agent_kwargs)

    @task
    def resume_generation_task(self) -> Task:
        return Task(
            config=self.tasks_config["resume_generation_task"],
            output_pydantic=ResumeCrewAI,
            max_execution_time=600,
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
