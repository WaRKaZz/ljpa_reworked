from pathlib import Path

from crewai import LLM, Agent, Crew, Process, Task
from crewai.knowledge.source.pdf_knowledge_source import PDFKnowledgeSource
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool

from ljpa_reworked.config import CV_FILE_PATH, EMBEDDER_CONFIG, LLM_MODEL
from ljpa_reworked.models.crewai_pydantic_models import EmailCrewAI

scrape_tool = ScrapeWebsiteTool()


@CrewBase
class EmailGenerationCrew:
    """Crew for generating personalized job application emails."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    agents: list[Agent]
    tasks: list[Task]

    def __init__(self, cv_file_path: str = CV_FILE_PATH) -> None:
        """Initialize the EmailGenerationCrew."""
        self.cv_file_path = cv_file_path

    @property
    def llm(self) -> LLM:
        """Get the LLM instance."""
        return LLM(model=LLM_MODEL)

    @property
    def resume_pdf(self) -> PDFKnowledgeSource:
        """Get the PDF knowledge source for the resume."""
        return PDFKnowledgeSource(file_paths=[Path(self.cv_file_path)])

    @agent
    def email_generator_agent(self) -> Agent:
        """Create the email generator agent."""
        return Agent(
            config=self.agents_config["email_generator_agent"],
            llm=self.llm,
            tools=[scrape_tool],
            knowledge_sources=[self.resume_pdf],
        )

    @task
    def email_generation_task(self) -> Task:
        """Create the email generation task."""
        return Task(
            config=self.tasks_config["email_generation_task"],
            description=self.tasks_config["email_generation_task"]["description"],
            expected_output=self.tasks_config["email_generation_task"]["expected_output"],
            output_pydantic=EmailCrewAI,
        )

    @crew
    def crew(self) -> Crew:
        """Create the EmailGenerationCrew crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            embedder=EMBEDDER_CONFIG,
            verbose=False,
            max_rpm=10,
        )
