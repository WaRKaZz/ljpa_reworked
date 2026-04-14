from pathlib import Path

from crewai import LLM, Agent, Crew, Process, Task
from crewai.knowledge.source.pdf_knowledge_source import PDFKnowledgeSource
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool

from ljpa_reworked.config import CV_FILE_PATH, EMBEDDER_CONFIG, LLM_MODEL
from ljpa_reworked.models.crewai_pydantic_models import ResumeCrewAI

scrape_tool = ScrapeWebsiteTool()


@CrewBase
class ResumeGenerationCrew:
    """Crew for generating tailored resumes based on job vacancies."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    agents: list[Agent]
    tasks: list[Task]

    def __init__(self, cv_file_path: str = CV_FILE_PATH) -> None:
        """Initialize the ResumeGenerationCrew."""
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
    def resume_agent(self) -> Agent:
        """Create the resume agent."""
        return Agent(
            config=self.agents_config["resume_agent"],
            llm=self.llm,
            tools=[scrape_tool],
            knowledge_sources=[self.resume_pdf],
        )

    @task
    def resume_generation_task(self) -> Task:
        """Create the resume generation task."""
        return Task(
            config=self.tasks_config["resume_generation_task"],
            description=self.tasks_config["resume_generation_task"]["description"],
            expected_output=self.tasks_config["resume_generation_task"]["expected_output"],
            output_pydantic=ResumeCrewAI,
        )

    @task
    def resume_verification_task(self) -> Task:
        """Create the resume verification task."""
        return Task(
            config=self.tasks_config["resume_verification_task"],
            description=self.tasks_config["resume_verification_task"]["description"],
            expected_output=self.tasks_config["resume_verification_task"]["expected_output"],
            output_pydantic=ResumeCrewAI,
        )

    @crew
    def crew(self) -> Crew:
        """Create the ResumeGenerationCrew crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            embedder=EMBEDDER_CONFIG,
            verbose=False,
            max_rpm=10,
        )
