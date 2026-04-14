from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.tasks.conditional_task import ConditionalTask
from crewai.tasks.task_output import TaskOutput

from ljpa_reworked.config import LLM_MODEL
from ljpa_reworked.models.crewai_pydantic_models import ProcessedPost, VacancyCrewAI


@CrewBase
class VacancyReviewCrew:
    """Crew for reviewing LinkedIn posts to identify vacancies."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    agents: list[Agent]
    tasks: list[Task]

    @property
    def llm(self) -> LLM:
        """Get the LLM instance."""
        return LLM(model=LLM_MODEL)

    @agent
    def linkedin_analyst(self) -> Agent:
        """Create the LinkedIn analyst agent."""
        return Agent(config=self.agents_config["linkedin_analyst"], llm=self.llm)

    @task
    def verify_vacancy(self) -> Task:
        """Create the vacancy verification task."""
        return Task(
            config=self.tasks_config["verify_vacancy"],
            description=self.tasks_config["verify_vacancy"]["description"],
            expected_output=self.tasks_config["verify_vacancy"]["expected_output"],
            output_pydantic=ProcessedPost,
        )

    @task
    def process_vacancy(self) -> Task:
        """Create the vacancy processing task."""
        return ConditionalTask(
            config=self.tasks_config["process_vacancy"],
            output_pydantic=VacancyCrewAI,
            condition=is_vacancy,
        )

    @crew
    def crew(self) -> Crew:
        """Create the VacancyReviewCrew crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            max_rpm=10,
        )


def is_vacancy(output: TaskOutput) -> bool:
    """Check if the post is a job vacancy."""
    if output.pydantic and isinstance(output.pydantic, ProcessedPost):
        return output.pydantic.is_vacancy
    return False


if __name__ == "__main__":
    vacancy = """Bypass this, this is not a vacancy"""
    crew_instance = VacancyReviewCrew()
    crew_instance.crew().kickoff(inputs={"linkedin_post": vacancy})
