import os

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from ljpa_reworked.config import create_llm
from ljpa_reworked.models.crewai_pydantic_models import JobSearchQuerySet

config_dir = os.path.join(os.path.dirname(__file__), "config")


@CrewBase
class QueryGenerationCrew:
    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = os.path.join(config_dir, "agents.yaml")
    tasks_config = os.path.join(config_dir, "tasks.yaml")

    @agent
    def query_strategist(self) -> Agent:
        llm = create_llm()
        return Agent(
            config=self.agents_config["query_strategist"],
            llm=llm,
            allow_delegation=False,
        )

    @task
    def generate_job_search_queries_task(self) -> Task:
        return Task(
            config=self.tasks_config["generate_job_search_queries_task"],
            output_pydantic=JobSearchQuerySet,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
