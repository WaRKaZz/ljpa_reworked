import os
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.knowledge.source.pdf_knowledge_source import PDFKnowledgeSource
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool

from ljpa_reworked.config import (
    CV_FILE_PATH,
    EMBED_API_KEY,
    EMBED_BASE_URL,
    EMBED_MODEL,
    EMBED_PROVIDER,
    create_llm,
)
from ljpa_reworked.models.crewai_pydantic_models import EmailCrewAI

config_dir = os.path.join(os.path.dirname(__file__), "config")

scrape_tool = ScrapeWebsiteTool()


@CrewBase
class EmailGenerationCrew:
    agents: list[BaseAgent]
    tasks: list[Task]
    agents_config = os.path.join(config_dir, "agents.yaml")
    tasks_config = os.path.join(config_dir, "tasks.yaml")

    def __init__(
        self,
        cv_file_path: str | None = CV_FILE_PATH,
        embed_provider: str = EMBED_PROVIDER,
        embed_model: str = EMBED_MODEL,
        embed_api_key: str = EMBED_API_KEY,
        embed_api_base: str = EMBED_BASE_URL,
        knowledge_sources: list | None = None,
    ) -> None:
        self.embedder = {
            "provider": embed_provider,
            "config": {
                "model": embed_model,
                "api_key": embed_api_key,
                "api_base": embed_api_base,
            },
        }
        self.llm = create_llm()
        if knowledge_sources is not None:
            self.knowledge_sources = knowledge_sources
        elif cv_file_path and os.path.exists(cv_file_path):
            self.knowledge_sources = [PDFKnowledgeSource(file_paths=[Path(cv_file_path)])]
        else:
            self.knowledge_sources = []

    @agent
    def email_generator_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["email_generator_agent"],
            llm=self.llm,
            tools=[scrape_tool],
            knowledge_sources=self.knowledge_sources if self.knowledge_sources else None,
            allow_delegation=False,
        )

    @task
    def email_generation_task(self) -> Task:
        return Task(
            config=self.tasks_config["email_generation_task"],
            output_pydantic=EmailCrewAI,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            embedder=self.embedder,
            verbose=False,
            max_rpm=10,
        )
