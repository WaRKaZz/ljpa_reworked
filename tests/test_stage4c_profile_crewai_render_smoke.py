import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from ljpa_reworked.config import PROFILE_FILE_PATH, RESOURCES_DIR
from ljpa_reworked.crews.resume_evaluation_crew.resume_evaluation_crew import (
    ResumeEvaluationCrew,
)
from ljpa_reworked.crews.resume_generation_crew.resume_generation_crew import (
    ResumeGenerationCrew,
)
from ljpa_reworked.models.crewai_pydantic_models import (
    CertificationCrewAI,
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ProjectCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
)
from ljpa_reworked.services.rendercv_helper import (
    convert_resume_crewai_to_rendercv_input,
)


def test_profile_file_path_exists_and_configured():
    """Verify PROFILE_FILE_PATH is configured to resources/profile.md and exists."""
    assert PROFILE_FILE_PATH == os.path.join(RESOURCES_DIR, "profile.md")
    assert os.path.exists(PROFILE_FILE_PATH)


def test_evaluation_crew_yaml_prompts_have_no_scraping_instructions():
    """Hermetic test: Ensure evaluator YAML prompts do not instruct agents to scrape URLs."""
    eval_dir = Path(__file__).resolve().parents[1] / "src" / "ljpa_reworked" / "crews" / "resume_evaluation_crew" / "config"
    with open(eval_dir / "agents.yaml", encoding="utf-8") as f:
        agents_content = f.read().lower()
    with open(eval_dir / "tasks.yaml", encoding="utf-8") as f:
        tasks_content = f.read().lower()

    prohibited = ["scrape", "scrape_tool", "scrapewebsite", "browse", "fetch url", "open url"]
    for term in prohibited:
        assert term not in agents_content, f"Evaluator agents.yaml contains prohibited term '{term}'"
        assert term not in tasks_content, f"Evaluator tasks.yaml contains prohibited term '{term}'"


def test_generation_crew_yaml_prompts_have_no_scraping_instructions():
    """Hermetic test: Ensure resume generation YAML prompts do not instruct agents to scrape URLs."""
    gen_dir = Path(__file__).resolve().parents[1] / "src" / "ljpa_reworked" / "crews" / "resume_generation_crew" / "config"
    with open(gen_dir / "agents.yaml", encoding="utf-8") as f:
        agents_content = f.read().lower()
    with open(gen_dir / "tasks.yaml", encoding="utf-8") as f:
        tasks_content = f.read().lower()

    prohibited = ["scrape", "scrape_tool", "scrapewebsite", "browse", "fetch url", "open url"]
    for term in prohibited:
        assert term not in agents_content, f"Resume generation agents.yaml contains prohibited term '{term}'"
        assert term not in tasks_content, f"Resume generation tasks.yaml contains prohibited term '{term}'"


def test_crewai_classes_use_text_file_knowledge_source_and_no_scrape_tool():
    """Hermetic test: Verify crews use TextFileKnowledgeSource pointing to profile.md, and no ScrapeWebsiteTool."""
    from crewai.knowledge.source.text_file_knowledge_source import (
        TextFileKnowledgeSource,
    )

    with patch("ljpa_reworked.crews.resume_evaluation_crew.resume_evaluation_crew.create_llm", return_value=MagicMock()):
        eval_crew_instance = ResumeEvaluationCrew()
        agent_eval = eval_crew_instance.resume_evaluation_agent()
        assert len(agent_eval.tools) == 0, f"Evaluator agent must have no tools, got: {agent_eval.tools}"
        assert isinstance(eval_crew_instance.profile_md, TextFileKnowledgeSource)

    with patch("ljpa_reworked.crews.resume_generation_crew.resume_generation_crew.create_llm", return_value=MagicMock()):
        gen_crew_instance = ResumeGenerationCrew()
        agent_gen = gen_crew_instance.resume_agent()
        assert len(agent_gen.tools) == 0, f"Resume agent must have no tools, got: {agent_gen.tools}"
        assert isinstance(gen_crew_instance.profile_md, TextFileKnowledgeSource)


def test_convert_resume_crewai_to_rendercv_input():
    """Test mapping ResumeCrewAI into valid RenderCV input dictionary."""
    resume_data = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test Candidate",
            email="candidate@example.com",
            phone="+1 555 0199",
            address="123 Main St",
            location="Berlin, Germany",
            linkedin_url="https://linkedin.com/in/testcandidate",
        ),
        summary="A professional software engineer with 5 years experience.",
        education=[
            EducationCrewAI(
                course="Computer Science",
                institution="Tech University",
                location="Berlin, Germany",
                start_date="2018-09",
                end_date="2022-06",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Senior Backend Engineer",
                company="Tech Solutions",
                location="Remote",
                start_date="2022-07",
                end_date="Present",
                description=["Developed microservices in Python", "Optimized PostgreSQL queries"],
            )
        ],
        skills=[
            SkillCrewAI(title="Programming", elements=["Python", "Go", "SQL"])
        ],
        projects=[
            ProjectCrewAI(
                title="OpenSource Library",
                description="High performance caching library",
                url="https://github.com/test/lib",
                start_date="2023-01",
                end_date="2023-05",
                highlights=["500+ stars on GitHub"],
            )
        ],
        certifications=[
            CertificationCrewAI(
                title="AWS Certified Solutions Architect",
                issuer="Amazon Web Services",
                date="2023-08",
                url="https://aws.amazon.com/cert",
            )
        ],
    )

    rendercv_dict = convert_resume_crewai_to_rendercv_input(resume_data)

    assert "cv" in rendercv_dict
    cv = rendercv_dict["cv"]
    assert cv["name"] == "Test Candidate"
    assert cv["email"] == "candidate@example.com"
    assert cv["location"] == "Berlin, Germany"
    assert cv["social_networks"] == [{"network": "LinkedIn", "username": "testcandidate"}]

    sections = cv["sections"]
    assert "Summary" in sections
    assert "Education" in sections
    assert "Experience" in sections
    assert "Skills" in sections
    assert "Projects" in sections
    assert "Certifications" in sections

    exp = sections["Experience"][0]
    assert exp["company"] == "Tech Solutions"
    assert exp["position"] == "Senior Backend Engineer"
    assert exp["end_date"] == "present"  # RenderCV requires lowercase 'present'
    assert exp["highlights"] == ["Developed microservices in Python", "Optimized PostgreSQL queries"]


def test_resume_crews_have_deterministic_timeout_and_bounded_agent_execution():
    """Verify evaluation and generation crews configure timeout and bounded execution on LLM and Agent."""
    eval_crew = ResumeEvaluationCrew(llm_timeout=30, max_execution_time=45, max_iter=3)
    eval_agent = eval_crew.resume_evaluation_agent()
    assert eval_crew.llm.timeout == 30, f"Expected LLM timeout 30, got {eval_crew.llm.timeout}"
    assert eval_agent.max_execution_time == 45, f"Expected agent max_execution_time 45, got {eval_agent.max_execution_time}"
    assert eval_agent.max_iter == 3, f"Expected agent max_iter 3, got {eval_agent.max_iter}"

    gen_crew = ResumeGenerationCrew(llm_timeout=30, max_execution_time=45, max_iter=3)
    gen_agent = gen_crew.resume_agent()
    assert gen_crew.llm.timeout == 30, f"Expected LLM timeout 30, got {gen_crew.llm.timeout}"
    assert gen_agent.max_execution_time == 45, f"Expected agent max_execution_time 45, got {gen_agent.max_execution_time}"
    assert gen_agent.max_iter == 3, f"Expected agent max_iter 3, got {gen_agent.max_iter}"




