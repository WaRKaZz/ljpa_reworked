import os

from crewai import LLM, Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from crewai.tasks.conditional_task import ConditionalTask
from crewai.tasks.task_output import TaskOutput

from ljpa_reworked.config import GEMINI_API_KEY, GEMINI_MODEL
from ljpa_reworked.models.crewai_pydantic_models import ProcessedPost, VacancyCrewAI

config_dir = os.path.join(os.path.dirname(__file__), "config")


@CrewBase
class VacancyReviewCrew:
    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = os.path.join(config_dir, "agents.yaml")
    tasks_config = os.path.join(config_dir, "tasks.yaml")

    @agent
    def linkedin_analyst(self) -> Agent:
        llm = LLM(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
        return Agent(config=self.agents_config["linkedin_analyst"], llm=llm)

    @task
    def verify_vacancy(self) -> Task:
        return Task(
            config=self.tasks_config["verify_vacancy"],
            output_pydantic=ProcessedPost,
        )

    @task
    def process_vacancy(self) -> ConditionalTask:
        return ConditionalTask(
            config=self.tasks_config["process_vacancy"],
            output_pydantic=VacancyCrewAI,
            condition=is_vacancy,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            max_rpm=10,
        )


def is_vacancy(output: TaskOutput) -> bool:
    """Check if we should post a job"""
    if output.pydantic:
        return output.pydantic.is_vacancy
    return False


if __name__ == "__main__":
    vacancy = """Bypass this, this is not a vacancy"""
    crew = VacancyReviewCrew()
    crew.crew().kickoff(inputs={"linkedin_post": vacancy})
    print("end")
