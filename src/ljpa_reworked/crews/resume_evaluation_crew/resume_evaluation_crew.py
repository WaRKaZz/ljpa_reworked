import os
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.knowledge.knowledge import Knowledge
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource
from crewai.project import CrewBase, agent, crew, task

from ljpa_reworked.config import (
    EMBED_API_KEY,
    EMBED_BASE_URL,
    EMBED_MODEL,
    EMBED_PROVIDER,
    PROFILE_FILE_PATH,
    create_llm,
)
from ljpa_reworked.models.crewai_pydantic_models import BasicEvaluationCrewAI

config_dir = os.path.join(os.path.dirname(__file__), "config")


@CrewBase
class ResumeEvaluationCrew:
    agents: list[BaseAgent]
    tasks: list[Task]
    agents_config = os.path.join(config_dir, "agents.yaml")
    tasks_config = os.path.join(config_dir, "tasks.yaml")

    def __init__(
        self,
        profile_file_path: str = PROFILE_FILE_PATH,
        embed_provider: str | None = EMBED_PROVIDER,
        embed_model: str | None = EMBED_MODEL,
        embed_api_key: str | None = EMBED_API_KEY,
        embed_api_base: str | None = EMBED_BASE_URL,
    ) -> None:
        super().__init__()
        profile_path = Path(profile_file_path).resolve()
        if embed_provider and embed_model:
            self.embedder = {
                "provider": embed_provider,
                "config": {
                    "model": embed_model,
                    "api_key": embed_api_key,
                    "api_base": embed_api_base,
                },
            }
        else:
            self.embedder = None

        self.llm = create_llm()
        self.profile_md = TextFileKnowledgeSource(
            file_paths=[
                profile_path,
            ]
        )

    @agent
    def resume_evaluation_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["resume_evaluation_agent"],
            llm=self.llm,
            tools=[],
            max_execution_time=300,
        )

    @task
    def evaluate_resume_task(self) -> Task:
        return Task(
            config=self.tasks_config["evaluate_resume_task"],
            output_pydantic=BasicEvaluationCrewAI,
        )

    @crew
    def crew(self) -> Crew:
        knowledge = Knowledge(
            collection_name="resume_evaluation_profile",
            sources=[self.profile_md],
            embedder=self.embedder,
        )
        crew_kwargs = {
            "agents": self.agents,
            "tasks": self.tasks,
            "process": Process.sequential,
            "knowledge": knowledge,
            "verbose": False,
            "max_rpm": 10,
        }
        if self.embedder:
            crew_kwargs["embedder"] = self.embedder
        return Crew(**crew_kwargs)
